import json
import tempfile
import unittest
from pathlib import Path

from muki.backup import BackupError, BackupManager
from muki.database import Database


class BackupManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = Database(self.root / "muki.sqlite3")
        self.media = self.root / "media"
        self.media.mkdir()
        self.audio = self.media / "mai.wav"
        self.audio.write_bytes(b"example-audio-data")
        deck_id = self.database.create_deck("HSK 1")
        self.card_id = self.database.create_card(deck_id, {
            "hanzi": "买",
            "pinyin": "mǎi",
            "meaning": "to buy",
            "word_audio": str(self.audio),
        })
        self.database.grade_card(self.card_id, 3)
        self.database.record_practice_result(self.card_id, 2, mistakes=1)
        self.manager = BackupManager(
            self.database, media_dir=self.media,
            backup_root=self.root / "backups", retention=2,
        )

    def tearDown(self):
        self.database.close()
        self.temp.cleanup()

    def test_manual_snapshot_contains_database_media_and_verified_manifest(self):
        snapshot = self.manager.create_snapshot("manual")
        manifest = self.manager.verify_snapshot(snapshot)
        self.assertEqual(manifest["backup_type"], "manual")
        self.assertEqual(manifest["database_stats"]["decks"], 1)
        self.assertEqual(manifest["database_stats"]["cards"], 1)
        self.assertEqual(manifest["database_stats"]["reviews"], 1)
        self.assertEqual(manifest["database_stats"]["practice_reviews"], 1)
        self.assertEqual((snapshot / "media" / "mai.wav").read_bytes(), b"example-audio-data")
        self.assertEqual({entry["path"] for entry in manifest["files"]},
                         {"muki.sqlite3", "media/mai.wav"})

    def test_checksum_mismatch_is_rejected(self):
        snapshot = self.manager.create_snapshot("manual")
        with (snapshot / "media" / "mai.wav").open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaises(BackupError):
            self.manager.verify_snapshot(snapshot)

    def test_missing_referenced_media_is_reported(self):
        self.audio.unlink()
        snapshot = self.manager.create_snapshot("manual")
        manifest = self.manager.verify_snapshot(snapshot)
        self.assertEqual(manifest["missing_media"], ["mai.wav"])

    def test_automatic_retention_keeps_latest_verified_snapshots(self):
        snapshots = [
            self.manager.create_snapshot("automatic")
            for _ in range(4)
        ]
        remaining = sorted((self.root / "backups" / "automatic").iterdir())
        self.assertEqual(len(remaining), 2)
        self.assertTrue(snapshots[-1].exists())
        self.assertTrue(snapshots[-2].exists())
        self.assertFalse(snapshots[0].exists())
        self.assertFalse(snapshots[1].exists())

    def test_restore_replaces_database_and_media_with_safety_snapshot(self):
        snapshot = self.manager.create_snapshot("manual")
        temporary_deck = self.database.create_deck("Temporary after backup")
        self.database.create_card(temporary_deck, {
            "hanzi": "新", "meaning": "new"
        })
        self.audio.write_bytes(b"changed-after-backup")

        restored, safety_snapshot = self.manager.restore_snapshot(snapshot)
        self.database = restored
        self.assertEqual(self.database.dashboard_stats()["decks"], 1)
        self.assertEqual(self.database.dashboard_stats()["cards"], 1)
        self.assertEqual(self.audio.read_bytes(), b"example-audio-data")
        restored_card = self.database.get_card(self.card_id)
        fields = json.loads(restored_card["fields_json"])
        self.assertEqual(fields["word_audio"], str(self.audio))
        self.assertTrue(Path(fields["word_audio"]).is_file())
        safety_manifest = self.manager.verify_snapshot(safety_snapshot)
        self.assertEqual(safety_manifest["database_stats"]["decks"], 2)

    def test_interrupted_restore_recovers_previous_database_and_media(self):
        import os

        recovery = self.root / "backups" / "restore-recovery" / "interrupted-test"
        recovery.mkdir(parents=True)
        stage_name = ".muki-restore-stage-interrupted"
        (self.root / stage_name).mkdir()
        self.database.close()
        os.replace(str(self.root / "muki.sqlite3"), str(recovery / "muki.sqlite3"))
        os.replace(str(self.media), str(recovery / "media"))

        replacement = Database(self.root / "muki.sqlite3")
        replacement.create_deck("Unfinished replacement")
        replacement.close()
        (self.root / "media").mkdir()
        (self.root / "media" / "wrong.wav").write_bytes(b"replacement")
        marker = {
            "format_version": 1,
            "phase": "new_media_installed",
            "recovery_dir": "backups/restore-recovery/interrupted-test",
            "stage_dir": stage_name,
            "had_media": True,
        }
        BackupManager._write_restore_marker(self.root, marker)

        self.assertTrue(BackupManager.recover_interrupted_restore(self.root))
        recovered = Database(self.root / "muki.sqlite3")
        try:
            self.assertEqual(recovered.dashboard_stats()["decks"], 1)
            self.assertTrue((self.root / "media" / "mai.wav").is_file())
            self.assertFalse((self.root / "media" / "wrong.wav").exists())
        finally:
            recovered.close()
        self.database = Database(self.root / "muki.sqlite3")
        self.manager.database = self.database

    def test_manual_snapshot_can_be_deleted(self):
        snapshot = self.manager.create_snapshot("manual")
        self.manager.delete_snapshot(snapshot)
        self.assertFalse(snapshot.exists())

    def test_last_verified_automatic_snapshot_cannot_be_deleted(self):
        snapshot = self.manager.create_snapshot("automatic")
        with self.assertRaises(BackupError):
            self.manager.delete_snapshot(snapshot)
        self.assertTrue(snapshot.exists())

    def test_older_automatic_snapshot_can_be_deleted_when_another_valid_copy_exists(self):
        first = self.manager.create_snapshot("automatic")
        second = self.manager.create_snapshot("automatic")
        self.manager.delete_snapshot(first)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())

    def test_portable_archive_round_trip(self):
        snapshot = self.manager.create_snapshot("manual")
        archive = self.root / "portable.muki-backup"
        self.manager.export_archive(snapshot, archive)
        imported = self.manager.import_archive(archive)
        manifest = self.manager.verify_snapshot(imported)
        self.assertEqual(manifest["backup_type"], "manual")
        self.assertEqual(manifest["database_stats"]["cards"], 1)
        self.assertEqual((imported / "media" / "mai.wav").read_bytes(), b"example-audio-data")
        self.assertEqual(manifest["imported_from"], archive.name)

    def test_portable_archive_rejects_path_traversal(self):
        snapshot = self.manager.create_snapshot("manual")
        manifest = self.manager.verify_snapshot(snapshot)
        archive = self.root / "malicious.muki-backup"
        import zipfile
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("manifest.json", json.dumps(manifest))
            package.write(snapshot / "muki.sqlite3", "muki.sqlite3")
            package.writestr("../../outside.txt", "not allowed")
        with self.assertRaises(BackupError):
            self.manager.import_archive(archive)
        self.assertFalse((self.root.parent / "outside.txt").exists())

    def test_failed_creation_does_not_replace_existing_snapshot(self):
        existing = self.manager.create_snapshot("manual")
        original = (existing / "manifest.json").read_bytes()
        bad_manager = BackupManager(
            self.database, media_dir=self.root / "missing-media-file",
            backup_root=self.root / "other-backups",
        )
        bad_manager.media_dir.mkdir()
        link = bad_manager.media_dir / "unsafe-link"
        try:
            link.symlink_to(self.audio)
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links are unavailable on this platform.")
        with self.assertRaises(BackupError):
            bad_manager.create_snapshot("manual")
        self.assertEqual((existing / "manifest.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
