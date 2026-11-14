import tempfile
import unittest
from pathlib import Path
import json

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

    def test_create_mandarin_card_preserves_unicode_and_fields(self):
        deck_id = self.db.create_deck("HSK 1")
        card_id = self.db.create_card(deck_id, {
            "hanzi": "买", "pinyin": "mǎi", "meaning": "to buy",
            "notes": "Contrast with 卖 (mài), to sell."
        })
        card = self.db.get_card(card_id)
        fields = json.loads(card["fields_json"])
        self.assertEqual(card["front"], "买")
        self.assertEqual(fields["pinyin"], "mǎi")
        self.assertIn("卖", fields["notes"])

    def test_card_requires_hanzi_and_meaning(self):
        deck_id = self.db.create_deck("HSK 1")
        with self.assertRaises(ValueError):
            self.db.create_card(deck_id, {"hanzi": "", "meaning": "buy"})
        with self.assertRaises(ValueError):
            self.db.create_card(deck_id, {"hanzi": "买", "meaning": ""})

    def test_card_update_persists_audio_and_sentence_fields(self):
        deck_id = self.db.create_deck("HSK 1")
        card_id = self.db.create_card(deck_id, {"hanzi": "买", "meaning": "buy"})
        self.db.update_card(card_id, {
            "hanzi": "买", "pinyin": "mǎi", "meaning": "to buy",
            "word_audio": "/local/media/mai.wav", "sentence": "我买书。"
        })
        fields = json.loads(self.db.get_card(card_id)["fields_json"])
        self.assertEqual(fields["word_audio"], "/local/media/mai.wav")
        self.assertEqual(fields["sentence"], "我买书。")

    def test_delete_card_also_deletes_review_history(self):
        deck_id = self.db.create_deck("HSK 1")
        card_id = self.db.create_card(deck_id, {"hanzi": "你好", "meaning": "hello"})
        self.db.grade_card(card_id, 3)
        self.assertTrue(self.db.delete_card(card_id))
        self.assertIsNone(self.db.get_card(card_id))
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0], 0)
        self.assertEqual(self.db.dashboard_stats()["reviews"], 0)
        self.assertFalse(self.db.delete_card(card_id))

    def test_delete_deck_cascades_to_cards_and_review_history(self):
        deck_id = self.db.create_deck("Temporary")
        card_id = self.db.create_card(deck_id, {"hanzi": "你好", "meaning": "hello"})
        self.db.grade_card(card_id, 3)
        self.assertTrue(self.db.delete_deck(deck_id))
        self.assertIsNone(self.db.get_deck(deck_id))
        self.assertIsNone(self.db.get_card(card_id))
        self.assertEqual(self.db.dashboard_stats(), {"decks": 0, "cards": 0, "due": 0, "reviews": 0})
        self.assertFalse(self.db.delete_deck(deck_id))

    def test_practice_all_includes_cards_not_yet_due_and_can_exclude_seen(self):
        deck_id = self.db.create_deck("HSK 1")
        card_id = self.db.create_card(deck_id, {"hanzi": "你好", "meaning": "hello"})
        self.db.grade_card(card_id, 3)
        self.assertIsNone(self.db.next_study_card(deck_id))
        card = self.db.next_study_card(deck_id, include_not_due=True)
        self.assertEqual(card["id"], card_id)
        self.assertIsNone(self.db.next_study_card(
            deck_id, include_not_due=True, exclude_card_ids={card_id}
        ))

    def test_grade_card_writes_review_log_and_next_due(self):
        deck_id = self.db.create_deck("HSK 1")
        card_id = self.db.create_card(deck_id, {"hanzi": "买", "meaning": "buy"})
        self.db.grade_card(card_id, 3, elapsed_ms=1200)
        card = self.db.get_card(card_id)
        self.assertEqual(card["state"], "review")
        self.assertEqual(card["repetitions"], 1)
        self.assertIsNotNone(card["due_at"])
        self.assertEqual(self.db.dashboard_stats()["reviews"], 1)

    def test_invalid_grade_is_rejected(self):
        deck_id = self.db.create_deck("HSK 1")
        card_id = self.db.create_card(deck_id, {"hanzi": "卖", "meaning": "sell"})
        with self.assertRaises(ValueError):
            self.db.grade_card(card_id, 5)


if __name__ == "__main__":
    unittest.main()
