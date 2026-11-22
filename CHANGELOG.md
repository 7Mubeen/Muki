# Changelog

All notable MUKI changes are recorded here. This project uses a lightweight
version history; entries describe behavior reported as implemented and tested
where that information is available.

## Unreleased — v0.5.4

Planned foundation release:

- Add the GNU GPL version 3 or later license and project notices.
- Document the home-directory data layout.
- Design reliable automatic and manual backups.
- Add backup integrity verification and a safe restore workflow.
- Add portable backup export and import.
- Record the development journey and release testing process.

These are planned items, not claims that the backup implementation is already
available.

## v0.5.3 — Study layout and visual recall

- Made the study content area vertically scrollable while keeping answer and
  rating controls accessible in a fixed footer.
- Replaced text-symbol selection indicators with native Tkinter checkboxes.
- Added Anki image extraction and optional image hints.
- Added Image → Hanzi recall with a meaning → Pinyin fallback for cards without
  an associated image.
- Added a session-level image toggle and a three-presentation image hint limit.

## v0.5.2 — Adaptive, continuous practice

- Added separate practice history so practice ratings do not alter normal SRS
  scheduling.
- Added recency-weighted weakness prioritization and randomized practice rounds.
- Automatically continues into another round without a completion prompt.

## v0.5.1 — Selective study and Anki import improvements

- Added selected-card study.
- Improved compatibility with Anki packages containing `collection.anki21`.
- Added deck/card deletion and unlimited practice improvements from the
  preceding development cycle.

## v0.5.0 — Practice and deck management

- Added unlimited practice behavior.
- Added deck and card deletion.

## v0.4.0 — Working Anki import and audio

- User-tested Anki `.apkg` import.
- Added working deck audio playback and basic Mandarin study workflows.

Earlier experimental versions are not exhaustively documented here yet.
