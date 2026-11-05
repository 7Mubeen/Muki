import json
import tempfile
import unittest
from pathlib import Path

from muki.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.sqlite3")
        self.deck_id = self.db.create_deck("HSK 1")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_empty_dashboard_uses_real_zero_counts(self):
        self.assertEqual(self.db.dashboard_stats(), {"decks": 1, "cards": 0, "due": 0, "reviews": 0})

    def test_create_and_list_deck(self):
        rows = self.db.list_decks()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "HSK 1")

    def test_empty_deck_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.create_deck("  ")

    def test_create_mandarin_card_and_preserve_unicode_fields(self):
        card_id = self.db.create_card(self.deck_id, {
            "hanzi": "银行", "pinyin": "yínháng", "meaning": "bank",
            "sentence": "我去银行。", "sentence_pinyin": "Wǒ qù yínháng.",
            "word_audio": "/tmp/yinhang.mp3"
        })
        card = self.db.get_card(card_id)
        fields = json.loads(card["fields_json"])
        self.assertEqual(card["front"], "银行")
        self.assertEqual(fields["pinyin"], "yínháng")
        self.assertEqual(fields["sentence"], "我去银行。")
        self.assertEqual(fields["word_audio"], "/tmp/yinhang.mp3")

    def test_grade_card_updates_schedule_and_review_log(self):
        card_id = self.db.create_card(self.deck_id, {"hanzi": "你好", "meaning": "hello"})
        self.db.grade_card(card_id, 3, 1200)
        card = self.db.get_card(card_id)
        self.assertEqual(card["state"], "review")
        self.assertEqual(card["repetitions"], 1)
        self.assertIsNotNone(card["due_at"])
        self.assertEqual(self.db.dashboard_stats()["reviews"], 1)

    def test_invalid_rating_is_rejected(self):
        card_id = self.db.create_card(self.deck_id, {"hanzi": "好", "meaning": "good"})
        with self.assertRaises(ValueError):
            self.db.grade_card(card_id, 5)


if __name__ == "__main__":
    unittest.main()
