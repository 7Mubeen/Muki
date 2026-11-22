# The MUKI Development Journey

This document records why MUKI exists, how it has changed, what worked, what
failed, and what its development has taught us. It is a living project diary,
not a claim that every milestone was independently audited.

## Why MUKI began

MUKI began as a practical attempt to build a lightweight Mandarin spaced-
repetition tool for a constrained 32-bit Linux computer. A central motivation
was to have a usable study system on hardware where installing and running
the usual Anki desktop application was difficult.

The project follows a simple principle: a learner should be able to study
offline, keep their own data, and use the application without paying a
subscription or depending on a cloud service.

## Development principles

- Lightweight first: the reference machine has an Intel Atom N270, 2 GB RAM,
  and 32-bit antiX Linux.
- Offline-first: decks and media are stored locally.
- Data ownership: learning history and imported material belong to the user.
- Honest compatibility: support only the Anki package features that have
  actually been implemented and tested.
- Incremental development: make a small change, test it, then continue.
- Recovery matters: protecting a learner's data is a core feature, not an
  optional extra.

## Milestones

### Early prototypes — v0.1 to v0.3

The early work established the application structure and core Mandarin
flashcard workflow. The history of every prototype is not yet fully recorded;
future entries should add exact dates and commit references when verified.

### v0.4.0 — Anki import and audio

A working Anki `.apkg` import and deck audio playback were tested by the
developer. This made it possible to bring existing Mandarin learning material
into MUKI.

### v0.5.0 — Practice and deck management

Unlimited practice and deck/card deletion were introduced. The project began
separating ordinary scheduled reviews from unrestricted practice.

### v0.5.1 — Selective study and importer improvements

Selected-card study was added. An importer issue involving packages containing
both `collection.anki2` and `collection.anki21` was investigated; the
implementation was changed to prefer the newer collection database when both
are present.

### v0.5.2 — Adaptive practice

Practice history was separated from normal SRS scheduling. Practice sessions
began prioritizing weaker cards using recent results and randomized rounds.

### v0.5.3 — Study layout and visual recall

The study screen was adjusted for small displays, card selection moved to
native checkboxes, and optional image hints were added. Image → Hanzi mode
falls back to meaning → Pinyin when a card has no associated image.

### v0.5.4 — Protecting the learner's work (in progress)

The planned foundation release introduces an open-source license, a documented
home-directory data layout, automatic and manual backups, portable exports,
backup verification, and safe restoration. These features remain planned
until implemented and tested.

## Development log template

Append a dated entry for each meaningful milestone:

```markdown
### YYYY-MM-DD — Short title

**Goal:** What problem were we trying to solve?

**Approach:** What design or implementation was chosen?

**What happened:** What worked, what failed, and what changed?

**Testing:** Exact commands, hardware, OS, and results.

**Lessons:** What did this teach us?

**References:** Pull request, commit, issue, or relevant discussion.
```

## A note about the record

Where exact dates, commit identifiers, or test output have not been verified,
they are intentionally omitted. Add them from Git history and test records
rather than reconstructing them from memory.
