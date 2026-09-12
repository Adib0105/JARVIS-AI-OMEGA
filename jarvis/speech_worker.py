"""Isolated speech process: source and frozen Windows builds share this entrypoint.

The parent owns the temporary directory and kills this process to interrupt speech.
No transcript or API key is placed in the command line.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

from .config import settings


def speech_chunks(text: str, limit: int = 1200):
    """Bound provider input size, preferring sentence/word boundaries."""
    text = text.strip()
    while text:
        if len(text) <= limit:
            yield text
            return
        window = text[:limit]
        boundaries = list(re.finditer(r'[.!?।]\s+|\s+', window))
        end = boundaries[-1].end() if boundaries else limit
        yield text[:end].strip()
        text = text[end:].lstrip()


def speech_segments(text):
    """Render a short first sentence before synthesizing a long answer."""
    text = text.strip()
    if not text:
        return
    match = re.search(r'[.!?।](?:\s+|$)', text[:220])
    if match:
        end = match.end()
    else:
        end = text.rfind(' ', 0, 220) if len(text) > 220 else len(text)
        if end <= 0:
            end = min(220, len(text))
    yield text[:end].strip()
    yield from speech_chunks(text[end:].lstrip(), limit=400)


def play_prefetched(chunks, directory, render, play=None):
    """Render the next segment during playback; keep at most two audio files."""
    play = play or play_audio
    chunks = iter(chunks)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='tts-prefetch') as pool:
        def submit(index, text):
            path = Path(directory) / f'segment-{index}.mp3'
            def task():
                render(text, path)
                return path
            return pool.submit(task)
        first = next(chunks, None)
        if first is None:
            return
        current = submit(0, first)
        index = 1
        while current is not None:
            path = current.result()
            following = next(chunks, None)
            upcoming = submit(index, following) if following is not None else None
            index += 1
            try:
                play(path)
            finally:
                path.unlink(missing_ok=True)
            current = upcoming


def play_audio(path: Path) -> None:
    if os.name == 'nt':
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        mci.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        mci.restype = ctypes.c_uint
        def send(command):
            code = mci(command, None, 0, None)
            if code:
                raise RuntimeError(f'Windows audio playback failed ({code})')
        send(f'open "{path}" alias jarvis_speech')
        try:
            send('play jarvis_speech wait')
        finally:
            send('close jarvis_speech')
        return
    # Source installs on non-Windows systems need a media player.
    player = shutil.which('mpv') or shutil.which('ffplay')
    if not player:
        raise RuntimeError('Install mpv or ffplay for neural speech playback on this OS.')
    args = ([player, '--no-video', '--really-quiet', str(path)] if Path(player).name == 'mpv'
            else [player, '-nodisp', '-autoexit', '-loglevel', 'error', str(path)])
    subprocess.run(args, check=True, timeout=180)


def speak_offline(text: str, speed: float) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    try:
        engine.setProperty('rate', int(max(80, min(360, settings.voice_rate * speed))))
        engine.setProperty('volume', settings.voice_volume)
        voices = engine.getProperty('voices') or []
        selected = settings.offline_voice_id
        if not selected:
            for voice in voices:
                description = f'{getattr(voice, "name", "")} {getattr(voice, "gender", "")}'.lower()
                if any(hint in description for hint in ('female', 'zira', 'heera', 'hazel')):
                    selected = voice.id
                    break
        if selected:
            engine.setProperty('voice', selected)
        engine.say(text)
        engine.runAndWait()
    finally:
        engine.stop()


def render_openai(text: str, path: Path, speed: float) -> None:
    from openai import OpenAI
    if not settings.openai_api_key.strip():
        raise RuntimeError('OPENAI_API_KEY is required for OpenAI speech.')
    kwargs = dict(model=settings.openai_tts_model, voice=settings.openai_tts_voice,
                  input=text, response_format='mp3', speed=speed)
    if settings.openai_tts_model.startswith('gpt-4o-mini-tts'):
        kwargs['instructions'] = settings.openai_tts_instructions
    with OpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=0) as client:
        with client.audio.speech.with_streaming_response.create(**kwargs) as response:
            response.stream_to_file(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--engine', choices=('edge', 'openai', 'pyttsx3'), required=True)
    parser.add_argument('--speed', type=float, default=1.0)
    args = parser.parse_args(argv)
    text_path = Path(args.file)
    text = text_path.read_text(encoding='utf-8')
    speed = max(0.6, min(2.0, args.speed))
    if args.engine == 'pyttsx3':
        speak_offline(text, speed)
        return 0
    from .voice import choose_voice, edge_rate_for_speed
    # Resolve once: short English opening words must not switch the voice halfway.
    voice_name = choose_voice(text)
    def render(chunk, path):
        if args.engine == 'openai':
            render_openai(chunk, path, speed)
        else:
            import edge_tts
            asyncio.run(edge_tts.Communicate(
                chunk, voice_name, rate=edge_rate_for_speed(settings.edge_voice_rate, speed),
                volume=settings.edge_voice_volume, pitch=settings.edge_voice_pitch,
            ).save(str(path)))
    with tempfile.TemporaryDirectory(prefix='segments-', dir=text_path.parent) as directory:
        play_prefetched(speech_segments(text), directory, render)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
