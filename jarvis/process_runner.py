"""Bounded transport for trusted subprocesses; this module is NOT a sandbox.

Project code is only launched by code_execution inside a configured container.
Callbacks run on this caller's thread, never on pipe-reader threads or Tk.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import queue
import signal
import subprocess
import threading
import time


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    reason: str = ''


def _kill(process):
    # POSIX readers can outlive a parent that left a child holding its pipes.
    if os.name != 'nt':
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()  # Only the trusted Docker CLI runs on the Windows host.
    process.wait(timeout=3)


def run_process(argv, *, cwd, env, timeout, cancel=None, stdin=None,
                on_output=None, output_limit=65536) -> ProcessResult:
    """Drain both pipes concurrently; cap aggregate output and elapsed time.

Cancellation kills the CLI. The sandbox owner separately removes the container;
CLI exit must never be treated as proof that the container stopped.
"""
    if cancel is not None and cancel.is_set():
        return ProcessResult(130, b'', b'', 'cancelled')
    pending = queue.Queue(maxsize=16)
    stopping = threading.Event()
    readers = []
    output = {'stdout': bytearray(), 'stderr': bytearray()}
    size, reason = 0, ''
    deadline = time.monotonic() + max(.01, timeout)
    process = subprocess.Popen(
        list(argv), cwd=str(cwd), env=env, stdin=stdin or subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
        start_new_session=os.name != 'nt',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )

    def read_pipe(name, pipe):
        try:
            while not stopping.is_set():
                block = pipe.read(4096)
                if not block:
                    break
                while not stopping.is_set():
                    try:
                        pending.put((name, block), timeout=.05)
                        break
                    except queue.Full:
                        pass
        except OSError:
            pass

    try:
        for name, pipe in (('stdout', process.stdout), ('stderr', process.stderr)):
            reader = threading.Thread(target=read_pipe, args=(name, pipe), daemon=True,
                                      name='jarvis-process-' + name)
            reader.start()
            readers.append(reader)
        while True:
            if cancel is not None and cancel.is_set():
                reason = 'cancelled'
                break
            if time.monotonic() >= deadline:
                reason = 'timeout'
                break
            try:
                name, block = pending.get(timeout=.025)
            except queue.Empty:
                if process.poll() is not None and not any(t.is_alive() for t in readers):
                    break
                continue
            remaining = max(0, output_limit - size)
            output[name].extend(block[:remaining])
            size += len(block)
            if on_output is not None and remaining:
                on_output(name, block[:remaining])
            if size > output_limit:
                reason = 'output_limit'
                break
    finally:
        stopping.set()
        _kill(process)
        for reader in readers:
            reader.join(timeout=1)
        for pipe in (process.stdout, process.stderr):
            pipe.close()
    return ProcessResult(process.returncode, bytes(output['stdout']), bytes(output['stderr']), reason)
