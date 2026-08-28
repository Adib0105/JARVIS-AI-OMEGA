from __future__ import annotations

import queue
import threading
import unittest
from unittest.mock import patch

import jarvis.providers.deadline as deadline
from jarvis.microphone import WakeWordListener


class _FakeThread:
    instances = []

    def __init__(self, *, target, args=(), daemon=None, name=None):
        self.target = target
        self.args = args
        self.daemon = daemon
        self.name = name
        self.alive = False
        self.join_calls = []
        self.__class__.instances.append(self)

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls.append(timeout)
        self.alive = False


class RuntimeReliabilityPolishTests(unittest.TestCase):
    def test_provider_worker_capacity_fails_closed_when_all_slots_are_busy(self):
        slots = threading.BoundedSemaphore(1)
        self.assertTrue(slots.acquire(blocking=False))
        try:
            with patch.object(deadline, '_PROVIDER_WORKER_SLOTS', slots):
                with self.assertRaisesRegex(TimeoutError, 'capacity is exhausted'):
                    deadline.call_with_deadline(lambda: 'unused', 1.0)
        finally:
            slots.release()

    def test_provider_worker_slot_is_released_after_success(self):
        slots = threading.BoundedSemaphore(1)
        with patch.object(deadline, '_PROVIDER_WORKER_SLOTS', slots):
            self.assertEqual(deadline.call_with_deadline(lambda: 'ok', 1.0), 'ok')
            self.assertTrue(slots.acquire(blocking=False))
            slots.release()

    def test_wake_listener_restart_uses_distinct_stop_event(self):
        _FakeThread.instances = []
        listener = WakeWordListener(lambda _command: None, chunk_seconds=2.0, continuous_seconds=0)
        with patch('jarvis.microphone.threading.Thread', _FakeThread):
            listener.start()
            first_thread = _FakeThread.instances[-1]
            first_stop = first_thread.args[0]
            self.assertFalse(first_stop.is_set())

            listener.stop(wait=False)
            self.assertTrue(first_stop.is_set())

            listener.start()
            second_thread = _FakeThread.instances[-1]
            second_stop = second_thread.args[0]
            self.assertIsNot(first_stop, second_stop)
            self.assertTrue(first_stop.is_set())
            self.assertFalse(second_stop.is_set())

    def test_wake_listener_stop_performs_bounded_join(self):
        _FakeThread.instances = []
        listener = WakeWordListener(lambda _command: None, chunk_seconds=2.0, continuous_seconds=0)
        with patch('jarvis.microphone.threading.Thread', _FakeThread):
            listener.start()
            thread = _FakeThread.instances[-1]
            stopped = listener.stop(wait=True, timeout=0.25)
        self.assertTrue(stopped)
        self.assertEqual(thread.join_calls, [0.25])

    def test_existing_deadline_queue_contract_remains_compatible(self):
        blocker = threading.Event()
        with patch('jarvis.providers.deadline.queue.Queue.get', side_effect=queue.Empty):
            with self.assertRaisesRegex(TimeoutError, '1s request deadline'):
                deadline.call_with_deadline(lambda: blocker.wait(30), 0.05, operation='compatibility request')


if __name__ == '__main__':
    unittest.main()
