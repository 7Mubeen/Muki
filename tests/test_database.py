import tempfile
import unittest
from pathlib import Path
import json
import sqlite3

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

    def test_study_query_can_be_limited_to_selected_cards(self):
        deck_id = self.db.create_deck("HSK 1")
        first = self.db.create_card(deck_id, {"hanzi": "你好", "meaning": "hello"})
        second = self.db.create_card(deck_id, {"hanzi": "谢谢", "meaning": "thanks"})
        third = self.db.create_card(deck_id, {"hanzi": "再见", "meaning": "goodbye"})
        selected = self.db.next_study_card(
            deck_id, include_not_due=True, selected_card_ids=[second, third]
        )
        self.assertEqual(selected["id"], second)
        selected_next = self.db.next_study_card(
            deck_id, include_not_due=True, selected_card_ids=[third],
            exclude_card_ids={second}
        )
        self.assertEqual(selected_next["id"], third)
        self.assertIsNone(self.db.next_study_card(
            deck_id, include_not_due=True, selected_card_ids=[]
        ))
        self.assertEqual(self.db.next_study_card(deck_id, include_not_due=True)["id"], first)

    def test_practice_result_does_not_change_srs_state_or_review_history(self):
        deck_id = self.db.create_deck("HSK 1")
        card_id = self.db.create_card(deck_id, {"hanzi": "学习", "meaning": "to study"})
        before = self.db.get_card(card_id)
        for _ in range(10):
            self.db.record_practice_result(
                card_id, 1, elapsed_ms=900, mode="hanzi_to_pinyin"
            )
        after = self.db.get_card(card_id)
        for key in ("state", "due_at", "interval_days", "ease_factor", "repetitions", "lapses"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(self.db.dashboard_stats()["reviews"], 0)
        log = self.db.connection.execute(
            "SELECT rating, mode, elapsed_ms, mistakes FROM practice_logs WHERE card_id=?",
            (card_id,),
        ).fetchone()
        self.assertEqual(tuple(log), (1, "hanzi_to_pinyin", 900, 0))
        self.assertEqual(
            self.db.connection.execute(
                "SELECT COUNT(*) FROM practice_logs WHERE card_id=?", (card_id,)
            ).fetchone()[0],
            10,
        )

    def test_practice_priority_uses_errors_and_respects_selection(self):
        deck_id = self.db.create_deck("HSK 1")
        weak = self.db.create_card(deck_id, {"hanzi": "学习", "meaning": "study"})
        strong = self.db.create_card(deck_id, {"hanzi": "你好", "meaning": "hello"})
        unassessed = self.db.create_card(deck_id, {"hanzi": "再见", "meaning": "goodbye"})
        self.db.record_practice_result(weak, 1)
        self.db.record_practice_result(strong, 4)
        self.db.record_practice_result(unassessed, 3, mistakes=1)
        entries = self.db.practice_cards(deck_id)
        scores = {entry["card"]["id"]: entry["weakness_score"] for entry in entries}
        self.assertGreater(scores[weak], scores[unassessed])
        self.assertGreater(scores[unassessed], scores[strong])
        self.assertEqual(scores[unassessed], 2.5)
        selected = self.db.practice_cards(deck_id, selected_card_ids=[strong, weak])
        self.assertEqual({entry["card"]["id"] for entry in selected}, {strong, weak})

    def test_v1_database_migrates_practice_history_table(self):
        legacy_path = Path(self.temp.name) / "legacy.sqlite3"
        connection = sqlite3.connect(str(legacy_path))
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version(version) VALUES (1)")
        connection.commit()
        connection.close()
        migrated = Database(legacy_path)
        try:
            version = migrated.connection.execute(
                "SELECT version FROM schema_version LIMIT 1"
            ).fetchone()[0]
            self.assertEqual(version, 2)
            self.assertIsNotNone(migrated.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='practice_logs'"
            ).fetchone())
        finally:
            migrated.close()

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
