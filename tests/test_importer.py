import tempfile
import unittest
import zipfile
from pathlib import Path

from muki.anki.importer import AnkiImportError, _read_collection


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
