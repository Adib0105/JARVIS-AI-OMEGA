from __future__ import annotations

import argparse
import os
import sys
import tempfile
from ctypes import create_unicode_buffer, windll, wintypes
from pathlib import Path

import edge_tts


def _short_path(path: str) -> str:
    if os.name != 'nt':
        return path
    get_short_path = windll.kernel32.GetShortPathNameW
    get_short_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short_path.restype = wintypes.DWORD
    size = 0
    while True:
        buffer = create_unicode_buffer(size)
        needed = get_short_path(path, buffer, size)
        if needed == 0:
            return path
        if size >= needed:
            return buffer.value
        size = needed


def _mci_send(command: str) -> None:
    if os.name != 'nt':
        raise RuntimeError('Native packaged TTS playback is only supported on Windows.')
    result = int(windll.winmm.mciSendStringW(command, 0, 0, 0))
    if result:
        raise RuntimeError(f'Windows audio playback failed with MCI error {result}.')


def play_mp3_windows(path: str | Path) -> None:
    target = _short_path(str(Path(path).resolve()))
    _mci_send('Close JARVISTTS')
    _mci_send(f'Open "{target}" Type MPEGVideo Alias JARVISTTS')
    try:
        _mci_send('Play JARVISTTS Wait')
    finally:
        try:
            _mci_send('Close JARVISTTS')
        except Exception:
            pass


def synthesize_and_play(
    text: str,
    *,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
) -> None:
    spoken = str(text or '').strip()
    if not spoken:
        raise ValueError('TTS worker received empty text.')
    media_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as media:
            media_path = media.name
        communicator = edge_tts.Communicate(
            spoken,
            voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
        )
        communicator.save_sync(media_path)
        if not Path(media_path).exists() or Path(media_path).stat().st_size <= 0:
            raise RuntimeError('TTS synthesis produced no playable audio data.')
        play_mp3_windows(media_path)
    finally:
        if media_path:
            try:
                os.unlink(media_path)
            except OSError:
                pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--voice', required=True)
    parser.add_argument('--rate', default='+0%')
    parser.add_argument('--volume', default='+0%')
    parser.add_argument('--pitch', default='+0Hz')
    parser.add_argument('--file', required=True)
    return parser


def run_edge_playback_worker(argv: list[str] | None = None) -> int:
    """Frozen-safe replacement for ``python -m edge_playback``.

    In a PyInstaller build ``sys.executable`` is JARVIS-OMEGA-V7.exe. The parent
    voice controller still launches that executable so playback remains
    interruptible, but desktop_app routes the child here before any GUI/bootstrap
    code can execute.
    """
    args, unknown = _parser().parse_known_args(list(argv or []))
    if unknown:
        raise ValueError(f'Unsupported TTS worker arguments: {unknown!r}')
    text = Path(args.file).read_text(encoding='utf-8', errors='replace')
    try:
        synthesize_and_play(
            text,
            voice=args.voice,
            rate=args.rate,
            volume=args.volume,
            pitch=args.pitch,
        )
        return 0
    except Exception as exc:
        # No credentials are involved in this worker. Keep diagnostics concise and
        # never include environment/configuration values.
        print(f'JARVIS TTS worker failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


__all__ = ['play_mp3_windows', 'run_edge_playback_worker', 'synthesize_and_play']
