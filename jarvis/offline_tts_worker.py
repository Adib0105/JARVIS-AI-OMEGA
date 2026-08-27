from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyttsx3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--file', required=True)
    parser.add_argument('--rate', type=int, default=170)
    parser.add_argument('--volume', type=float, default=1.0)
    return parser


def run_offline_playback_worker(argv: list[str] | None = None) -> int:
    """Speak one text file and exit; the parent can terminate this process safely."""
    try:
        args, unknown = _parser().parse_known_args(list(argv or []))
        if unknown:
            raise ValueError(f'Unsupported offline TTS worker arguments: {unknown!r}')
        text = Path(args.file).read_text(encoding='utf-8', errors='replace').strip()
        if not text:
            raise ValueError('Offline TTS worker received empty text.')
        engine = pyttsx3.init()
        engine.setProperty('rate', max(80, min(360, int(args.rate))))
        engine.setProperty('volume', max(0.0, min(1.0, float(args.volume))))
        engine.say(text)
        engine.runAndWait()
        return 0
    except Exception as exc:
        print(f'JARVIS offline TTS worker failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(run_offline_playback_worker(sys.argv[1:]))


__all__ = ['run_offline_playback_worker']
