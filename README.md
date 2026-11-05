# MUKI

**MUKI** is a lightweight, offline-first spaced-repetition application focused on Mandarin Chinese. It is designed for constrained hardware, with a 32-bit i686 antiX Linux / Intel Atom N270 / 2 GB RAM machine as the reference target.

## Current status

**v0.2 development branch — cards and audio foundation.** Adds Mandarin card creation/editing, pinyin and sentence fields, local audio attachment and recording, a basic review flow, and a simple four-button interval scheduler. This is an early scheduler, not an FSRS implementation or Anki scheduling clone.

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

## Add your first Mandarin card

1. Open **Deck library**.
2. Double-click a deck, or create one first.
3. Select **+ Add card**.
4. Enter Hanzi, pinyin with tone marks, and meaning. Add an example sentence, sentence pinyin, translation, and usage/homophone notes if useful.
5. Choose existing audio files or record a six-second word/sentence clip.
6. Save. Double-click a card in the deck to edit it.
7. Open **Study session** from that deck. Reveal the answer and grade Again, Hard, Good, or Easy (keys 1–4).

Audio formats depend on the installed system player. MP3, WAV, OGG, FLAC and M4A are offered in the file picker; the installed backend determines which formats actually play. WAV recording uses arecord or ffmpeg/ALSA.

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
3. Anki APKG import and validation report.
4. Mandarin-focused improvements: tone-aware listening modes, homophone/context drills, HSK tags.
5. More robust scheduling, statistics, backups and performance testing on i686.
6. Windows portability.

See DESIGN.md and docs/ARCHITECTURE.md for design and architecture notes.
