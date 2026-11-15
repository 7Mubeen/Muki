import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from muki.anki.importer import AnkiImportError, _read_collection, import_apkg
from muki.database import Database


class AnkiPackageSelectionTests(unittest.TestCase):
    def test_prefers_new_collection_when_legacy_and_new_are_both_present(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "both.apkg"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("collection.anki2", b"legacy database")
                archive.writestr("collection.anki21", b"new database")
            with zipfile.ZipFile(package) as archive:
                selected = _read_collection(archive, Path(directory))
            self.assertEqual(selected.name, "collection.anki21")
            self.assertEqual(selected.read_bytes(), b"new database")

    def test_import_prefers_full_anki21_collection_and_maps_example_sentence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def make_collection(path, deck_name, words):
                connection = sqlite3.connect(path)
                model = {
                    "123": {
                        "name": "Chinese vocabulary",
                        "flds": [
                            {"name": "Chinese Word"},
                            {"name": "Chinese Example Sentence"},
                            {"name": "Pinyin"},
                            {"name": "English Translation"},
                        ],
                        "tmpls": [{
                            "qfmt": "{{Chinese Word}}<br>{{Chinese Example Sentence}}",
                            "afmt": "{{Chinese Word}}<hr>{{English Translation}}",
                        }],
                    }
                }
                decks = {"10": {"id": 10, "name": deck_name}}
                connection.execute("CREATE TABLE col (models TEXT, decks TEXT)")
                connection.execute(
                    "INSERT INTO col(models, decks) VALUES (?, ?)",
                    (json.dumps(model), json.dumps(decks)),
                )
                connection.execute(
                    "CREATE TABLE notes (id INTEGER, mid INTEGER, flds TEXT, tags TEXT)"
                )
                connection.execute(
                    "CREATE TABLE cards (id INTEGER, nid INTEGER, did INTEGER, ord INTEGER, "
                    "queue INTEGER, due INTEGER, ivl INTEGER, factor INTEGER, reps INTEGER, "
                    "lapses INTEGER, type INTEGER)"
                )
                for index, (word, sentence, pinyin, translation) in enumerate(words, 1):
                    note_id = index
                    connection.execute(
                        "INSERT INTO notes VALUES (?, ?, ?, ?)",
                        (note_id, 123, "\x1f".join((word, sentence, pinyin, translation)), "hsk1"),
                    )
                    connection.execute(
                        "INSERT INTO cards VALUES (?, ?, 10, 0, 0, 0, 0, 2500, 0, 0, 0)",
                        (note_id, note_id),
                    )
                connection.commit()
                connection.close()

            legacy = root / "legacy.sqlite"
            modern = root / "modern.sqlite"
            make_collection(legacy, "Old placeholder", [("placeholder", "", "", "")])
            make_collection(modern, "Chinese high frequency", [
                ("我", "我去商店。", "wǒ qù shāngdiàn", "I go to the store."),
                ("是", "这本书是我的。", "shì", "to be"),
            ])
            package = root / "sample.apkg"
            with zipfile.ZipFile(package, "w") as archive:
                archive.write(legacy, "collection.anki2")
                archive.write(modern, "collection.anki21")

            database = Database(root / "muki.sqlite3")
            try:
                result = import_apkg(package, database, root / "media")
                self.assertEqual(result["cards"], 2)
                self.assertEqual(result["notes"], 2)
                self.assertEqual(database.list_decks()[0]["name"], "Chinese high frequency")
                imported = database.list_cards(database.list_decks()[0]["id"])
                fields = json.loads(imported[0]["fields_json"])
                self.assertIn("sentence", fields)
                self.assertTrue(fields["sentence"])
                self.assertIn("sentence_translation", fields)
            finally:
                database.close()

    def test_reports_unsupported_anki21b_package(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "compressed.apkg"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("collection.anki21b", b"compressed")
            with zipfile.ZipFile(package) as archive:
                with self.assertRaisesRegex(AnkiImportError, "anki21b"):
                    _read_collection(archive, Path(directory))


if __name__ == "__main__":
    unittest.main()
