# MUKI

**MUKI** is a lightweight, offline-first spaced-repetition application focused on Mandarin Chinese. It is designed for constrained hardware, with a 32-bit i686 antiX Linux / Intel Atom N270 / 2 GB RAM machine as the reference target.

## Current status

**Current main version: v0.5.3 — study layout, selective card controls, and visual recall.** Practice mode shuffles each round, weights weaker cards earlier using practice-only review history, automatically continues into the next round, and never changes normal SRS scheduling. Normal SRS grading and due-date behaviour remain separate.

## Requirements

- Python 3.10+
- Tkinter
- SQLite (Python standard library)
- Optional audio playback: mpv (preferred) or ffplay
- Optional microphone recording: arecord from alsa-utils (preferred) or ffmpeg with ALSA support

The app has no mandatory third-party Python packages. Without audio tools, card creation and review remain usable.

## Run

    python3 -m muki

On Debian/antiX, if Tkinter is missing, install the distribution's matching python3-tk package.

Optional audio tools:

    sudo apt install mpv alsa-utils

Check that your microphone is detected with:

    arecord -l

Run tests:

    python3 -m unittest discover -s tests -v

The database is created at $XDG_DATA_HOME/muki/muki.sqlite3, or ~/.local/share/muki/muki.sqlite3 when XDG_DATA_HOME is unset. Audio selected or recorded in the editor is copied into the application's local media directory.

## Import an Anki deck

1. Open **Deck library**.
2. Select **Import Anki .apkg**.
3. Choose an APKG file from your computer or connected storage.
4. Review the import report. MUKI creates imported decks with their Anki names, stores original note fields and tags, creates cards, and extracts media into the local MUKI media folder.
5. Open an imported deck to study its cards.

The importer supports ZIP-based `.apkg` packages and compatible `.oapkg` archives containing `collection.anki2` or `collection.anki21`. If both collection databases are present, MUKI prefers `collection.anki21` because the legacy `collection.anki2` may be an incomplete compatibility snapshot. It detects an exact repeat of the same package and skips it. If a deck name already exists, the imported deck receives an "(Anki 2)"-style suffix rather than overwriting your deck.

Important limitations: this is a data importer, not a full Anki runtime. `.anki21b` compressed collections are not yet decoded. Complex templates, cloze behavior, CSS/JavaScript, add-ons, and filtered decks are not reproduced. An `.oapkg` file is accepted only when it uses the supported ZIP collection layout; this is not a promise of universal OAPKG compatibility. Anki scheduling values are retained as metadata, but imported cards enter MUKI as new cards; due dates are not converted. Images referenced directly by note fields are extracted and associated with their note; the study screen displays the first associated image as an optional hint. Images referenced only by CSS or complex card templates may not be detected. Audio media is extracted and the first recognized sound file is attached as word audio where possible. The experimental .anki21b format is not supported in this version.

## Add your first Mandarin card

1. Open **Deck library**.
2. Double-click a deck, or create one first.
3. Select **+ Add card**.
4. Enter Hanzi, pinyin (tone marks recommended but optional), and meaning. Add an example sentence, sentence pinyin, translation, and usage/homophone notes if useful.
5. Choose existing audio files or record a six-second word/sentence clip.
6. Save. Double-click a card or select it and press **Edit selected** to edit it.
7. Open **Study session** from that deck. Reveal the answer and grade Again, Hard, Good, or Easy (keys 1–4).

Audio formats depend on the installed system player. MP3, WAV, OGG, FLAC and M4A are offered in the file picker; the installed backend determines which formats actually play. WAV recording uses arecord or ffmpeg/ALSA.


## Active recall modes (v0.4)

Open a deck and choose **Study / recall modes**. Select the direction you want to practise:

- **Hanzi → Pinyin:** see the Chinese word and type its pronunciation.
- **Pinyin → Hanzi:** see tone-marked pinyin and type the Chinese characters.
- **Meaning → Pinyin:** see the translation and retrieve the pronunciation.
- **Audio → Hanzi:** listen to the attached word recording and type the word.
- **Image → Hanzi:** view an attached image and type the associated Chinese word. If a card has no associated image, MUKI automatically shows its meaning and asks you to type the pinyin instead.

Pinyin answer checking ignores tone marks and tone numbers, so `nǐ hǎo`, `ni hao`, and `ni3 hao3` are accepted as equivalent. It retains syllable boundaries and the ü distinction. The stored/displayed pinyin is not rewritten: add tone marks to the card when you know them, but you do not need to type them during a quiz.

Answers are entered directly in the MUKI window. Chinese characters can be composed through a running Fcitx5 input method; on Linux, MUKI sets Tk's XIM modifier to `@im=fcitx` if the desktop has not already set one. Start Fcitx5 in your desktop session and ensure its Pinyin addon is enabled. This does not install or configure Fcitx5 itself.



## Selective study sessions (v0.5.1)

Open a deck and tick the checkbox beside each card you want to study. Use **Select all** or **Deselect all** for bulk selection; the selected count updates immediately. Choose **Study selected** to restrict the session to those cards in both SRS and all-cards practice scopes. Choose **Study all** to return to the whole-deck session. Selection is temporary; it does not move or delete cards.

## Optional study images (v0.5.3 development)

Anki images referenced directly from note fields are extracted to MUKI's local media folder and associated with the note. The study screen shows the first associated image as an optional hint; cards do not need images, and audio remains separate. The **Images: ON · first 3 views / Images: OFF** session control lets you disable image hints at any time. When enabled, a card's image is shown for its first three presentations in that session, then hidden automatically to encourage retrieval without the picture. The Image → Hanzi mode follows the same progression: after the third image-assisted presentation, it asks you to retrieve the word from memory without the image. Exposure counts reset when a new study session starts.

MUKI uses Tk's built-in image support for supported PNG/GIF/PPM/PGM files. Pillow is optional and enables additional formats such as JPEG and WebP while resizing previews before display; it is not a mandatory dependency. Without Pillow, unsupported formats display a fallback message rather than crashing. The current lightweight viewer displays the first image associated with a note, not a full Anki template or multi-image gallery.

## Adaptive practice (v0.5.2)

Practice mode uses a separate practice-history table. Again, Hard, Good and Easy ratings affect only practice weakness scores; they do not change SRS due dates, intervals, ease factors, repetitions or normal review history. Scores use the latest 20 practice results per card with recency weighting. Incorrect typed answers are counted as errors even if the learner later corrects the answer; a single recorded mistake raises the card's weakness priority. Cards without practice history start as unassessed (score 2). Every selected card appears at least once in a weighted randomized round. High-priority cards appear three times, medium-priority cards twice, and low-priority or unassessed cards once; weaker cards are also more likely to appear earlier. A new round starts automatically when the current round ends. Normal SRS mode continues to use the existing scheduler.

Existing v0.5.1 databases are upgraded automatically by creating the practice-history table and advancing the schema version; existing cards and SRS review history are retained.

## Lightweight performance

MUKI uses only Python's standard library, Tkinter and SQLite. SQLite uses a small cache, memory-backed temporary storage and indexes for deck/review lookups. Audio remains optional. The target remains a 32-bit i686 antiX machine with 2 GB RAM; please report timings from that hardware before making speed claims.

## Mandarin card design

A card can store:
- Hanzi and tone-marked pinyin
- Meaning / translation
- Example sentence, sentence pinyin and translation
- Usage notes, including context to distinguish homophones
- Separate word and sentence audio paths

MUKI supports multiple cards containing the same pronunciation or characters. Context, meaning and recordings help distinguish homophones; audio alone cannot distinguish identical-sounding words without context.

## Compatibility promises

MUKI does not yet claim Anki APKG/COLPKG compatibility, FSRS parity, automatic speech recognition, or pronunciation scoring. The current scheduler is intentionally simple and will need more testing and refinement. Audio is local and offline; no cloud speech service is required.

## Roadmap

1. Foundation: desktop shell, SQLite schema, deck navigation.
2. **v0.2:** Mandarin note/card editor, local audio attachment/recording, character-recall and listening-drill modes, basic study flow and scheduler.
3. **v0.3:** Anki APKG import and validation report.
4. Mandarin-focused improvements: tone-aware listening modes, homophone/context drills, HSK tags.
5. More robust scheduling, statistics, backups and performance testing on i686.
6. Windows portability.

See DESIGN.md and docs/ARCHITECTURE.md for design and architecture notes.


## Project license

MUKI is intended to be distributed under the **GNU General Public License
version 3 or (at your option) any later version**. See [LICENSE](LICENSE)
and [NOTICE](NOTICE). You may use, study, modify, and redistribute the
software under the license terms. Third-party and user-imported materials may
have separate licenses.

## Data location and backups

MUKI stores its database under `$XDG_DATA_HOME/muki/`, or
`~/.local/share/muki/` when `XDG_DATA_HOME` is unset. The existing database
path is retained for compatibility. The v0.5.4 backup and restore design is
documented in
[`docs/architecture/DATA_AND_BACKUP_V0.5.4.md`](docs/architecture/DATA_AND_BACKUP_V0.5.4.md).
Backup features described there are planned until implemented and tested.

## Development history

See [CHANGELOG.md](CHANGELOG.md) for release notes and
[`docs/journey/DEVELOPMENT_JOURNEY.md`](docs/journey/DEVELOPMENT_JOURNEY.md)
for the project's development journal. Contributions are welcome; see
[CONTRIBUTING.md](CONTRIBUTING.md).
