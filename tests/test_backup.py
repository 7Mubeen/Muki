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
