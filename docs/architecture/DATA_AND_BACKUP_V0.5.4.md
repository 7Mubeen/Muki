# MUKI v0.5.4 — Data and Backup Architecture

Status: implementation in progress. The development branch now includes local
snapshots, startup and pre-operation backups, a backup manager UI, portable
archive import/export, and staged restore with rollback recovery. Target-device
validation on 32-bit antiX is still required.

## 1. Goals

The v0.5.4 foundation release prioritizes protecting a learner's decks,
vocabulary, media, and review history.

The design must:

- Keep user data in the user's home directory by default.
- Preserve the current database location for existing installations.
- Back up automatically at application startup and before defined risky
  operations.
- Support manual backups.
- Verify backups before reporting success.
- Restore without overwriting the only usable copy of current data.
- Remain usable on 32-bit Linux and low-memory hardware.
- Avoid mandatory third-party Python dependencies.

## 2. Default data root

Use the existing Linux data location:

```text
$XDG_DATA_HOME/muki/
```

When `XDG_DATA_HOME` is unset, this resolves to:

```text
~/.local/share/muki/
```

Compatibility requirement: the existing database path remains
`~/.local/share/muki/muki.sqlite3` (or its XDG equivalent). Do not move it
into a new nested database directory in v0.5.4. Keeping the current path avoids
an unnecessary migration and reduces risk to existing users.

## 3. Proposed directory layout

```text
~/.local/share/muki/
├── muki.sqlite3
├── media/
│   └── ... existing imported and recorded media ...
├── backups/
│   ├── automatic/
│   │   └── <timestamp>/
│   │       ├── muki.sqlite3
│   │       ├── media/
│   │       └── manifest.json
│   └── manual/
│       └── <timestamp>/
│           ├── muki.sqlite3
│           ├── media/
│           └── manifest.json
├── exports/
│   └── ... portable .muki-backup archives ...
└── logs/
    └── ... diagnostic logs ...
```

Only create directories when needed. Do not create empty folders in the
repository as substitutes for runtime directories. The application creates
these folders under the user's data root.

The current media directory and any existing media paths must be discovered
from the code before implementation. Do not rename or relocate media as part
of the initial folder-creation step.

## 4. Backup types

### Automatic snapshots

Create a snapshot:

1. At application startup, after the database is opened successfully and
   before the user begins changing data.
2. Before operations classified as high-risk, such as destructive deck/card
   deletion, Anki import that changes the collection, schema migration, and
   restore.

Do not create a backup for every ordinary review rating. That would create
unnecessary disk writes on low-resource hardware.

Default retention proposal: keep the latest 7 automatic snapshots. Manual
snapshots are not automatically deleted. Retention must never delete the
only valid backup, and cleanup happens only after a newer backup has been
created and verified.

### Manual snapshots

Provide a user-invoked backup action. Manual backups remain until the user
explicitly deletes them.

### Portable archive

Provide a `.muki-backup` archive containing:

- The SQLite database snapshot.
- All media required by the database.
- A manifest with format version, MUKI version, creation time, database
  schema version, and file inventory.
- A SHA-256 checksum for every archived file.

The archive must not contain absolute paths, credentials, or unrelated files
from the user's home directory.

## 5. Consistent SQLite snapshots

Never copy the live SQLite database file with a plain filesystem copy while
the application may be writing to it.

Use Python's SQLite online backup API (`Connection.backup`) to create a
consistent database snapshot. The backup must be closed and checked before
being packaged or retained.

Run `PRAGMA integrity_check` against the snapshot. A successful result must
be exactly `ok`. Record failure details in the diagnostic log and do not
label a failed snapshot as successful.

## 6. Atomic creation

Create new snapshots in a temporary sibling directory on the same filesystem.
Copy the required media, write the manifest, and verify every file. Rename the
temporary directory to its final timestamped name only after all steps pass.

If creation fails, leave the previous snapshots untouched and remove only the
incomplete temporary output created by that attempt. Never overwrite an
existing snapshot with the same name.

## 7. Restore safety

Restore is a high-risk operation and must require explicit user confirmation.

Before restoring:

1. Inspect the archive or snapshot without extracting arbitrary paths.
2. Validate the manifest format and all checksums.
3. Reject absolute paths, parent-directory traversal, symlinks, and unexpected
   paths in an archive.
4. Check the database with SQLite integrity_check.
5. Show a preview of the MUKI version, backup time, deck/card counts where
   available, and media inventory.
6. Create and verify a safety snapshot of the current data.

Restore into a staging directory first. The application must close its active
database connection before replacing live files. Replace data using a
same-filesystem rename strategy where possible; if a safe replacement cannot
be completed, retain the current data and report the failure.

Never delete the current database or media before the replacement has been
validated. If the process is interrupted, the next launch must detect an
incomplete restore state and preserve recoverable copies rather than guessing
which files to delete.

## 8. Media integrity

The backup must include all media referenced by cards and notes, including
audio and images. Preserve relative paths and filenames. Detect missing
referenced files and report them in the backup manifest or verification
report; do not silently pretend they were backed up.

Avoid loading media contents into memory all at once. Stream file hashing and
archive operations to keep memory usage low.

## 9. User interface

The eventual backup manager should offer:

- Create manual backup.
- View automatic and manual backups.
- Verify a selected backup.
- Export a portable archive.
- Restore with a preview and explicit confirmation.
- Delete a selected backup with confirmation.
- Display clear success/failure messages and the backup location.

Keep the interface small and usable at 1024×600.

## 10. Portability and security

Use standard-library modules where possible: `sqlite3`, `zipfile`,
`hashlib`, `json`, `pathlib`, and `shutil`.

Do not execute files from a backup. Treat archive names and manifest content as
untrusted input. Do not restore configuration that changes executable paths.

A backup on the same disk is not protection against disk failure. Documentation
must encourage users to copy important portable backups to another device,
such as a USB drive.

## 11. Acceptance criteria

The implementation is not complete until tests demonstrate:

- Existing installations continue using their current database path.
- Startup backup is created when appropriate.
- A pre-operation backup exists before a destructive operation begins.
- Manual backup can be created and verified.
- A portable archive can be exported and imported.
- Database and media are restored together.
- Corrupt database, altered checksum, missing media, and malicious archive
  paths are rejected safely.
- An interrupted backup leaves prior valid backups intact.
- Restore creates a verified safety copy of the current data.
- Existing decks, cards, SRS review history, practice history, audio, and
  images survive a backup/restore round trip.
- Memory use remains reasonable on the reference 2 GB machine.

A green unit-test run alone is not sufficient: complete a restore test on the
target antiX installation before calling the release stable.
