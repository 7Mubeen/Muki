"""Conservative Anki APKG importer for MUKI.

Supports common SQLite-backed .apkg archives (collection.anki2 and
collection.anki21). This is a data importer, not a complete Anki renderer.
"""
from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


class AnkiImportError(Exception):
    """Raised when an APKG package cannot be safely imported."""


def _safe_name(name: str) -> str:
    # Do not allow archive paths to escape the managed media directory.
    cleaned = PurePosixPath(str(name).replace("\\", "/")).name
    return cleaned if cleaned not in ("", ".", "..") else "unnamed"


def _plain(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", value or "")
    value = re.sub(r"(?i)<br\\s*/?>|</(div|p|li|tr|h[1-6])>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"[ \\t\\xa0]+", " ", value).strip()


def _render(template: str, fields: dict[str, str], front: str = "") -> str:
    """Render basic {{Field}} and {{FrontSide}} substitutions only."""
    rendered = template or ""
    rendered = rendered.replace("{{FrontSide}}", front)
    rendered = re.sub(r"{{[#/^][^}]+}}", "", rendered)  # conditional sections unsupported
    rendered = re.sub(r"{{(?:type:)?([^{}]+)}}",
                      lambda m: fields.get(m.group(1).strip(), ""), rendered)
    return _plain(rendered)


def _read_collection(archive: zipfile.ZipFile, temp_dir: Path) -> Path:
    names = set(archive.namelist())
    candidates = ("collection.anki2", "collection.anki21")
    for candidate in candidates:
        if candidate in names:
            target = temp_dir / candidate
            with archive.open(candidate) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            return target
    if "collection.anki21b" in names:
        raise AnkiImportError(
            "This package uses collection.anki21b compression, which this MUKI build "
            "does not yet decode. Export it from Anki as a regular .apkg and retry."
        )
    raise AnkiImportError("No supported collection.anki2 or collection.anki21 database was found.")


def _load_media(archive: zipfile.ZipFile, media_dir: Path) -> tuple[dict[str, str], int]:
    names = set(archive.namelist())
    if "media" not in names:
        return {}, 0
    try:
        mapping = json.loads(archive.read("media").decode("utf-8"))
    except Exception as exc:
        raise AnkiImportError("The APKG media index is invalid.") from exc
    result: dict[str, str] = {}
    extracted = 0
    for index, original_name in mapping.items():
        archive_name = str(index)
        if archive_name not in names:
            continue
        safe = _safe_name(original_name)
        target = media_dir / safe
        if target.exists():
            stem, suffix = target.stem, target.suffix
            number = 2
            while target.exists():
                target = media_dir / f"{stem}_{number}{suffix}"
                number += 1
        media_dir.mkdir(parents=True, exist_ok=True)
        with archive.open(archive_name) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        result[str(original_name)] = str(target)
        extracted += 1
    return result, extracted


def import_apkg(package_path: str | Path, database, media_dir: str | Path) -> dict:
    """Import notes/cards/media from a common APKG into the MUKI database."""
    package_path = Path(package_path)
    if not package_path.is_file():
        raise AnkiImportError("The selected APKG file does not exist.")
    if package_path.suffix.lower() != ".apkg":
        raise AnkiImportError("Choose an Anki .apkg package.")
    digest = hashlib.sha256()
    with package_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    package_id = digest.hexdigest()
    source = "anki:" + package_id
    conn = database.connection
    duplicate = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE source=?", (source,)
    ).fetchone()[0]
    if duplicate:
        return {"decks": 0, "notes": 0, "cards": 0, "media": 0,
                "duplicates": duplicate, "warnings": ["This exact APKG was already imported."]}

    media_dir = Path(media_dir)
    warnings: list[str] = []
    counts = {"decks": 0, "notes": 0, "cards": 0, "media": 0, "duplicates": 0}
    with tempfile.TemporaryDirectory(prefix="muki-apkg-") as temp:
        temp_dir = Path(temp)
        try:
            archive = zipfile.ZipFile(package_path, "r")
        except zipfile.BadZipFile as exc:
            raise AnkiImportError("This file is not a valid ZIP-based APKG package.") from exc
        with archive:
            collection_path = _read_collection(archive, temp_dir)
            media_map, counts["media"] = _load_media(archive, media_dir)
        try:
            source_db = sqlite3.connect(str(collection_path))
            source_db.row_factory = sqlite3.Row
            col = source_db.execute("SELECT models, decks FROM col LIMIT 1").fetchone()
            if col is None:
                raise AnkiImportError("The Anki collection metadata is missing.")
            models = json.loads(col["models"] or "{}")
            source_decks = json.loads(col["decks"] or "{}")
            notes = source_db.execute("SELECT * FROM notes ORDER BY id").fetchall()
            cards = source_db.execute("SELECT * FROM cards ORDER BY id").fetchall()
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise AnkiImportError("The Anki collection database could not be read.") from exc
        finally:
            try:
                source_db.close()
            except Exception:
                pass

        cards_by_note: dict[int, list] = {}
        for card in cards:
            cards_by_note.setdefault(int(card["nid"]), []).append(card)

        deck_map: dict[int, int] = {}
        note_map: dict[tuple[int, int], int] = {}
        now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
        conn.execute("BEGIN")
        try:
            # Create only decks that actually contain cards.
            used_deck_ids = sorted({int(card["did"]) for card in cards})
            for anki_deck_id in used_deck_ids:
                deck_info = source_decks.get(str(anki_deck_id), {})
                original_name = str(deck_info.get("name") or f"Imported deck {anki_deck_id}")
                name = original_name
                suffix = 2
                while conn.execute("SELECT 1 FROM decks WHERE name=? COLLATE NOCASE", (name,)).fetchone():
                    name = f"{original_name} (Anki {suffix})"
                    suffix += 1
                cursor = conn.execute(
                    "INSERT INTO decks(name, description) VALUES (?, ?)",
                    (name, f"Imported from Anki APKG: {package_path.name}")
                )
                deck_map[anki_deck_id] = int(cursor.lastrowid)
                counts["decks"] += 1

            for note in notes:
                note_id = int(note["id"])
                note_cards = cards_by_note.get(note_id, [])
                if not note_cards:
                    continue
                model = models.get(str(note["mid"]), {})
                model_fields = model.get("flds", [])
                field_values = str(note["flds"] or "").split("\x1f")
                fields = {}
                for index, field_def in enumerate(model_fields):
                    field_name = str(field_def.get("name") or f"Field{index + 1}")
                    fields[field_name] = field_values[index] if index < len(field_values) else ""
                if not fields:
                    fields = {f"Field{i + 1}": value for i, value in enumerate(field_values)}
                tags = str(note["tags"] or "").split()
                for card in note_cards:
                    anki_deck_id = int(card["did"])
                    local_deck_id = deck_map[anki_deck_id]
                    key = (note_id, anki_deck_id)
                    if key not in note_map:
                        enriched = {
                            "hanzi": _plain(next((v for k, v in fields.items()
                                                  if any(x in k.lower() for x in ("hanzi", "simplified", "word", "front")) and _plain(v)), "")),
                            "pinyin": _plain(next((v for k, v in fields.items() if "pinyin" in k.lower()), "")),
                            "meaning": _plain(next((v for k, v in fields.items()
                                                    if any(x in k.lower() for x in ("meaning", "definition", "translation", "back")) and _plain(v)), "")),
                            "anki_fields": fields,
                            "anki_model": model.get("name", "Unknown note type"),
                            "anki_note_id": note_id,
                            "anki_tags": tags,
                        }
                        if not enriched["hanzi"]:
                            enriched["hanzi"] = _plain(next(iter(fields.values()), ""))
                        media_refs = set()
                        for value in fields.values():
                            media_refs.update(re.findall(r"\\[sound:([^\\]]+)\\]", value, flags=re.I))
                            media_refs.update(re.findall(r"""<img[^>]+src=["']([^"']+)["']""", value, flags=re.I))
                        local_refs = [media_map[name] for name in media_refs if name in media_map]
                        enriched["anki_media"] = local_refs
                        audio_refs = [media_map[name] for name in media_refs
                                      if name in media_map and Path(name).suffix.lower() in
                                      (".mp3", ".wav", ".ogg", ".flac", ".m4a")]
                        if audio_refs:
                            enriched["word_audio"] = audio_refs[0]
                        note_cursor = conn.execute(
                            "INSERT INTO notes(deck_id,note_type,fields_json,tags_json,source,source_id) "
                            "VALUES(?,?,?,?,?,?)",
                            (local_deck_id, "anki", json.dumps(enriched, ensure_ascii=False),
                             json.dumps(tags, ensure_ascii=False), source, f"{note_id}:{anki_deck_id}")
                        )
                        note_map[key] = int(note_cursor.lastrowid)
                        counts["notes"] += 1

                    note_local_id = note_map[key]
                    ordinal = int(card["ord"])
                    if conn.execute("SELECT 1 FROM cards WHERE note_id=? AND template_ordinal=?",
                                    (note_local_id, ordinal)).fetchone():
                        counts["duplicates"] += 1
                        continue
                    template_list = model.get("tmpls", [])
                    template = template_list[ordinal] if ordinal < len(template_list) else {}
                    front_html = _render(template.get("qfmt", ""), fields)
                    back_html = _render(template.get("afmt", ""), fields, front=front_html)
                    front = front_html or _plain(next(iter(fields.values()), ""))
                    back = back_html or _plain(" ".join(fields.values()))
                    queue = int(card["queue"])
                    state = "new" if queue == 0 else ("learning" if queue in (1, 3) else "review")
                    due_value = None
                    # Anki due is scheduler-specific (day number or learning timestamp);
                    # preserve original values in note metadata instead of guessing dates.
                    enriched = json.loads(conn.execute(
                        "SELECT fields_json FROM notes WHERE id=?", (note_local_id,)
                    ).fetchone()[0])
                    enriched.setdefault("anki_card_data", []).append({
                        "card_id": int(card["id"]), "due": int(card["due"]),
                        "interval": int(card["ivl"]), "factor": int(card["factor"]),
                        "reps": int(card["reps"]), "lapses": int(card["lapses"]),
                        "queue": queue, "type": int(card["type"])
                    })
                    conn.execute("UPDATE notes SET fields_json=? WHERE id=?",
                                 (json.dumps(enriched, ensure_ascii=False), note_local_id))
                    conn.execute(
                        "INSERT INTO cards(note_id,template_ordinal,front,back,state,due_at,interval_days,"
                        "ease_factor,repetitions,lapses) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (note_local_id, ordinal, front, back, state, due_value,
                         max(0, float(card["ivl"])), max(1.3, float(card["factor"]) / 1000.0),
                         max(0, int(card["reps"])), max(0, int(card["lapses"])))
                    )
                    counts["cards"] += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # Register extracted media so later MUKI tools can manage it.
    for original, local_path in media_map.items():
        path = Path(local_path)
        mime = mimetypes.guess_type(path.name)[0]
        conn.execute(
            "INSERT OR IGNORE INTO media(media_name,relative_path,checksum,mime_type) VALUES(?,?,?,?)",
            (original, str(path), None, mime)
        )
    conn.commit()
    if counts["media"]:
        warnings.append("Media was extracted locally. Image display in card templates is not yet implemented.")
    warnings.append("Anki scheduling due dates are not transferred yet; imported cards are available as new/review material.")
    warnings.append("Complex templates, cloze logic, CSS, JavaScript, and add-ons are not fully rendered.")
    return {**counts, "warnings": warnings}
