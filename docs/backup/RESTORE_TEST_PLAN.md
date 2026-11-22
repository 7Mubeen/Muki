# Backup and Restore Test Plan

This checklist is for implementation and release validation of MUKI v0.5.4.
Do not mark a test passed until it has actually been run.

## Test data

Prepare a disposable MUKI data directory containing:

- At least two decks.
- Cards with Hanzi, Pinyin, meanings, and example fields.
- Cards with imported image media.
- Cards with word and sentence audio.
- Both normal SRS review history and adaptive-practice history.

Keep the real user data untouched. Use a separate temporary data root for
destructive and restore tests.

## Backup creation

- [ ] Create a manual snapshot.
- [ ] Confirm the SQLite snapshot passes `PRAGMA integrity_check`.
- [ ] Confirm all expected media files are present.
- [ ] Confirm manifest inventory and SHA-256 checksums match.
- [ ] Confirm a failed backup does not replace or delete an older valid backup.
- [ ] Confirm repeated backups do not overwrite existing snapshots.
- [ ] Confirm startup backup runs as specified.
- [ ] Confirm backup runs before each configured high-risk operation.

## Portable archive

- [ ] Export a `.muki-backup` archive.
- [ ] Inspect archive contents; confirm no absolute paths or unrelated home
      directory files are included.
- [ ] Import the archive into a separate temporary data root.
- [ ] Verify every checksum before restore.
- [ ] Reject a modified file with a checksum mismatch.
- [ ] Reject path traversal entries such as `../../outside-file`.
- [ ] Reject unsupported manifest versions with a clear message.

## Restore

- [ ] Preview a valid backup before confirmation.
- [ ] Confirm current data receives a safety backup before restore.
- [ ] Restore database and media together.
- [ ] Confirm deck/card counts and review histories match.
- [ ] Confirm audio and images still open from restored paths.
- [ ] Confirm an invalid backup leaves current data unchanged.
- [ ] Simulate an interrupted restore and confirm recoverable copies remain.

## Retention

- [ ] Create more automatic snapshots than the configured retention count.
- [ ] Confirm only older automatic snapshots are pruned.
- [ ] Confirm manual snapshots are never pruned automatically.
- [ ] Confirm the newest verified automatic snapshot is retained.

## Target hardware

- [ ] Run the full unit test suite on the development environment.
- [ ] Run the full unit test suite on 32-bit antiX where practical.
- [ ] Perform a full backup/restore round trip on the ASUS Eee PC 1000H.
- [ ] Observe startup time, backup duration, disk use, and peak memory.
- [ ] Confirm MUKI remains responsive during normal study after backup.

Record the date, MUKI commit, OS/Python version, test data size, and actual
results for every target-device test.
