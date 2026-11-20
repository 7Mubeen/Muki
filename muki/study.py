"""Fast, dependency-free answer matching for Mandarin recall modes."""
from __future__ import annotations

import random
import re
import unicodedata


MODES = {
    "hanzi_to_pinyin": ("Hanzi → Pinyin", "hanzi", "pinyin"),
    "pinyin_to_hanzi": ("Pinyin → Hanzi", "pinyin", "hanzi"),
    "meaning_to_pinyin": ("Meaning → Pinyin", "meaning", "pinyin"),
    "audio_to_hanzi": ("Audio → Hanzi", "word_audio", "hanzi"),
    "image_to_hanzi": ("Image → Hanzi", "image_media", "hanzi"),
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
            if kept and kept[-1] != " ":
                kept.append(" ")
            continue
        kept.append(char)
    return unicodedata.normalize("NFC", "".join(kept)).strip()


def normalize_hanzi(value: str) -> str:
    """Normalize Unicode and whitespace without changing Chinese characters."""
    return "".join((value or "").split())


def resolve_mode(fields: dict, mode: str) -> str:
    """Use meaning-to-pinyin when an image prompt has no attached image."""
    if mode not in MODES:
        raise ValueError("Unknown study mode: " + str(mode))
    if mode == "image_to_hanzi":
        images = fields.get("image_media") or []
        if isinstance(images, str):
            images = [images] if images.strip() else []
        if not images:
            return "meaning_to_pinyin"
    return mode


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



def practice_priority_label(score: float, has_history: bool = True) -> str:
    """Translate an adaptive weakness score into a learner-facing label."""
    if not has_history:
        return "Unassessed"
    score = float(score)
    if score >= 3.0:
        return "High"
    if score >= 1.5:
        return "Medium"
    return "Low"


def weighted_shuffle_cards(cards, rng=None):
    """Build a weighted randomized round, repeating cards according to weakness.

    Every card appears at least once. High-priority cards appear three times,
    medium-priority cards twice, and low/unassessed cards once. Higher scores
    also make occurrences more likely to appear earlier. Each new round gets
    a fresh order.
    """
    source = rng or random
    weighted = []
    for item in cards:
        score = max(0.0, float(item.get("weakness_score", 2.0)))
        has_history = bool(item.get("has_history", True))
        if not has_history:
            repeats = 1
        elif score >= 3.0:
            repeats = 3
        elif score >= 1.5:
            repeats = 2
        else:
            repeats = 1
        weight = 1.0 + score
        for _ in range(repeats):
            random_key = max(float(source.random()), 1e-12) ** (1.0 / weight)
            weighted.append((random_key, item))
    weighted.sort(key=lambda pair: pair[0], reverse=True)

    # Avoid showing the same word back-to-back when another card is available.
    ordered = []
    while weighted:
        next_index = 0
        if ordered:
            previous_id = ordered[-1]["card"]["id"]
            for index, (_, candidate) in enumerate(weighted):
                if candidate["card"]["id"] != previous_id:
                    next_index = index
                    break
        _, item = weighted.pop(next_index)
        ordered.append(item)
    return ordered
