# Changelog

All notable MUKI changes are recorded here. Entries distinguish implemented
work from features that still require completion or target-device validation.

## Unreleased — v0.5.4 (in progress)

Implemented in the current development branch:

- Added a standard-library local snapshot engine using SQLite's online backup
  API, media copying, SHA-256 manifests, and integrity verification.
- Added automatic startup snapshots for existing databases.
- Added verified pre-operation snapshots before Anki imports and destructive
  deck/card deletion.
- Added retention of the latest seven verified automatic snapshots by default;
  manual snapshots are not automatically pruned.
- Added a backup screen for creating manual snapshots and verifying a selected backup.

Still to implement and validate:

- Add portable .muki-backup export and safe import.
- Add restore preview, safety snapshot, staged replacement, and recovery.
- Complete unit and target-device restore testing on 32-bit antiX.
- Record the development journey and release test results.

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
- Improved compatibility with Anki packages containing collection.anki21.
- Added deck/card deletion and unlimited practice improvements from the
  preceding development cycle.

## v0.5.0 — Practice and deck management

- Added unlimited practice behavior.
- Added deck and card deletion.

## v0.4.0 — Working Anki import and audio

- User-tested Anki .apkg import.
- Added working deck audio playback and basic Mandarin study workflows.

Earlier experimental versions are not exhaustively documented here yet.
