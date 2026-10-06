"""Single-flight background work with Tk owned exclusively by the UI thread.

This transports results; it is not an execution sandbox and cannot kill native
calls. Do not release a running slot on a UI timeout and start duplicate work.
"""
from __future__ import annotations

import queue
import threading
import time


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
        self._progress = queue.Queue(maxsize=128)
        self._dropped = threading.Event()

    def _assert_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError('Task lifecycle must be managed on the Tk thread.')

    @property
    def running(self):
        # Includes an undelivered completion; a new job cannot overwrite it.
        return self._thread is not None

    def start(self, fn, done, failed, progress=None, *, daemon=True):
        self._assert_owner()
        if self._closed or self.running:
            return False
        self._callbacks = (done, failed, progress)
        self._dropped.clear()
        self._progress_error = None
        while not self._progress.empty():
            self._progress.get_nowait()

        def worker():
            try:
                result = (True, fn())
            except BaseException as exc:
                # SystemExit in a worker must also restore the owning view.
                result = (False, f'{type(exc).__name__}: {exc}')
            self._results.put_nowait(result)

        self._thread = threading.Thread(target=worker, name='jarvis-ui-task', daemon=daemon)
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
        done, failed, progress = self._callbacks
        for _ in range(64):
            try:
                item = self._progress.get_nowait()
            except queue.Empty:
                break
            if progress is not None:
                try:
                    progress(item)
                except Exception as exc:
                    self._progress_error = f'Live output error: {type(exc).__name__}: {exc}'
                    progress = None
                    self._callbacks = (done, failed, None)
        if self._dropped.is_set() and progress is not None:
            self._dropped.clear()
            try:
                progress({'stream': 'status', 'text': 'Some live output was omitted because the UI queue was full.'})
            except Exception as exc:
                self._progress_error = f'Live output error: {type(exc).__name__}: {exc}'
        if self._thread.is_alive():
            self._after_id = self.root.after(self.poll_ms, self._poll)
            return
        if not self._progress.empty():
            self._after_id = self.root.after(self.poll_ms, self._poll)
            return
        ok, value = self._results.get_nowait()
        self._thread = None
        self._callbacks = None
        if self._progress_error:
            failed(self._progress_error)
        else:
            (done if ok else failed)(value)

    def post_progress(self, item):
        """Worker-safe, bounded, nonblocking; does not call any Tk API."""
        if self._closed:
            return
        try:
            self._progress.put_nowait(item)
        except queue.Full:
            self._dropped.set()

    def close(self):
        self._assert_owner()
        self._closed = True
        self._callbacks = None
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        # A still-running function retains ownership until actual exit. Closing a
        # view does not mean that a side effect was cancelled or never happened.


class TkCallGate:
    """Marshal synchronous permission dialogs to a Tk-owned polling queue."""
    def __init__(self, root, *, closing=lambda: False):
        self.root = root
        self.owner = threading.get_ident()
        self.pending = queue.Queue(maxsize=16)
        self.closed = threading.Event()
        self.closing = closing
        self.after_id = root.after(25, self._poll)

    def call(self, fn, *, default=False, cancel=None, timeout=120):
        if self.closed.is_set() or self.closing() or (cancel is not None and cancel.is_set()):
            return default
        if threading.get_ident() == self.owner:
            return fn()
        request = {'fn': fn, 'event': threading.Event(), 'value': default, 'abandoned': False,
                   'cancel': cancel}
        try:
            self.pending.put_nowait(request)
        except queue.Full:
            return default
        deadline = time.monotonic() + timeout
        while not request['event'].wait(.05):
            if self.closed.is_set() or self.closing() or time.monotonic() >= deadline or (cancel is not None and cancel.is_set()):
                request['abandoned'] = True
                return default
        return request['value']

    def _poll(self):
        self.after_id = None
        if self.closed.is_set():
            return
        try:
            request = self.pending.get_nowait()
        except queue.Empty:
            request = None
        if request is not None:
            try:
                if not self.closing() and not request['abandoned'] and not (request['cancel'] is not None and request['cancel'].is_set()):
                    request['value'] = request['fn']()
            except Exception:
                pass  # Permission UI failure preserves the default denial.
            finally:
                request['event'].set()
                if not self.closed.is_set():
                    self.after_id = self.root.after(25, self._poll)
        else:
            self.after_id = self.root.after(25, self._poll)

    def close(self):
        self.closed.set()
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
