"""Small SQLite persistence foundation for MUKI."""
from pathlib import Path
import sqlite3

SCHEMA_VERSION = 1

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
            raise RuntimeError("Database was created by a newer MUKI version")
        self.connection.commit()

    def dashboard_stats(self) -> dict[str, int]:
        conn = self.connection
        return {
            "decks": conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0],
            "cards": conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0],
            "due": conn.execute(
                "SELECT COUNT(*) FROM cards WHERE state != 'new' AND (due_at IS NULL OR due_at <= CURRENT_TIMESTAMP)"
            ).fetchone()[0],
            "reviews": conn.execute("SELECT COUNT(*) FROM review_logs").fetchone()[0],
        }

    def list_decks(self):
        return self.connection.execute(
            "SELECT d.id, d.name, COUNT(c.id) AS cards, "
            "SUM(CASE WHEN c.state != 'new' AND (c.due_at IS NULL OR c.due_at <= CURRENT_TIMESTAMP) "
            "THEN 1 ELSE 0 END) AS due FROM decks d "
            "LEFT JOIN notes n ON n.deck_id=d.id LEFT JOIN cards c ON c.note_id=n.id "
            "GROUP BY d.id ORDER BY d.name COLLATE NOCASE"
        ).fetchall()

    def create_deck(self, name: str, description: str = "") -> int:
        name = name.strip()
        if not name:
            raise ValueError("Deck name cannot be empty")
        cursor = self.connection.execute(
            "INSERT INTO decks(name, description) VALUES (?, ?)", (name, description.strip())
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def close(self) -> None:
        self.connection.close()
