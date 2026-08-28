import unittest

from jarvis.runtime_guard import (
    clean_display_text,
    local_identity_answer,
    looks_garbled,
    preferred_text_model,
)


class RuntimeGuardTests(unittest.TestCase):
    def test_creator_identity_is_deterministic(self):
        answer = local_identity_answer('tumhe kisne banaya hai aur kya kya kar sakte ho')
        self.assertIsNotNone(answer)
        self.assertIn('Adib Azam ne mujhe banaya hai', answer)
        self.assertIn('JARVIS', answer)
        self.assertIn('Screen Vision', answer)

    def test_unrelated_question_does_not_trigger_identity(self):
        self.assertIsNone(local_identity_answer('python list comprehension samjhao'))

    def test_markdown_is_cleaned_for_desktop(self):
        raw = '**Hello**\n- one\n- two\n`code`\n<formula>x</formula>'
        clean = clean_display_text(raw)
        self.assertNotIn('**', clean)
        self.assertNotIn('<formula>', clean)
        self.assertIn('• one', clean)
        self.assertIn('code', clean)

    def test_detects_mixed_cjk_corruption(self):
        self.assertTrue(looks_garbled('Main help kar sakta hoon メ random 文 broken', 'kya kar sakte ho'))

    def test_free_router_text_stays_on_live_free_router_by_default(self):
        model = preferred_text_model('openrouter/free', 'chat')
        self.assertEqual(model, 'openrouter/free')

    def test_vision_keeps_router_for_capability_filtering(self):
        self.assertEqual(preferred_text_model('openrouter/free', 'image'), 'openrouter/free')


if __name__ == '__main__':
    unittest.main()
