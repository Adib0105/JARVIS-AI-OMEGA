"""Single-flight background work with Tk owned exclusively by the UI thread.

This transports results; it is not an execution sandbox and cannot kill native
calls. Do not release a running slot on a UI timeout and start duplicate work.
"""
from __future__ import annotations

import queue
import threading


class TkTaskRunner:
    def __init__(self, root, *, poll_ms=25):
        self.root = root
        self.poll_ms = max(10, int(poll_ms))
        self._owner = threading.get_ident()
        self._thread = None
        self._results = queue.Queue(maxsize=1)
        self._callbacks = None
        self._after_id = None
        self._closed = False

    def _assert_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError('Task lifecycle must be managed on the Tk thread.')

    @property
    def running(self):
        # Includes an undelivered completion; a new job cannot overwrite it.
        return self._thread is not None

    def start(self, fn, done, failed):
        self._assert_owner()
        if self._closed or self.running:
            return False
        self._callbacks = (done, failed)

        def worker():
            try:
                result = (True, fn())
            except BaseException as exc:
                # SystemExit in a worker must also restore the owning view.
                result = (False, f'{type(exc).__name__}: {exc}')
            self._results.put_nowait(result)

        self._thread = threading.Thread(target=worker, name='jarvis-ui-task', daemon=True)
        try:
            self._thread.start()
        except BaseException as exc:
            self._thread = None
            self._callbacks = None
            failed(f'{type(exc).__name__}: {exc}')
            return False
        self._after_id = self.root.after(self.poll_ms, self._poll)
        return True

    def _poll(self):
        self._assert_owner()
        self._after_id = None
        if self._closed:
            return
        if self._thread.is_alive():
            self._after_id = self.root.after(self.poll_ms, self._poll)
            return
        ok, value = self._results.get_nowait()
        done, failed = self._callbacks
        self._thread = None
        self._callbacks = None
        (done if ok else failed)(value)

    def close(self):
        self._assert_owner()
        self._closed = True
        self._callbacks = None
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        # A still-running function retains ownership until actual exit. Closing a
        # view does not mean that a side effect was cancelled or never happened.
