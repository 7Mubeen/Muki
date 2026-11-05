"""SQLite persistence and lightweight review scheduling for MUKI."""
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    note_type TEXT NOT NULL DEFAULT 'basic',
    fields_json TEXT NOT NULL DEFAULT '{}',
    tags_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'muki',
    source_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    template_ordinal INTEGER NOT NULL DEFAULT 0,
    front TEXT NOT NULL DEFAULT '',
    back TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'new',
    due_at TEXT,
    interval_days REAL NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    repetitions INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(note_id, template_ordinal)
);
CREATE TABLE IF NOT EXISTS review_logs (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 4),
    elapsed_ms INTEGER NOT NULL DEFAULT 0,
    previous_state_json TEXT NOT NULL DEFAULT '{}',
    next_state_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY,
    media_name TEXT NOT NULL UNIQUE,
    relative_path TEXT NOT NULL,
    checksum TEXT,
    mime_type TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due_at);
CREATE INDEX IF NOT EXISTS idx_notes_deck ON notes(deck_id);
CREATE INDEX IF NOT EXISTS idx_review_logs_card_time ON review_logs(card_id, reviewed_at);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        row = self.connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row is None:
            self.connection.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
        elif row["version"] > SCHEMA_VERSION:
            self.connection.close()
            raise RuntimeError("Database was created by a newer MUKI version")
        elif row["version"] < SCHEMA_VERSION:
            self.connection.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        self.connection.commit()

    def dashboard_stats(self) -> dict[str, int]:
        conn = self.connection
        return {
            "decks": conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0],
            "cards": conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0],
            "due": conn.execute(
                "SELECT COUNT(*) FROM cards WHERE state != 'new' AND due_at <= ?",
                (datetime.now().isoformat(timespec="seconds"),)
            ).fetchone()[0],
            "reviews": conn.execute("SELECT COUNT(*) FROM review_logs").fetchone()[0],
        }

    def list_decks(self):
        return self.connection.execute(
            "SELECT d.id, d.name, COUNT(c.id) AS cards, "
            "SUM(CASE WHEN c.state != 'new' AND c.due_at <= ? THEN 1 ELSE 0 END) AS due "
            "FROM decks d LEFT JOIN notes n ON n.deck_id=d.id "
            "LEFT JOIN cards c ON c.note_id=n.id GROUP BY d.id ORDER BY d.name COLLATE NOCASE",
            (datetime.now().isoformat(timespec="seconds"),)
        ).fetchall()

    def get_deck(self, deck_id: int):
        return self.connection.execute("SELECT * FROM decks WHERE id=?", (deck_id,)).fetchone()

    def create_deck(self, name: str, description: str = "") -> int:
        name = name.strip()
        if not name:
            raise ValueError("Deck name cannot be empty")
        cursor = self.connection.execute(
            "INSERT INTO decks(name, description) VALUES (?, ?)", (name, description.strip())
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_card(self, deck_id: int, fields: dict) -> int:
        hanzi = fields.get("hanzi", "").strip()
        meaning = fields.get("meaning", "").strip()
        if not hanzi:
            raise ValueError("Chinese characters are required.")
        if not meaning:
            raise ValueError("Meaning is required.")
        saved = dict(fields)
        front = hanzi
        back = meaning
        if saved.get("pinyin"):
            back = saved["pinyin"].strip() + "\n" + back
        cursor = self.connection.execute(
            "INSERT INTO notes(deck_id, note_type, fields_json) VALUES (?, 'mandarin', ?)",
            (deck_id, json.dumps(saved, ensure_ascii=False))
        )
        note_id = cursor.lastrowid
        card = self.connection.execute(
            "INSERT INTO cards(note_id, front, back, state) VALUES (?, ?, ?, 'new')",
            (note_id, front, back)
        )
        self.connection.commit()
        return int(card.lastrowid)

    def update_card(self, card_id: int, fields: dict) -> None:
        row = self.connection.execute(
            "SELECT note_id FROM cards WHERE id=?", (card_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Card no longer exists.")
        hanzi = fields.get("hanzi", "").strip()
        meaning = fields.get("meaning", "").strip()
        if not hanzi or not meaning:
            raise ValueError("Chinese characters and meaning are required.")
        back = (fields.get("pinyin", "").strip() + "\n" if fields.get("pinyin", "").strip() else "") + meaning
        self.connection.execute(
            "UPDATE notes SET fields_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(fields, ensure_ascii=False), row["note_id"])
        )
        self.connection.execute("UPDATE cards SET front=?, back=? WHERE id=?", (hanzi, back, card_id))
        self.connection.commit()

    def get_card(self, card_id: int):
        return self.connection.execute(
            "SELECT c.*, n.deck_id, n.fields_json FROM cards c "
            "JOIN notes n ON n.id=c.note_id WHERE c.id=?", (card_id,)
        ).fetchone()

    def list_cards(self, deck_id: int):
        return self.connection.execute(
            "SELECT c.id, c.front, c.back, c.state, n.fields_json "
            "FROM cards c JOIN notes n ON n.id=c.note_id WHERE n.deck_id=? "
            "ORDER BY c.id DESC", (deck_id,)
        ).fetchall()

    def next_study_card(self, deck_id: int | None = None):
        now = datetime.now().isoformat(timespec="seconds")
        sql = (
            "SELECT c.*, n.deck_id, n.fields_json FROM cards c "
            "JOIN notes n ON n.id=c.note_id "
            "WHERE (c.state='new' OR (c.due_at IS NOT NULL AND c.due_at<=?))"
        )
        args = [now]
        if deck_id is not None:
            sql += " AND n.deck_id=?"
            args.append(deck_id)
        sql += " ORDER BY CASE WHEN c.state='new' THEN 0 ELSE 1 END, c.due_at, c.id LIMIT 1"
        return self.connection.execute(sql, args).fetchone()

    def grade_card(self, card_id: int, rating: int, elapsed_ms: int = 0) -> None:
        if rating not in (1, 2, 3, 4):
            raise ValueError("Rating must be between 1 and 4.")
        card = self.get_card(card_id)
        if card is None:
            raise ValueError("Card no longer exists.")
        previous = {key: card[key] for key in ("state", "due_at", "interval_days", "ease_factor", "repetitions", "lapses")}
        interval = float(card["interval_days"])
        ease = float(card["ease_factor"])
        reps = int(card["repetitions"])
        lapses = int(card["lapses"])
        if rating == 1:
            interval, reps, lapses = 10.0 / 1440.0, 0, lapses + 1
            state = "learning"
            ease = max(1.3, ease - 0.20)
        elif rating == 2:
            interval = max(1.0, interval * 1.2) if reps else 1.0
            reps += 1
            state = "review"
            ease = max(1.3, ease - 0.15)
        elif rating == 3:
            interval = 1.0 if reps == 0 else (3.0 if reps == 1 else interval * ease)
            reps += 1
            state = "review"
        else:
            interval = 4.0 if reps == 0 else max(4.0, interval * ease * 1.3)
            reps += 1
            state = "review"
            ease = min(3.0, ease + 0.10)
        due = (datetime.now() + timedelta(days=interval)).isoformat(timespec="seconds")
        next_state = {"state": state, "due_at": due, "interval_days": interval,
                      "ease_factor": round(ease, 2), "repetitions": reps, "lapses": lapses}
        self.connection.execute(
            "UPDATE cards SET state=?, due_at=?, interval_days=?, ease_factor=?, repetitions=?, lapses=? WHERE id=?",
            (state, due, interval, round(ease, 2), reps, lapses, card_id)
        )
        self.connection.execute(
            "INSERT INTO review_logs(card_id, rating, elapsed_ms, previous_state_json, next_state_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (card_id, rating, max(0, int(elapsed_ms)), json.dumps(previous), json.dumps(next_state))
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
