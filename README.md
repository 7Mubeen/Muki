# MUKI

**MUKI** is a lightweight, offline-first spaced-repetition application focused on Mandarin Chinese. It is being designed for constrained hardware, with a 32-bit i686 antiX Linux / Intel Atom N270 / 2 GB RAM machine as the reference target.

## Current status

**Foundation milestone — early development.** The current branch contains a native Tkinter desktop shell, SQLite database foundation, live database-backed dashboard counts, deck creation/listing, and initial unit tests. Card editing, review scheduling, Anki importing, and audio are not implemented yet.

## Requirements
- Python 3.10+ (the reference machine reports Python 3.13.5)
- Tkinter 8.6 (available on the reference machine)
- SQLite (Python standard library)

No third-party Python packages are required for the foundation.

## Run

    python3 -m muki

On Debian/antiX, if Tkinter is missing, install the distribution's matching python3-tk package.

Run tests:

    python3 -m unittest discover -s tests -v

The database is created at $XDG_DATA_HOME/muki/muki.sqlite3, or ~/.local/share/muki/muki.sqlite3 when XDG_DATA_HOME is unset.

## Design
The UI follows the supplied **Scholar Stone Precision** design reference: compact 1024×600 layout, indigo focus, jade retention, amber due state, crisp borders, keyboard-first interaction, and CJK font fallbacks. See DESIGN.md and docs/ARCHITECTURE.md.

## Compatibility promises
MUKI does not yet claim Anki APKG/COLPKG compatibility or FSRS parity. These will be implemented and tested against real decks before being described as supported. Audio is planned as an optional subsystem; the core application will remain usable without it.

## Roadmap
1. Foundation: desktop shell, SQLite schema, deck navigation.
2. Core SRS: note/card editor, scheduler, study flow, review history.
3. Anki APKG import and validation report.
4. Mandarin-focused card rendering, pinyin and tones, HSK tagging.
5. Optional audio playback and recording.
6. Backups, migrations, reliability and i686 performance testing.
7. Windows portability.

See docs/ARCHITECTURE.md for architecture and known risks.
