import random
import unittest

from muki.study import (
    check_answer, normalize_pinyin, practice_priority_label,
    prompt_for_mode, weighted_shuffle_cards,
)


class MandarinRecallTests(unittest.TestCase):
    def setUp(self):
        self.fields = {
            "hanzi": "你好",
            "pinyin": "nǐ hǎo",
            "meaning": "hello",
            "word_audio": "/tmp/nihao.wav",
        }

    def test_tone_marked_and_unmarked_pinyin_match(self):
        self.assertEqual(normalize_pinyin("nǐ hǎo"), normalize_pinyin("ni hao"))
        self.assertEqual(normalize_pinyin("nǐ hǎo"), normalize_pinyin("ni3 hao3"))
        self.assertEqual(normalize_pinyin("lǜ"), normalize_pinyin("lv"))
        self.assertNotEqual(normalize_pinyin("xi an"), normalize_pinyin("xian"))

    def test_hanzi_to_pinyin_accepts_unmarked_input(self):
        self.assertTrue(check_answer(self.fields, "hanzi_to_pinyin", "ni hao"))
        self.assertFalse(check_answer(self.fields, "hanzi_to_pinyin", "ni hou"))

    def test_pinyin_to_hanzi(self):
        self.assertEqual(prompt_for_mode(self.fields, "pinyin_to_hanzi"), "nǐ hǎo")
        self.assertTrue(check_answer(self.fields, "pinyin_to_hanzi", " 你 好 "))
        self.assertFalse(check_answer(self.fields, "pinyin_to_hanzi", "你好啊"))

    def test_meaning_to_pronunciation(self):
        self.assertEqual(prompt_for_mode(self.fields, "meaning_to_pinyin"), "hello")
        self.assertTrue(check_answer(self.fields, "meaning_to_pinyin", "ni3 hao3"))

    def test_image_mode_falls_back_to_meaning_when_no_image_is_attached(self):
        from muki.study import resolve_mode

        self.assertEqual(resolve_mode(self.fields, "image_to_hanzi"), "meaning_to_pinyin")
        self.assertEqual(
            prompt_for_mode(self.fields, resolve_mode(self.fields, "image_to_hanzi")),
            "hello",
        )
        self.assertTrue(
            check_answer(self.fields, resolve_mode(self.fields, "image_to_hanzi"), "ni hao")
        )

    def test_image_mode_is_preserved_when_image_is_attached(self):
        from muki.study import resolve_mode

        fields = dict(self.fields, image_media=["/tmp/buy.png"])
        self.assertEqual(resolve_mode(fields, "image_to_hanzi"), "image_to_hanzi")

    def test_audio_to_word(self):
        self.assertEqual(prompt_for_mode(self.fields, "audio_to_hanzi"), self.fields["word_audio"])
        self.assertTrue(check_answer(self.fields, "audio_to_hanzi", "你好"))

    def test_empty_answers_never_pass(self):
        self.assertFalse(check_answer(self.fields, "hanzi_to_pinyin", ""))
        self.assertFalse(check_answer({"hanzi": "你", "meaning": "you"}, "hanzi_to_pinyin", " "))



class AdaptivePracticeOrderTests(unittest.TestCase):
    def test_low_priority_round_contains_each_card_once_and_is_shuffled(self):
        cards = [
            {"card": {"id": card_id}, "weakness_score": 0.5, "has_history": True}
            for card_id in range(1, 9)
        ]
        ordered = weighted_shuffle_cards(cards, rng=random.Random(7))
        self.assertEqual(
            {item["card"]["id"] for item in ordered},
            {item["card"]["id"] for item in cards},
        )
        self.assertEqual(len(ordered), len(cards))
        self.assertNotEqual(
            [item["card"]["id"] for item in ordered],
            [item["card"]["id"] for item in cards],
        )

    def test_weaker_cards_are_more_likely_to_appear_earlier(self):
        weak = {"card": {"id": 1}, "weakness_score": 1.0, "has_history": True}
        strong = {"card": {"id": 2}, "weakness_score": 0.0, "has_history": True}
        weak_first = 0
        for seed in range(100):
            ordered = weighted_shuffle_cards([weak, strong], rng=random.Random(seed))
            if ordered[0]["card"]["id"] == 1:
                weak_first += 1
        self.assertGreater(weak_first, 55)

    def test_priority_labels(self):
        self.assertEqual(practice_priority_label(3.5), "High")
        self.assertEqual(practice_priority_label(2.0), "Medium")
        self.assertEqual(practice_priority_label(0.5), "Low")
        self.assertEqual(practice_priority_label(2.0, has_history=False), "Unassessed")

    def test_weak_cards_receive_more_practice_repetitions(self):
        cards = [
            {"card": {"id": 1}, "weakness_score": 4.0, "has_history": True},
            {"card": {"id": 2}, "weakness_score": 2.0, "has_history": True},
            {"card": {"id": 3}, "weakness_score": 0.5, "has_history": True},
            {"card": {"id": 4}, "weakness_score": 2.0, "has_history": False},
        ]
        ordered = weighted_shuffle_cards(cards, rng=random.Random(11))
        counts = {}
        for item in ordered:
            card_id = item["card"]["id"]
            counts[card_id] = counts.get(card_id, 0) + 1
        self.assertEqual(counts, {1: 3, 2: 2, 3: 1, 4: 1})
        card_ids = [item["card"]["id"] for item in ordered]
        self.assertTrue(all(left != right for left, right in zip(card_ids, card_ids[1:])))


if __name__ == "__main__":
    unittest.main()
