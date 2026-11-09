import unittest

from muki.study import check_answer, normalize_pinyin, prompt_for_mode


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

    def test_audio_to_word(self):
        self.assertEqual(prompt_for_mode(self.fields, "audio_to_hanzi"), self.fields["word_audio"])
        self.assertTrue(check_answer(self.fields, "audio_to_hanzi", "你好"))

    def test_empty_answers_never_pass(self):
        self.assertFalse(check_answer(self.fields, "hanzi_to_pinyin", ""))
        self.assertFalse(check_answer({"hanzi": "你", "meaning": "you"}, "hanzi_to_pinyin", " "))


if __name__ == "__main__":
    unittest.main()
