"""Fast, dependency-free answer matching for Mandarin recall modes."""
from __future__ import annotations

import re
import unicodedata


MODES = {
    "hanzi_to_pinyin": ("Hanzi → Pinyin", "hanzi", "pinyin"),
    "pinyin_to_hanzi": ("Pinyin → Hanzi", "pinyin", "hanzi"),
    "meaning_to_pinyin": ("Meaning → Pinyin", "meaning", "pinyin"),
    "audio_to_hanzi": ("Audio → Hanzi", "word_audio", "hanzi"),
}


def normalize_pinyin(value: str) -> str:
    """Compare pinyin with or without tone marks/numbers, preserving ü.

    Examples accepted as equivalent: nǐ hǎo, ni hao, ni3 hao3.
    The ü/ǖ/ǚ distinction is retained; v and u: are accepted as ü aliases.
    """
    value = (value or "").strip().lower().replace("u:", "ü").replace("v", "ü")
    decomposed = unicodedata.normalize("NFD", value)
    kept = []
    for char in decomposed:
        if char in "\u0300\u0301\u0304\u030c":
            continue
        if char.isdigit() and char in "12345":
            continue
        if char.isspace() or unicodedata.category(char).startswith("P"):
            continue
        kept.append(char)
    return unicodedata.normalize("NFC", "".join(kept))


def normalize_hanzi(value: str) -> str:
    """Normalize Unicode and whitespace without changing Chinese characters."""
    return "".join((value or "").split())


def prompt_for_mode(fields: dict, mode: str) -> str:
    """Return the visible prompt text; audio prompts are played by the UI."""
    if mode not in MODES:
        raise ValueError("Unknown study mode: " + str(mode))
    _, prompt_key, _ = MODES[mode]
    return str(fields.get(prompt_key, "") or "").strip()


def check_answer(fields: dict, mode: str, answer: str) -> bool:
    """Check a typed answer, ignoring pinyin tones but not its lexical spelling."""
    if mode not in MODES:
        raise ValueError("Unknown study mode: " + str(mode))
    _, _, answer_key = MODES[mode]
    expected = str(fields.get(answer_key, "") or "").strip()
    submitted = str(answer or "").strip()
    if not expected or not submitted:
        return False
    if answer_key == "pinyin":
        return normalize_pinyin(submitted) == normalize_pinyin(expected)
    return normalize_hanzi(submitted) == normalize_hanzi(expected)
