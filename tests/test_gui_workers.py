import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.gui import JarvisDesktop


class DeferredRoot:
    def __init__(self):
        self.callbacks = []

    def after(self, _delay, callback):
        self.callbacks.append(callback)


class FailingJarvis:
    @staticmethod
    def chat(_text):
        raise RuntimeError('chat failed')

    @staticmethod
    def run_mission(_goal, _progress):
        raise RuntimeError('mission failed')

    @staticmethod
    def analyze_image(_image, _prompt):
        raise RuntimeError('vision failed')


class GuiWorkerExceptionTests(unittest.TestCase):
    @staticmethod
    def _subject(done_name):
        root = DeferredRoot()
        calls = []
        subject = SimpleNamespace(root=root, jarvis=FailingJarvis())
        setattr(subject, done_name, lambda *args: calls.append(args))
        return subject, root, calls

    def test_answer_error_survives_deferred_tk_callback(self):
        subject, root, calls = self._subject('_answer_done')
        JarvisDesktop._answer_worker(subject, 'hello', [])
        root.callbacks[0]()
        self.assertEqual(calls, [('', 'chat failed', False)])

    def test_mission_error_survives_deferred_tk_callback(self):
        subject, root, calls = self._subject('_mission_done')
        JarvisDesktop._mission_worker(subject, 'goal')
        root.callbacks[0]()
        self.assertEqual(calls, [('', 'mission failed')])

    def test_microphone_error_survives_deferred_tk_callback(self):
        subject, root, calls = self._subject('_mic_done')
        with patch('jarvis.gui.record_and_transcribe', side_effect=RuntimeError('mic failed')):
            JarvisDesktop._mic_worker(subject)
        root.callbacks[0]()
        self.assertEqual(calls, [('', 'mic failed')])

    def test_vision_error_survives_deferred_tk_callback(self):
        subject, root, calls = self._subject('_vision_done')
        with patch('jarvis.gui.capture_screen', return_value=SimpleNamespace(name='screen.png')):
            JarvisDesktop._vision_worker(subject, 'inspect')
        root.callbacks[0]()
        self.assertEqual(calls, [('', '', 'vision failed')])


if __name__ == '__main__':
    unittest.main()
