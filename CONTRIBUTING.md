# Contributing to MUKI

Thank you for considering a contribution.

MUKI is a lightweight, offline-first Mandarin spaced-repetition application.
Its reference environment is a 32-bit i686 antiX Linux machine with an Intel
Atom N270 and 2 GB RAM. Contributions should respect that constraint.

## Before changing code

1. Read the README and the relevant design notes under `docs/`.
2. Check existing issues and pull requests to avoid duplicating work.
3. Keep changes focused and explain the user problem they solve.
4. Preserve existing user data and backward compatibility wherever possible.

## Development principles

- Keep mandatory dependencies limited to the Python standard library,
  Tkinter, and SQLite unless a strong reason is documented.
- Keep audio and other optional integrations optional.
- Do not silently discard user data during migrations, imports, or restores.
- Prefer clear error messages and recoverable operations.
- Avoid claiming universal Anki compatibility.
- Test on supported Python versions and, when possible, on the low-resource
  reference machine.

## Tests

Run the test suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

Add regression tests for bug fixes. For backup and restore changes, tests must
cover valid backups, corrupted archives, missing media, interrupted writes,
and restoration into a separate temporary data directory.

## Pull requests

A useful pull request includes:

- The problem and expected behavior.
- A concise implementation summary.
- Tests run and their results.
- Any limitations or migration implications.
- Screenshots only when they materially help explain a UI change.

Keep pull requests focused. Do not merge a release-critical change until it
has been tested on the target hardware where practical.

## Licensing

By submitting a contribution, you agree that the contribution is offered
under the project's GNU GPL version 3 or later, unless a different license is
explicitly agreed to by the maintainers. Do not submit code, media, or other
materials that you do not have permission to contribute.
