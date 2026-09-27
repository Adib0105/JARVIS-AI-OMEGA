"""Small reentrant cross-process lock for read/modify/replace local state."""
from contextlib import contextmanager
from pathlib import Path
import os
import threading
import time

_GUARD = threading.Lock()
_LOCKS = {}
_HELD = threading.local()


@contextmanager
def locked_file(path, timeout=5):
    key = str(Path(path).resolve())
    with _GUARD:
        lock = _LOCKS.setdefault(key, threading.RLock())
    with lock:
        held = getattr(_HELD, 'paths', None)
        if held is None:
            held = _HELD.paths = set()
        if key in held:
            yield
            return
        lock_path = Path(key + '.lock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('a+b') as handle:
            if not handle.tell():
                handle.write(b'0')
                handle.flush()
            deadline = time.monotonic() + timeout
            while True:
                try:
                    handle.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Settings are busy in another JARVIS process. Retry shortly.') from None
                    time.sleep(.02)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class FileMutex:
    def __init__(self, path):
        self.path = path
        self.local = threading.local()

    def __enter__(self):
        context = locked_file(self.path)
        context.__enter__()
        stack = getattr(self.local, 'stack', None)
        if stack is None:
            stack = self.local.stack = []
        stack.append(context)
        return self

    def __exit__(self, *args):
        return self.local.stack.pop().__exit__(*args)
