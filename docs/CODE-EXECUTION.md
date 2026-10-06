# Isolated code execution — V8 development

`RUN CODE TESTS` and `SelfDevelopmentTester` now share an opt-in Linux-container
runner. An unconfigured or unsupported machine still returns
`EXECUTION_ISOLATION_UNAVAILABLE` without starting project code. An ordinary
permission approval cannot enable host Python execution.

## Prerequisites and activation

Use a dedicated local Docker Linux engine on a disposable development machine;
Windows requires Docker Desktop in Linux-container mode. The engine must report
cgroup v2, memory/swap/PID/CPU limit support and the built-in seccomp profile.
The connection is fixed to the local Unix socket or Windows Docker named pipe.
Remote Docker contexts, inherited Docker configuration and `DOCKER_HOST` are not
used. Rootless/custom sockets are not supported by this initial adapter.

An operator must independently review and provision a Python image with
`/usr/local/bin/python3` and the required offline dependencies. It must have no
declared volumes. Configure its full immutable **local image ID**, for example:

```dotenv
# Replace with the actual reviewed image ID from docker image inspect.
JARVIS_CODE_SANDBOX_IMAGE=sha256:<64 lowercase hex characters>
```

The product never pulls/builds images, runs package installation, accepts an image
from tool arguments or substitutes an image tag. CI provisions the official
`python:3.12-slim` image on its disposable runner and records the resolved digest
and ID; this does not activate a production client. Dependencies that are missing
from the image produce a failed check, not a host/network fallback.

## Execution boundary

The existing tool schema, approved-root policy, capability approval, effect ledger
and audit run first. The background worker snapshots regular text/code files into
a private archive (2 MB/file, 2,000 files, 32 MiB source, 40 MiB archive). Linked
files, hardlinks, reparse paths, oversized/binary inputs and unstable reads are
rejected. Known secret names, Git metadata, environments, data/log/export/backup/
workspace/build directories are omitted. The result reports counts and a digest.
This is deliberately a restricted Python-project snapshot, not an arbitrary
repository clone; projects requiring omitted fixtures must use a separately
reviewed environment. The digest describes the copied input, not an atomic Git
commit snapshot of a concurrently changing directory.

The archive travels through stdin. **There are no host bind mounts, shared
volumes, Docker sockets, host environment credentials or file exports.** A trusted
bootstrap extracts only bounded regular files in `/work` and executes one fixed
compileall/unittest/pytest command. The GUI currently selects unittest; the
self-development flow runs compileall and unittest. Arbitrary shell/build commands
are not enabled. Compileall output stays inside the container.

Container policy: non-root UID/GID 65534, read-only image, private PID/cgroup
namespaces, no network, no IPC sharing, all capabilities dropped, no new privileges,
built-in seccomp, 64 processes, 512 MiB memory with no additional swap, one CPU,
128 descriptors, no core dumps. Writable tmpfs is restricted to 64 MiB `/work`
and 32 MiB `/tmp`, both noexec/nosuid/nodev. Logging is disabled on the daemon;
stdout/stderr are drained directly and separately, with a combined 65,536-byte
limit. This also bounds local live display. No private test output is persisted
in mission evidence; only redacted content summaries are retained there.

The trusted local engine/image/kernel are part of the trust boundary. Containers
share the Linux engine kernel and are not equivalent to a hardware VM against
kernel exploits. Use a dedicated VM/engine and maintained runtimes for hostile
code; do not configure an engine that hosts sensitive production workloads.

## Lifecycle and UI

All snapshot, control, process and cleanup work runs off Tk. A bounded event queue
delivers live output/status to the Tk owner. Permission dialogs also use an
owner-polled queue; background threads do not schedule Tk calls. Output is
redacted after complete lines, including secrets split across pipe reads; oversized
lines are suppressed. Output beyond the runner cap stops the execution.

`CANCEL TESTS` sets a cancellation event and keeps the UI busy until cleanup
finishes. Timeout/cancellation/output overflow kills the attached CLI and then
force-removes the named container, killing its process namespace. A PID-1
wall-clock watchdog also stops the namespace if the app/CLI connection disappears.
Normal window close cancels the runner and lets its bounded cleanup worker finish.
An abrupt application/host crash can leave a stopped container record; no claim
of crash-persistent garbage collection is made in this increment.

The final result distinguishes PASSED, FAILED, TIMEOUT, CANCELLED, OUTPUT_LIMIT,
MEMORY_LIMIT, ERROR and CLEANUP_FAILED. Only a confirmed exit code 0 plus verified
container removal can pass. Failed cleanup blocks subsequent runs in the process
until removal or absence is independently confirmed. The UI recovers and reports
the cleanup error; a completed CLI alone never certifies test success.

## Verification

`tests/test_v8_execution.py` covers policy, immutable images, disabled/unavailable
runtime, link/secret/snapshot limits, stream redaction, cleanup uncertainty,
duplicate/cancel handling, real subprocess floods/timeouts/descendant pipes and
real headless Tcl progress/permission/cancellation responsiveness.

`tests_sandbox/test_docker_execution.py` is a separate **real Docker** suite. It
does not mock the backend or silently skip an unavailable engine when invoked.
It checks ordinary coding and self-development paths, host file/env/network
denial, resource/security settings inside the container, failed tests, separate
streams, timeout with detached descendants, cancellation/recovery, output floods,
memory exhaustion and no remaining labeled containers.

This Linux workspace has no Docker engine; local policy/process/UI results and
the real-daemon CI results must be reported separately. Windows Docker Desktop,
rendered GUI and physical device acceptance remain release gates.

Primary design references: [Docker execution/resource controls](https://docs.docker.com/engine/containers/run/),
[seccomp](https://docs.docker.com/engine/security/seccomp/),
[cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).
