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
import stat
import tempfile
import zipfile

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
    if not path.parts or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
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
        if not isinstance(manifest, dict):
            raise BackupError("The backup manifest must contain a JSON object.")
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
            size = entry.get("size")
            checksum = entry.get("sha256")
            if not isinstance(size, int) or size < 0 or not isinstance(checksum, str):
                raise BackupError("The backup manifest has invalid size or checksum data.")
            expected.add(key)
            path = snapshot.joinpath(*relative.parts)
            if path.is_symlink() or not path.is_file():
                raise BackupError("A required backup file is missing or unsafe: {}".format(key))
            if path.stat().st_size != size:
                raise BackupError("Backup file size does not match the manifest: {}".format(key))
            if _sha256(path) != checksum:
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

    def export_archive(self, snapshot_path: str | Path, destination: str | Path) -> Path:
        """Export a verified snapshot as a portable .muki-backup ZIP archive."""
        snapshot = Path(snapshot_path)
        manifest = self.verify_snapshot(snapshot)
        destination = Path(destination)
        if destination.suffix.lower() != ".muki-backup":
            raise BackupError("Portable backups must use the .muki-backup extension.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            destination.resolve().relative_to(snapshot.resolve())
        except ValueError:
            pass
        else:
            raise BackupError("The portable archive cannot be written inside its source snapshot.")

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".{}-".format(destination.name),
            suffix=".tmp",
            dir=str(destination.parent),
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(str(temporary), "w", compression=zipfile.ZIP_STORED) as archive:
                archive.write(str(snapshot / MANIFEST_FILENAME), MANIFEST_FILENAME)
                for entry in manifest["files"]:
                    relative = _safe_relative_path(entry["path"])
                    source = snapshot.joinpath(*relative.parts)
                    archive.write(str(source), relative.as_posix())
            with temporary.open("rb+") as stream:
                os.fsync(stream.fileno())
            os.replace(str(temporary), str(destination))
        except Exception as exc:
            if temporary.exists():
                temporary.unlink()
            if isinstance(exc, BackupError):
                raise
            raise BackupError("Could not export the portable backup: {}".format(exc)) from exc
        return destination

    def import_archive(self, archive_path: str | Path) -> Path:
        """Validate and import a portable archive into manual local snapshots."""
        archive_path = Path(archive_path)
        if not archive_path.is_file() or archive_path.suffix.lower() != ".muki-backup":
            raise BackupError("Choose a valid .muki-backup archive.")
        category = self.backup_root / "manual"
        category.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".muki-backup-import-", dir=str(category)))
        try:
            try:
                archive = zipfile.ZipFile(str(archive_path), "r")
            except (OSError, zipfile.BadZipFile) as exc:
                raise BackupError("The selected file is not a valid MUKI backup archive.") from exc
            with archive:
                entries = {}
                for info in archive.infolist():
                    name = info.filename
                    if name in entries:
                        raise BackupError("The archive contains duplicate file names.")
                    if info.is_dir():
                        raise BackupError("Directory entries are not permitted in a MUKI backup archive.")
                    if stat.S_ISLNK(info.external_attr >> 16):
                        raise BackupError("Symbolic links are not permitted in a MUKI backup archive.")
                    if name == MANIFEST_FILENAME:
                        entries[name] = info
                    else:
                        relative = _safe_relative_path(name)
                        if relative.as_posix() != name:
                            raise BackupError("The archive contains a non-canonical file path.")
                        entries[name] = info

                manifest_info = entries.get(MANIFEST_FILENAME)
                if manifest_info is None or manifest_info.file_size > 1024 * 1024:
                    raise BackupError("The archive manifest is missing or too large.")
                try:
                    manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
                except (UnicodeDecodeError, ValueError) as exc:
                    raise BackupError("The archive manifest is invalid.") from exc
                if not isinstance(manifest, dict) or manifest.get("format_version") != FORMAT_VERSION:
                    raise BackupError("This archive uses an unsupported MUKI backup format.")
                if manifest.get("backup_type") not in ("automatic", "manual"):
                    raise BackupError("The archive backup type is invalid.")
                files = manifest.get("files")
                if not isinstance(files, list) or not files:
                    raise BackupError("The archive file inventory is missing.")

                expected = {}
                total_size = 0
                for item in files:
                    if not isinstance(item, dict):
                        raise BackupError("The archive file inventory is invalid.")
                    relative = _safe_relative_path(item.get("path"))
                    key = relative.as_posix()
                    if key in expected:
                        raise BackupError("The archive manifest contains duplicate paths.")
                    size = item.get("size")
                    checksum = item.get("sha256")
                    if not isinstance(size, int) or size < 0 or not isinstance(checksum, str):
                        raise BackupError("The archive file inventory has invalid size or checksum data.")
                    expected[key] = (relative, size, checksum)
                    total_size += size

                archive_names = set(entries) - {MANIFEST_FILENAME}
                if archive_names != set(expected):
                    raise BackupError("The archive contains missing or unexpected files.")
                if DATABASE_FILENAME not in expected:
                    raise BackupError("The archive does not contain a database snapshot.")

                free_space = shutil.disk_usage(str(category)).free
                if total_size > max(0, free_space - 8 * 1024 * 1024):
                    raise BackupError("There is not enough free disk space to import this backup safely.")

                for key, (relative, expected_size, expected_hash) in expected.items():
                    info = entries[key]
                    if info.file_size != expected_size:
                        raise BackupError("Archive file size does not match the manifest: {}".format(key))
                    target = temporary.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    copied = 0
                    with archive.open(info, "r") as source, target.open("wb") as output:
                        for chunk in iter(lambda: source.read(COPY_CHUNK_SIZE), b""):
                            copied += len(chunk)
                            if copied > expected_size:
                                raise BackupError("Archive file exceeds its declared size: {}".format(key))
                            digest.update(chunk)
                            output.write(chunk)
                    if copied != expected_size or digest.hexdigest() != expected_hash:
                        raise BackupError("Archive checksum mismatch: {}".format(key))

            manifest["backup_type"] = "manual"
            manifest["imported_from"] = archive_path.name
            manifest["imported_at"] = datetime.now(timezone.utc).isoformat()
            with (temporary / MANIFEST_FILENAME).open("w", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.verify_snapshot(temporary)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            final_path = category / ("imported-" + timestamp)
            suffix = 1
            while final_path.exists():
                final_path = category / ("imported-{}-{}".format(timestamp, suffix))
                suffix += 1
            os.rename(str(temporary), str(final_path))
            return final_path
        except Exception:
            if temporary.exists():
                shutil.rmtree(str(temporary), ignore_errors=True)
            raise

    @staticmethod
    def _write_restore_marker(data_dir: Path, marker: dict) -> Path:
        marker_path = data_dir / ".muki-restore-in-progress.json"
        temporary = data_dir / ".muki-restore-in-progress.tmp"
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(marker, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(marker_path))
        return marker_path

    @staticmethod
    def recover_interrupted_restore(data_dir: str | Path) -> bool:
        """Roll back an interrupted two-directory restore before opening SQLite."""
        data_dir = Path(data_dir)
        marker_path = data_dir / ".muki-restore-in-progress.json"
        if not marker_path.exists():
            return False
        if marker_path.is_symlink() or not marker_path.is_file():
            raise BackupError("An unsafe restore recovery marker was found; refusing to open MUKI data.")
        try:
            with marker_path.open("r", encoding="utf-8") as stream:
                marker = json.load(stream)
        except (OSError, ValueError) as exc:
            raise BackupError("The restore recovery marker is unreadable; preserve the data folder and seek recovery.") from exc
        if not isinstance(marker, dict) or marker.get("format_version") != 1:
            raise BackupError("The restore recovery marker has an unsupported format.")

        recovery_relative = marker.get("recovery_dir")
        stage_name = marker.get("stage_dir")
        if not isinstance(recovery_relative, str) or not isinstance(stage_name, str):
            raise BackupError("The restore recovery marker is incomplete.")
        recovery_path = Path(recovery_relative)
        if recovery_path.is_absolute() or ".." in recovery_path.parts:
            raise BackupError("The restore recovery marker contains an unsafe path.")
        if recovery_path.parts[:2] != ("backups", "restore-recovery"):
            raise BackupError("The restore recovery directory is outside the managed backup folder.")
        if Path(stage_name).name != stage_name or not stage_name.startswith(".muki-restore-stage-"):
            raise BackupError("The restore staging directory in the recovery marker is unsafe.")

        recovery_dir = data_dir / recovery_path
        stage_dir = data_dir / stage_name
        live_database = data_dir / DATABASE_FILENAME
        live_media = data_dir / "media"
        old_database = recovery_dir / DATABASE_FILENAME
        old_media = recovery_dir / "media"
        phase = marker.get("phase", "prepared")
        had_media = marker.get("had_media") is True

        if old_database.exists():
            if live_database.exists():
                live_database.unlink()
            os.replace(str(old_database), str(live_database))
        elif not live_database.exists():
            raise BackupError(
                "Restore recovery cannot find either the original or current database. "
                "Do not delete the recovery folder: {}.".format(recovery_dir)
            )

        if old_media.exists():
            if live_media.exists():
                shutil.rmtree(str(live_media))
            os.replace(str(old_media), str(live_media))
        elif had_media and phase in ("old_media_moved", "new_database_installed", "new_media_installed"):
            if not live_media.exists():
                raise BackupError("Restore recovery cannot find the original media folder.")
        elif not had_media and phase in ("old_database_moved", "old_media_moved", "new_database_installed", "new_media_installed") and live_media.exists():
            shutil.rmtree(str(live_media))

        if stage_dir.exists():
            shutil.rmtree(str(stage_dir), ignore_errors=True)
        if recovery_dir.exists():
            shutil.rmtree(str(recovery_dir), ignore_errors=True)
        marker_path.unlink()
        return True

    @staticmethod
    def _rebase_media_paths(database_path: Path, media_dir: Path, manifest: dict) -> None:
        """Rebase managed absolute media paths for the machine receiving a restore."""
        media_paths = set(manifest.get("missing_media", []))
        for item in manifest.get("files", []):
            name = item.get("path", "")
            if isinstance(name, str) and name.startswith("media/"):
                media_paths.add(name[len("media/"):])
        media_paths.discard("")
        if not media_paths:
            return

        def rebase(value):
            if not isinstance(value, str):
                return value
            candidate = Path(value)
            if not candidate.is_absolute():
                return value
            for index, part in enumerate(candidate.parts):
                if part == "media" and index + 1 < len(candidate.parts):
                    relative = PurePosixPath(*candidate.parts[index + 1:]).as_posix()
                    if relative in media_paths:
                        return str(media_dir.joinpath(*PurePosixPath(relative).parts))
            return value

        def visit(value):
            if isinstance(value, dict):
                return {key: visit(child) for key, child in value.items()}
            if isinstance(value, list):
                return [visit(child) for child in value]
            return rebase(value)

        connection = sqlite3.connect(str(database_path))
        try:
            rows = connection.execute("SELECT id, fields_json FROM notes").fetchall()
            for note_id, fields_json in rows:
                try:
                    fields = json.loads(fields_json or "{}")
                except (TypeError, ValueError):
                    continue
                updated = visit(fields)
                if updated != fields:
                    connection.execute(
                        "UPDATE notes SET fields_json=? WHERE id=?",
                        (json.dumps(updated, ensure_ascii=False), note_id),
                    )
            try:
                media_rows = connection.execute("SELECT id, relative_path FROM media").fetchall()
            except sqlite3.Error:
                media_rows = []
            for media_id, relative_path in media_rows:
                updated_path = rebase(relative_path)
                if updated_path != relative_path:
                    connection.execute(
                        "UPDATE media SET relative_path=? WHERE id=?",
                        (updated_path, media_id),
                    )
            connection.commit()
        finally:
            connection.close()

    def restore_snapshot(self, snapshot_path: str | Path) -> tuple[object, Path]:
        """Restore a verified snapshot, retaining a safety backup and rollback path.

        Returns (new_database, safety_snapshot_path). The application must replace
        its Database reference with the returned connection.
        """
        snapshot = Path(snapshot_path)
        manifest = self.verify_snapshot(snapshot)
        safety_snapshot = self.create_snapshot("automatic")

        stage_dir = Path(tempfile.mkdtemp(
            prefix=".muki-restore-stage-", dir=str(self.data_dir)
        ))
        recovery_root = self.backup_root / "restore-recovery"
        recovery_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        recovery_dir = recovery_root / timestamp
        recovery_dir.mkdir()
        stage_database = stage_dir / DATABASE_FILENAME
        stage_media = stage_dir / "media"
        live_database = self.data_dir / DATABASE_FILENAME
        live_media = self.media_dir
        had_media = live_media.exists()

        try:
            shutil.copy2(str(snapshot / DATABASE_FILENAME), str(stage_database))
            source_media = snapshot / "media"
            if source_media.is_dir():
                shutil.copytree(str(source_media), str(stage_media))
            else:
                stage_media.mkdir()
            self._rebase_media_paths(stage_database, live_media, manifest)

            # Validate that this application can open the staged database before
            # touching the live database or media directory.
            from muki.database import Database
            staged_database = Database(stage_database)
            staged_database.close()

            marker = {
                "format_version": 1,
                "phase": "prepared",
                "recovery_dir": str(recovery_dir.relative_to(self.data_dir)),
                "stage_dir": stage_dir.name,
                "had_media": had_media,
            }
            marker_path = self._write_restore_marker(self.data_dir, marker)
            self.database.close()

            try:
                os.replace(str(live_database), str(recovery_dir / DATABASE_FILENAME))
                marker["phase"] = "old_database_moved"
                self._write_restore_marker(self.data_dir, marker)

                if had_media:
                    os.replace(str(live_media), str(recovery_dir / "media"))
                marker["phase"] = "old_media_moved"
                self._write_restore_marker(self.data_dir, marker)

                os.replace(str(stage_database), str(live_database))
                marker["phase"] = "new_database_installed"
                self._write_restore_marker(self.data_dir, marker)

                os.replace(str(stage_media), str(live_media))
                marker["phase"] = "new_media_installed"
                self._write_restore_marker(self.data_dir, marker)

                restored_database = Database(live_database)
                self.database = restored_database
                marker_path.unlink()
                shutil.rmtree(str(recovery_dir), ignore_errors=True)
                shutil.rmtree(str(stage_dir), ignore_errors=True)
                return restored_database, safety_snapshot
            except Exception as exc:
                try:
                    if self.database is not None:
                        try:
                            self.database.close()
                        except Exception:
                            pass
                    self.recover_interrupted_restore(self.data_dir)
                    self.database = Database(live_database)
                except Exception as recovery_error:
                    raise BackupError(
                        "Restore failed and automatic rollback needs attention. "
                        "Keep the recovery folder and marker intact. Original error: {}. "
                        "Recovery error: {}.".format(exc, recovery_error)
                    ) from recovery_error
                raise BackupError(
                    "Restore failed. Your previous database and media were recovered. "
                    "A verified safety snapshot is also available at {}. Details: {}"
                    .format(safety_snapshot, exc)
                ) from exc
        except Exception:
            if stage_dir.exists():
                shutil.rmtree(str(stage_dir), ignore_errors=True)
            # If the transaction marker exists, leave recovery artifacts untouched:
            # the next launch must complete the deterministic rollback.
            marker_path = self.data_dir / ".muki-restore-in-progress.json"
            if not marker_path.exists() and recovery_dir.exists():
                shutil.rmtree(str(recovery_dir), ignore_errors=True)
            raise

    def delete_snapshot(self, snapshot_path: str | Path) -> None:
        """Delete one managed snapshot without allowing removal of the last valid automatic copy."""
        snapshot = Path(snapshot_path)
        if snapshot.is_symlink() or not snapshot.is_dir():
            raise BackupError("The selected backup is not a regular snapshot directory.")
        try:
            relative = snapshot.resolve().relative_to(self.backup_root.resolve())
        except (ValueError, OSError) as exc:
            raise BackupError("The selected folder is outside MUKI's backup library.") from exc
        if len(relative.parts) != 2 or relative.parts[0] not in ("automatic", "manual"):
            raise BackupError("Only a listed automatic or manual snapshot can be deleted.")

        if relative.parts[0] == "automatic":
            try:
                self.verify_snapshot(snapshot)
                selected_is_valid = True
            except BackupError:
                selected_is_valid = False
            if selected_is_valid:
                valid_others = 0
                for candidate in (self.backup_root / "automatic").iterdir():
                    if candidate.resolve() == snapshot.resolve() or not candidate.is_dir():
                        continue
                    try:
                        self.verify_snapshot(candidate)
                        valid_others += 1
                    except BackupError:
                        continue
                if valid_others == 0:
                    raise BackupError(
                        "This is the last verified automatic backup. Create another verified backup before deleting it."
                    )
        shutil.rmtree(str(snapshot))

    def _prune_automatic(self) -> None:
        category = self.backup_root / "automatic"
        candidates = sorted(
            (
                path for path in category.iterdir()
                if path.is_dir() and not path.name.startswith(".muki-backup-")
            ),
            key=lambda path: path.name,
            reverse=True,
        )
        # The newest snapshot was just verified and is always retained. Avoid
        # hashing all recent media snapshots on the Atom-class target machine;
        # verify only older candidates immediately before considering deletion.
        for old_path in candidates[self.retention:]:
            try:
                self.verify_snapshot(old_path)
            except BackupError:
                # Never delete an unverified directory automatically.
                continue
            shutil.rmtree(str(old_path))
