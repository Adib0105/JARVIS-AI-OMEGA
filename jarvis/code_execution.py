"""Opt-in, offline Linux-container execution for approved Python projects.

No host Python fallback, host mount, network, provider key or project-controlled
image/command. The existing permission/audit gate still runs before this layer.
See docs/CODE-EXECUTION.md for the boundary and operational prerequisites.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tarfile
import tempfile
import threading
import time
import uuid

from .local_files import LocalFiles, SAFE_EXTENSIONS
from .process_runner import run_process
from .safe_files import read_bounded
from .security.redaction import redact_text


ISOLATION_ERROR = ('EXECUTION_ISOLATION_UNAVAILABLE: configure a reviewed local Linux '
                   'Docker engine and JARVIS_CODE_SANDBOX_IMAGE=sha256:<image-id>. '
                   'Project code was not executed on the host.')
MAX_ARCHIVE = 40 * 1024 * 1024
MAX_SOURCE = 32 * 1024 * 1024
MAX_FILES = 2000
_LOCK = threading.Lock()
_UNCLEAN = set()
_IGNORED = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.idea',
            '.vscode', 'data', 'logs', 'exports', 'backups', 'workspace', 'dist', 'build'}
COMMANDS = {
    'unittest': ['-m', 'unittest', 'discover', '-s', 'tests', '-v'],
    'compileall': ['-m', 'compileall', '-f', '-q', '.'],
    'pytest': ['-m', 'pytest', '-q'],
}


@dataclass
class ExecutionControl:
    cancel: threading.Event = field(default_factory=threading.Event)
    emit: object = None

    def check(self):
        if self.cancel.is_set():
            raise InterruptedError('Cancellation requested; no further code action was started.')

    def event(self, stream, text):
        if self.emit is not None:
            try:
                self.emit({'stream': stream, 'text': redact_text(str(text))})
            except Exception:
                pass  # A closed progress consumer cannot skip process cleanup.


CURRENT = ContextVar('jarvis_code_execution', default=None)


@contextmanager
def execution_context(control):
    token = CURRENT.set(control)
    try:
        yield
    finally:
        CURRENT.reset(token)


class _OutputLines:
    """Redact complete lines, including tokens split across pipe reads.

Suppress oversized lines entirely instead of publishing an incomplete secret.
"""
    def __init__(self, control):
        self.control = control
        self.pending = {'stdout': b'', 'stderr': b''}
        self.discard = set()

    def feed(self, stream, block):
        for i, piece in enumerate(block.split(b'\n')):
            if i:
                if stream in self.discard:
                    self.control.event(stream, '[Oversized output line suppressed.]\n')
                    self.discard.remove(stream)
                else:
                    self.control.event(stream, self.pending[stream].decode('utf-8', 'replace') + '\n')
                self.pending[stream] = b''
            if stream not in self.discard:
                self.pending[stream] += piece
                if len(self.pending[stream]) > 4096:
                    self.pending[stream] = b''
                    self.discard.add(stream)

    def finish(self):
        for stream in self.pending:
            if stream in self.discard:
                self.control.event(stream, '[Oversized output line suppressed.]\n')
            elif self.pending[stream]:
                self.control.event(stream, self.pending[stream].decode('utf-8', 'replace'))


def snapshot_project(root: Path, output: Path, control: ExecutionControl, deadline: float) -> dict:
    """Copy approved, bounded regular text files; never follow links/reparse points.

Input is a private archive sent over stdin, not a mount of the user's project.
No container-created archive or file is extracted on the host.
"""
    root = Path(root).absolute()
    files = LocalFiles()
    files.roots = (root.resolve(),)
    count = total = skipped = visited = 0
    digest = hashlib.sha256()
    with tarfile.open(output, 'w') as archive:
        for current, dirs, names in os.walk(root, followlinks=False):
            control.check()
            if time.monotonic() >= deadline:
                raise TimeoutError('Project snapshot timed out.')
            visited += 1 + len(dirs) + len(names)
            if visited > 10000:
                raise ValueError('Project has too many directory entries; select a smaller project.')
            retained = []
            for name in sorted(dirs):
                path = Path(current) / name
                info = path.lstat()
                if (name.lower() in _IGNORED or files._looks_secret(path)
                        or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400):
                    skipped += 1
                else:
                    retained.append(name)
            dirs[:] = retained
            for name in sorted(names):
                control.check()
                path = Path(current) / name
                relative = path.relative_to(root).as_posix()
                if files._looks_secret(path) or path.suffix.lower() not in SAFE_EXTENSIONS:
                    skipped += 1
                    continue
                # Directory descriptors / Windows handle identity resist swaps.
                _, info, raw = read_bounded(files, str(path), SAFE_EXTENSIONS)
                if info.st_nlink != 1:
                    raise PermissionError('Hard-linked project files are not supported.')
                if b'\0' in raw:
                    raise ValueError('Binary project inputs are not supported by this runner.')
                total += len(raw)
                count += 1
                if total > MAX_SOURCE or count > MAX_FILES:
                    raise ValueError('Project snapshot exceeds the 32 MiB / 2,000 file limit.')
                item = tarfile.TarInfo(relative)
                item.size, item.mode, item.mtime = len(raw), 0o600, 0
                archive.addfile(item, io.BytesIO(raw))
                digest.update(relative.encode('utf-8') + b'\0' + hashlib.sha256(raw).digest())
    if not count or output.stat().st_size > MAX_ARCHIVE:
        raise ValueError('Project snapshot is empty or too large.')
    return {'files': count, 'bytes': total, 'skipped': skipped, 'sha256': digest.hexdigest()}


# Runs as PID 1. Exit kills the entire private PID namespace, including detached
# grandchildren. Its wall-clock watchdog also bounds execution if the GUI dies or
# loses the Docker connection. Project code runs only after input validation.
_BOOTSTRAP = r'''
import io, os, pathlib, struct, subprocess, sys, tarfile, threading
kind, seconds = sys.argv[1], float(sys.argv[2])
timer = threading.Timer(seconds, lambda: os._exit(124))
timer.daemon = True
timer.start()
os.environ.clear()
os.environ.update(PATH='/usr/local/bin:/usr/bin:/bin', HOME='/tmp', LANG='C.UTF-8',
                  PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
def exact(size):
    data = bytearray()
    while len(data) < size:
        part = sys.stdin.buffer.read(min(65536, size-len(data)))
        if not part: raise ValueError('Incomplete project input')
        data.extend(part)
    return data
size = struct.unpack('!Q', exact(8))[0]
if not 0 < size <= 40*1024*1024: raise ValueError('Input too large')
data = exact(size)
os.chdir('/work')
total = count = 0
with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
    for item in archive:
        parts = pathlib.PurePosixPath(item.name)
        if not item.isfile() or parts.is_absolute() or '..' in parts.parts:
            raise ValueError('Unsafe input member')
        total += item.size; count += 1
        if total > 32*1024*1024 or count > 2000: raise ValueError('Input limit')
        path = pathlib.Path('/work', *parts.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as target: target.write(archive.extractfile(item).read())
del data
commands = {'unittest': ['-m','unittest','discover','-s','tests','-v'],
            'compileall': ['-m','compileall','-f','-q','.'], 'pytest':['-m','pytest','-q']}
result = subprocess.run([sys.executable, '-u', *commands[kind]], stdin=subprocess.DEVNULL)
os._exit(result.returncode if 0 <= result.returncode <= 255 else 125)
'''


class DockerCodeRunner:
    def __init__(self, image=None):
        self.image = image if image is not None else os.getenv('JARVIS_CODE_SANDBOX_IMAGE', '').strip()

    def _configured(self):
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', self.image):
            raise PermissionError(ISOLATION_ERROR)
        binary = shutil.which('docker')
        if not binary:
            raise PermissionError(ISOLATION_ERROR)
        return str(Path(binary).resolve())

    @staticmethod
    def _verify_engine(info):
        if (info.get('OSType') != 'linux' or info.get('CgroupVersion') != '2'
                or not all(info.get(key) is True for key in ('MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsQuota'))
                or not any('name=seccomp' in str(x) and 'profile=builtin' in str(x)
                           for x in info.get('SecurityOptions', []))):
            raise PermissionError(ISOLATION_ERROR + ' Required seccomp/cgroup v2 limits are unavailable.')

    def _create_args(self, name, kind, timeout):
        return ['create', '--name', name, '--pull=never', '--interactive',
                '--label', 'com.jarvis.code-sandbox=1', '--network=none',
                '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges=true',
                '--user=65534:65534', '--pids-limit=64', '--memory=512m', '--memory-swap=512m',
                '--cpus=1', '--ulimit=nofile=128:128', '--ulimit=core=0:0',
                '--tmpfs=/work:rw,nosuid,nodev,noexec,size=64m,mode=1777',
                '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=32m,mode=1777',
                '--ipc=none', '--cgroupns=private', '--no-healthcheck', '--log-driver=none',
                '--workdir=/work', '--entrypoint=/usr/local/bin/python3', self.image,
                '-I', '-S', '-u', '-c', _BOOTSTRAP, kind, str(timeout)]

    def run(self, project, *, kind='unittest', timeout=120, control=None):
        binary = self._configured()  # Missing configuration must spawn nothing.
        if kind not in COMMANDS:
            raise ValueError('Only compileall, unittest and pytest are allowlisted.')
        control = control or CURRENT.get() or ExecutionControl()
        control.check()
        if not _LOCK.acquire(blocking=False):
            raise RuntimeError('A code test is already running; wait for cleanup before retrying.')
        started = time.monotonic()
        timeout = max(1., min(float(timeout), 900.))
        deadline = started + timeout
        name = 'jarvis-code-' + uuid.uuid4().hex
        attempted = False
        cleanup = True
        result = {'ok': False, 'returncode': 125, 'status': 'ERROR', 'backend': 'docker-linux',
                  'stdout': '', 'stderr': '', 'cleanup_verified': False}
        try:
            with tempfile.TemporaryDirectory(prefix='jarvis-code-') as directory:
                directory = Path(directory)
                config = directory / 'docker-config'
                config.mkdir()
                endpoint = 'npipe:////./pipe/docker_engine' if os.name == 'nt' else 'unix:///var/run/docker.sock'
                base = [binary, '--config', str(config), '--host', endpoint]
                env = {k: os.environ[k] for k in ('PATH', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP') if k in os.environ}
                env.update(HOME=str(directory), USERPROFILE=str(directory))

                def cli(args, *, final=False, stdin=None, stream=None):
                    remaining = 5. if final else min(15., deadline - time.monotonic())
                    if not final:
                        control.check()
                        if remaining <= 0:
                            raise TimeoutError('Code execution deadline expired.')
                    return run_process(base + args, cwd=directory, env=env, timeout=remaining,
                                       cancel=None if final else control.cancel, stdin=stdin,
                                       on_output=stream, output_limit=65536)

                def checked(args):
                    reply = cli(args)
                    if reply.reason or reply.returncode:
                        raise RuntimeError('Docker control failed: ' + (reply.reason or redact_text(reply.stderr.decode('utf-8', 'replace'))[:1000]))
                    return reply.stdout.decode('utf-8')

                def remove(container):
                    removed = cli(['rm', '--force', '--volumes', container], final=True)
                    if removed.returncode == 0 and not removed.reason:
                        return True
                    # A create may have failed before reaching the daemon. Prove
                    # absence using a successful exact-name query, not an error.
                    listed = cli(['container', 'ls', '--all', '--quiet', '--filter',
                                  'name=^/' + container + '$'], final=True)
                    return listed.returncode == 0 and not listed.reason and not listed.stdout.strip()

                try:
                    # Retry an uncertain cleanup before accepting another run.
                    for old in tuple(_UNCLEAN):
                        if not remove(old):
                            raise RuntimeError('Previous container cleanup remains unconfirmed; execution blocked.')
                        _UNCLEAN.discard(old)
                    control.event('status', 'Checking execution isolation…')
                    self._verify_engine(json.loads(checked(['info', '--format', '{{json .}}'])))
                    image = json.loads(checked(['image', 'inspect', self.image]))[0]
                    if (image.get('Id') != self.image or image.get('Os') != 'linux'
                            or image.get('Config', {}).get('Volumes')):
                        raise PermissionError(ISOLATION_ERROR + ' Image identity/volume policy rejected.')
                    control.event('status', 'Preparing a bounded project snapshot…')
                    archive = directory / 'source.tar'
                    result['snapshot'] = snapshot_project(Path(project), archive, control, deadline)
                    framed = directory / 'input.bin'
                    with framed.open('wb') as out, archive.open('rb') as source:
                        out.write(struct.pack('!Q', archive.stat().st_size))
                        shutil.copyfileobj(source, out)
                    attempted = True  # Even a failed CLI may have reached the daemon.
                    checked(self._create_args(name, kind, max(.1, deadline - time.monotonic())))
                    control.event('status', f'Running {kind} in the isolated container…')
                    lines = _OutputLines(control)
                    with framed.open('rb') as source:
                        attached = run_process(base + ['start', '--attach', '--interactive', name],
                                               cwd=directory, env=env, stdin=source,
                                               timeout=max(.01, deadline - time.monotonic()), cancel=control.cancel,
                                               on_output=lines.feed, output_limit=65536)
                    lines.finish()
                    result.update(stdout=redact_text(attached.stdout.decode('utf-8', 'replace')),
                                  stderr=redact_text(attached.stderr.decode('utf-8', 'replace')))
                    if attached.reason:
                        result.update(status=attached.reason.upper(), returncode=130 if attached.reason == 'cancelled' else 124 if attached.reason == 'timeout' else 125)
                    else:
                        state = json.loads(checked(['inspect', '--format', '{{json .State}}', name]))
                        code = state.get('ExitCode')
                        if state.get('Running') is not False or type(code) is not int or state.get('Status') != 'exited':
                            raise RuntimeError('Container exit could not be independently confirmed.')
                        result.update(returncode=code, status='TIMEOUT' if code == 124 else 'PASSED' if code == 0 else 'FAILED')
                        # Older Python unittest versions exit 0 for empty discovery.
                        if kind == 'unittest' and re.search(r'\bRan 0 tests?\b', result['stderr']):
                            result.update(returncode=5, status='NO_TESTS')
                        if state.get('OOMKilled') is True:
                            result['status'] = 'MEMORY_LIMIT'
                except InterruptedError as exc:
                    result.update(status='CANCELLED', returncode=130, error=str(exc))
                except TimeoutError as exc:
                    result.update(status='TIMEOUT', returncode=124, error=str(exc))
                except Exception as exc:
                    result.update(error=redact_text(f'{type(exc).__name__}: {exc}'))
                finally:
                    if attempted:
                        control.event('status', 'Stopping the container and cleaning temporary files…')
                        try:
                            cleanup = remove(name)
                        except Exception:
                            cleanup = False
                        if not cleanup:
                            _UNCLEAN.add(name)
                            result.update(status='CLEANUP_FAILED', returncode=125,
                                          error='Container removal could not be confirmed. Further execution is blocked until cleanup succeeds.')
                    result['cleanup_verified'] = cleanup
                result['ok'] = result['status'] == 'PASSED' and result['returncode'] == 0 and cleanup
        finally:
            _LOCK.release()
        result['duration_ms'] = round((time.monotonic() - started) * 1000, 3)
        return result
