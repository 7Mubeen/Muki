"""Verified, low-memory local snapshots for MUKI.

This module deliberately does not move or rename the live database. It uses
SQLite's online backup API and copies the application's managed media folder
into an atomically published snapshot directory.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile

from muki import __version__


FORMAT_VERSION = 1
DATABASE_FILENAME = "muki.sqlite3"
MANIFEST_FILENAME = "manifest.json"
COPY_CHUNK_SIZE = 1024 * 1024
DEFAULT_RETENTION = 7


class BackupError(RuntimeError):
    """Raised when a MUKI backup cannot be safely created or verified."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_check(path: Path) -> None:
    try:
        connection = sqlite3.connect(str(path))
        try:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise BackupError("The backup database could not be checked: {}".format(exc)) from exc
    if rows != [("ok",)]:
        details = "; ".join(str(row[0]) for row in rows[:10])
        raise BackupError("SQLite integrity check failed: {}".format(details or "unknown error"))


def _safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BackupError("The backup manifest contains an unsafe file path.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise BackupError("The backup manifest contains an unsafe file path: {}".format(value))
    if path.parts[0] not in (DATABASE_FILENAME, "media"):
        raise BackupError("The backup manifest contains an unexpected path: {}".format(value))
    return path


class BackupManager:
    """Create and verify local MUKI backup snapshots.

    Args:
        database: An open MUKI Database instance.
        media_dir: The existing managed media directory. Defaults to
            '<database parent>/media'.
        backup_root: Defaults to '<database parent>/backups'.
        retention: Number of verified automatic snapshots to retain.
    """

    def __init__(
        self,
        database,
        media_dir: str | Path | None = None,
        backup_root: str | Path | None = None,
        retention: int = DEFAULT_RETENTION,
    ):
        self.database = database
        self.database_path = Path(database.path)
        self.data_dir = self.database_path.parent
        self.media_dir = Path(media_dir) if media_dir is not None else self.data_dir / "media"
        self.backup_root = Path(backup_root) if backup_root is not None else self.data_dir / "backups"
        self.retention = int(retention)
        if self.retention < 1:
            raise ValueError("Backup retention must be at least one snapshot.")

    def create_snapshot(self, backup_type: str = "manual") -> Path:
        """Create and verify an atomic 'automatic' or 'manual' snapshot."""
        if backup_type not in ("automatic", "manual"):
            raise ValueError("Backup type must be 'automatic' or 'manual'.")
        category = self.backup_root / backup_type
        category.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc)
        base_name = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
        final_path = category / base_name
        suffix = 1
        while final_path.exists():
            final_path = category / "{}-{}".format(base_name, suffix)
            suffix += 1

        staging = Path(tempfile.mkdtemp(prefix=".muki-backup-", dir=str(category)))
        try:
            database_copy = staging / DATABASE_FILENAME
            self._copy_database(database_copy)
            copied_media = self._copy_media(staging / "media")
            missing_media = self._find_missing_media(database_copy)
            stats, schema_version = self._database_metadata(database_copy)

            inventory = []
            inventory.append({
                "path": DATABASE_FILENAME,
                "size": database_copy.stat().st_size,
                "sha256": _sha256(database_copy),
            })
            for relative in copied_media:
                path = staging / "media" / relative
                inventory.append({
                    "path": "media/" + relative.as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                })

            manifest = {
                "format_version": FORMAT_VERSION,
                "backup_type": backup_type,
                "created_at": timestamp.isoformat(),
                "muki_version": __version__,
                "database_schema_version": schema_version,
                "database_stats": stats,
                "files": inventory,
                "missing_media": missing_media,
            }
            manifest_path = staging / MANIFEST_FILENAME
            with manifest_path.open("w", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())

            self.verify_snapshot(staging)
            os.rename(str(staging), str(final_path))
        except Exception:
            if staging.exists():
                shutil.rmtree(str(staging), ignore_errors=True)
            raise

        if backup_type == "automatic":
            self._prune_automatic()
        return final_path

    def _copy_database(self, destination: Path) -> None:
        try:
            target = sqlite3.connect(str(destination))
            try:
                self.database.connection.backup(target, pages=128, sleep=0.01)
                target.commit()
            finally:
                target.close()
        except sqlite3.Error as exc:
            raise BackupError("Could not create a consistent SQLite snapshot: {}".format(exc)) from exc
        _integrity_check(destination)

    def _copy_media(self, destination: Path) -> list[Path]:
        copied = []
        destination.mkdir(parents=True, exist_ok=True)
        if not self.media_dir.exists():
            return copied
        if self.media_dir.is_symlink() or not self.media_dir.is_dir():
            raise BackupError("The MUKI media path is not a regular directory.")

        for root, directories, filenames in os.walk(str(self.media_dir), topdown=True, followlinks=False):
            root_path = Path(root)
            for name in list(directories):
                source = root_path / name
                if source.is_symlink():
                    raise BackupError("Symbolic links are not allowed in managed media: {}".format(source))
            relative_root = root_path.relative_to(self.media_dir)
            target_root = destination / relative_root
            target_root.mkdir(parents=True, exist_ok=True)
            for name in filenames:
                source = root_path / name
                if source.is_symlink() or not source.is_file():
                    raise BackupError("Non-regular media file cannot be backed up: {}".format(source))
                relative = source.relative_to(self.media_dir)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(source), str(target))
                copied.append(relative)
        return sorted(copied, key=lambda item: item.as_posix())

    def _find_missing_media(self, database_copy: Path) -> list[str]:
        """Find media paths stored in note fields that no longer exist."""
        if not self.media_dir.exists():
            media_root = self.media_dir.resolve()
        else:
            media_root = self.media_dir.resolve()
        missing = set()
        connection = sqlite3.connect(str(database_copy))
        try:
            rows = connection.execute("SELECT fields_json FROM notes").fetchall()
        except sqlite3.Error:
            return []
        finally:
            connection.close()

        def visit(value):
            if isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
            elif isinstance(value, str):
                candidate = Path(value)
                if not candidate.is_absolute():
                    return
                try:
                    relative = candidate.resolve(strict=False).relative_to(media_root)
                except (ValueError, OSError):
                    return
                if not candidate.is_file():
                    missing.add(relative.as_posix())

        for row in rows:
            try:
                visit(json.loads(row[0] or "{}"))
            except (TypeError, ValueError):
                continue
        return sorted(missing)

    @staticmethod
    def _database_metadata(database_path: Path) -> tuple[dict, int | None]:
        connection = sqlite3.connect(str(database_path))
        try:
            stats = {}
            for table, key in (
                ("decks", "decks"),
                ("notes", "notes"),
                ("cards", "cards"),
                ("review_logs", "reviews"),
                ("practice_logs", "practice_reviews"),
                ("media", "media_records"),
            ):
                try:
                    stats[key] = int(connection.execute(
                        "SELECT COUNT(*) FROM {}".format(table)
                    ).fetchone()[0])
                except sqlite3.Error:
                    stats[key] = 0
            try:
                row = connection.execute(
                    "SELECT version FROM schema_version LIMIT 1"
                ).fetchone()
                schema_version = int(row[0]) if row else None
            except sqlite3.Error:
                schema_version = None
            return stats, schema_version
        finally:
            connection.close()

    def verify_snapshot(self, snapshot_path: str | Path) -> dict:
        """Verify manifest paths, inventory, checksums, and SQLite integrity."""
        snapshot = Path(snapshot_path)
        if snapshot.is_symlink() or not snapshot.is_dir():
            raise BackupError("The selected backup is not a regular snapshot directory.")
        manifest_path = snapshot / MANIFEST_FILENAME
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise BackupError("The backup manifest is missing.")
        try:
            with manifest_path.open("r", encoding="utf-8") as stream:
                manifest = json.load(stream)
        except (OSError, ValueError) as exc:
            raise BackupError("The backup manifest is unreadable or invalid.") from exc
        if manifest.get("format_version") != FORMAT_VERSION:
            raise BackupError("This backup uses an unsupported manifest format.")
        if manifest.get("backup_type") not in ("automatic", "manual"):
            raise BackupError("The backup type in the manifest is invalid.")
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise BackupError("The backup file inventory is missing.")

        expected = set()
        for entry in files:
            if not isinstance(entry, dict):
                raise BackupError("The backup file inventory is invalid.")
            relative = _safe_relative_path(entry.get("path"))
            key = relative.as_posix()
            if key in expected:
                raise BackupError("The backup manifest contains duplicate paths.")
            expected.add(key)
            path = snapshot.joinpath(*relative.parts)
            if path.is_symlink() or not path.is_file():
                raise BackupError("A required backup file is missing or unsafe: {}".format(key))
            if path.stat().st_size != entry.get("size"):
                raise BackupError("Backup file size does not match the manifest: {}".format(key))
            if _sha256(path) != entry.get("sha256"):
                raise BackupError("Backup checksum mismatch: {}".format(key))

        actual = set()
        for root, directories, filenames in os.walk(str(snapshot), followlinks=False):
            root_path = Path(root)
            for name in directories:
                if (root_path / name).is_symlink():
                    raise BackupError("Symbolic links are not allowed in a backup.")
            for name in filenames:
                path = root_path / name
                if path.is_symlink():
                    raise BackupError("Symbolic links are not allowed in a backup.")
                relative = path.relative_to(snapshot).as_posix()
                if relative != MANIFEST_FILENAME:
                    actual.add(relative)
        if actual != expected:
            raise BackupError("The backup contains missing or unexpected files.")

        database_path = snapshot / DATABASE_FILENAME
        if DATABASE_FILENAME not in expected:
            raise BackupError("The backup database is missing from its inventory.")
        _integrity_check(database_path)
        return manifest

    def _prune_automatic(self) -> None:
        category = self.backup_root / "automatic"
        valid = []
        for candidate in category.iterdir():
            if not candidate.is_dir() or candidate.name.startswith(".muki-backup-"):
                continue
            try:
                manifest = self.verify_snapshot(candidate)
                valid.append((manifest.get("created_at", ""), candidate))
            except BackupError:
                # Never delete an unverified directory automatically.
                continue
        valid.sort(key=lambda item: item[0], reverse=True)
        for _, old_path in valid[self.retention:]:
            shutil.rmtree(str(old_path))
