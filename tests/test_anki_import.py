import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from muki.database import Database
from muki.anki.importer import AnkiImportError, import_apkg


class AnkiImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(self.root / "muki.sqlite3")
        self.media = self.root / "media"
        self.package = self.root / "sample.apkg"
        self._make_package()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def _make_package(self):
        collection = self.root / "collection.anki2"
        conn = sqlite3.connect(collection)
        conn.executescript("""
            CREATE TABLE col (models TEXT, decks TEXT);
            CREATE TABLE notes (id INTEGER, mid INTEGER, flds TEXT, tags TEXT);
            CREATE TABLE cards (
                id INTEGER, nid INTEGER, did INTEGER, ord INTEGER, queue INTEGER,
                due INTEGER, ivl INTEGER, factor INTEGER, reps INTEGER, lapses INTEGER, type INTEGER
            );
        """)
        models = {
            "10": {
                "name": "Basic",
                "flds": [{"name": "Hanzi"}, {"name": "Pinyin"}, {"name": "Meaning"}],
                "tmpls": [{"qfmt": "{{Hanzi}}", "afmt": "{{FrontSide}}<hr>{{Pinyin}}<br>{{Meaning}}"}]
            }
        }
        decks = {"20": {"name": "Mandarin::HSK 1"}}
        conn.execute("INSERT INTO col(models,decks) VALUES(?,?)",
                     (json.dumps(models), json.dumps(decks)))
        conn.execute("INSERT INTO notes(id,mid,flds,tags) VALUES(?,?,?,?)",
                     (100, 10, "买\x1fmǎi\x1fto buy [sound:mai.mp3]", " HSK1 beginner "))
        conn.execute("INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (200, 100, 20, 0, 2, 42, 3, 2500, 4, 0, 2))
        conn.commit()
        conn.close()
        with zipfile.ZipFile(self.package, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(collection, "collection.anki2")
            archive.writestr("media", json.dumps({"0": "mai.mp3"}))
            archive.writestr("0", b"fake-mp3-data")

    def test_imports_deck_note_card_tags_and_audio_media(self):
        result = import_apkg(self.package, self.db, self.media)
        self.assertEqual(result["decks"], 1)
        self.assertEqual(result["notes"], 1)
        self.assertEqual(result["cards"], 1)
        self.assertEqual(result["media"], 1)
        deck = self.db.list_decks()[0]
        self.assertEqual(deck["name"], "Mandarin::HSK 1")
        card = self.db.list_cards(deck["id"])[0]
        self.assertEqual(card["state"], "new")
        fields = json.loads(card["fields_json"])
        self.assertEqual(fields["hanzi"], "买")
        self.assertEqual(fields["pinyin"], "mǎi")
        self.assertEqual(fields["meaning"], "to buy")
        self.assertTrue(Path(fields["word_audio"]).is_file())
        self.assertIn("HSK1", fields["anki_tags"])

    def test_reimport_of_exact_same_package_is_skipped(self):
        first = import_apkg(self.package, self.db, self.media)
        second = import_apkg(self.package, self.db, self.media)
        self.assertEqual(first["cards"], 1)
        self.assertEqual(second["cards"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(self.db.dashboard_stats()["cards"], 1)

    def test_invalid_package_is_rejected(self):
        bad = self.root / "bad.apkg"
        bad.write_text("not a zip")
        with self.assertRaises(AnkiImportError):
            import_apkg(bad, self.db, self.media)


    def test_imported_card_can_be_edited_and_used_in_recall_modes(self):
        from muki.study import check_answer, prompt_for_mode

        result = import_apkg(self.package, self.db, self.media)
        self.assertEqual(result["cards"], 1)
        deck = self.db.list_decks()[0]
        card = self.db.list_cards(deck["id"])[0]
        fields = json.loads(card["fields_json"])
        self.assertEqual(fields["hanzi"], "买")
        self.assertEqual(fields["pinyin"], "mǎi")

        fields.update({"pinyin": "mǎi", "meaning": "to purchase", "notes": "verb"})
        self.db.update_card(card["id"], fields)
        edited = self.db.get_card(card["id"])
        saved = json.loads(edited["fields_json"])
        self.assertEqual(saved["meaning"], "to purchase")
        self.assertIn("HSK1", saved["anki_tags"])

        self.assertEqual(prompt_for_mode(saved, "hanzi_to_pinyin"), "mǎi")
        self.assertTrue(check_answer(saved, "hanzi_to_pinyin", "mai"))
        self.assertTrue(check_answer(saved, "pinyin_to_hanzi", "买"))
        self.assertTrue(check_answer(saved, "meaning_to_pinyin", "mai"))

        self.db.grade_card(card["id"], 3, elapsed_ms=850)
        self.assertEqual(self.db.get_card(card["id"])["state"], "review")
        self.assertEqual(self.db.dashboard_stats()["reviews"], 1)

if __name__ == "__main__":
    unittest.main()
