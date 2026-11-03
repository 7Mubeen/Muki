import tempfile
import unittest
from pathlib import Path

from muki.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_empty_dashboard_uses_real_zero_counts(self):
        self.assertEqual(self.db.dashboard_stats(), {"decks": 0, "cards": 0, "due": 0, "reviews": 0})

    def test_create_and_list_deck(self):
        deck_id = self.db.create_deck("HSK 1")
        self.assertGreater(deck_id, 0)
        rows = self.db.list_decks()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "HSK 1")

    def test_empty_deck_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.create_deck("  ")


if __name__ == "__main__":
    unittest.main()
