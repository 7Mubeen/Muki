# MUKI Architecture

## Product target
MUKI is an offline-first Mandarin SRS for constrained computers. The reference target is the ASUS Eee PC 1000H (Intel Atom N270, 2 GB RAM, i686 antiX). The supplied environment reports Python 3.13.5 and Tk 8.6.

## Technology decision
- UI: Python Tkinter/ttk. No webview, browser engine, animation framework, or mandatory third-party package.
- Persistence: SQLite through Python's built-in sqlite3.
- Domain logic: plain Python modules independent of Tkinter.
- Anki import: isolated importer. APKG is a ZIP container with a SQLite collection database and media mapping; full compatibility is not claimed until templates, scheduling, and media edge cases are tested against real decks.
- Audio: optional adapters around installed system players/recorders. Core review must work without audio utilities.
- Packaging: source execution on Linux first; evaluate Windows packaging after core stability.

## Module boundaries
- muki/__main__.py: application entry point
- muki/database.py: schema, migrations, transactions
- muki/repositories.py: persistence queries (to be extracted as the project grows)
- muki/scheduler.py: scheduling policy (next milestone)
- muki/anki/importer.py: APKG inspection/import (future milestone)
- muki/audio/backend.py: optional system audio adapters (future milestone)
- muki/ui/app.py: Tkinter screens

The UI calls application services/repositories; it must not own scheduling SQL or scheduling rules.

## Initial database model
- decks: deck identity, name, description, created/updated timestamps.
- notes: note type, fields JSON, tags JSON, owning deck, source/import metadata.
- cards: note reference, template ordinal, rendered front/back, due timestamp, interval, ease, repetitions, lapses, state.
- review_logs: card, review timestamp, rating, elapsed time, previous/next scheduling snapshots.
- media: stable media name, local relative path, checksum, MIME type.
- schema_version: ordered database migration version.

Use foreign keys, transactions, and indexes on due/deck. Use SQLite-consistent backups. WAL mode will be considered only after testing on the target filesystem.

## Anki compatibility strategy
1. Inspect APKG archives and validate their SQLite collection database.
2. Preserve the original package and extract media into an application-managed directory.
3. Map notes, decks, tags, templates, and card scheduling data explicitly.
4. Record unsupported features in an import report; never silently discard them.
5. Add fixtures from real decks before describing compatibility as supported.
6. Treat COLPKG separately because collection-level import and profile semantics are more complex.

## UI design constraints
The supplied Scholar Stone Precision design is the visual source of truth. Use indigo focus, jade retention, amber due-state, compact 4 px spacing, restrained 2–4 px radii, and crisp borders. The implementation must remain usable at 1024×600. Prefer system fonts; use WenQuanYi Micro Hei or Noto Sans CJK for Hanzi when available.

## Development phases
1. Foundation: application shell, SQLite schema, dashboard/deck navigation, empty states, tests.
2. Core SRS: card/note editing, review flow, scheduling policy, review history.
3. Anki APKG: inspect/import decks, templates, tags, media, validation report.
4. Mandarin workflow: pinyin/tone rendering, HSK tagging conventions, sentence/grammar cards.
5. Audio: optional playback/recording adapters and listening cards.
6. Reliability/performance: migrations, backup/restore, duplicate detection, measurements on i686.
7. Windows: isolate platform adapters and validate a Windows build.

## Risks and honest limitations
- Tkinter rendering and CJK font fallback vary across Tk/X11 installations.
- Python 3.13 and Tk 8.6 are confirmed on the supplied reference machine; other systems must check their versions.
- Full Anki template behavior, add-ons, filtered decks, scheduling parity, and COLPKG support are not assumed.
- Audio capture depends on installed tools and permissions.
- Performance targets must be measured on the actual Atom machine; no RAM/startup guarantees are claimed before measurement.
