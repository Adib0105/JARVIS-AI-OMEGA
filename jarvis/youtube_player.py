"""User-requested YouTube playback in a separate, visible Edge browser."""
from __future__ import annotations

import queue
import threading
from urllib.parse import urlencode, urlparse, parse_qs

_jobs = queue.Queue()
_lock = threading.Lock()
_thread = None
_active_cancel = None
_stopping = threading.Event()


def play_on_page(page, query, cancelled=None):
    def check_cancelled():
        if _stopping.is_set() or (cancelled is not None and cancelled.is_set()):
            raise RuntimeError('YouTube request cancelled.')
    check_cancelled()
    page.set_default_timeout(5000)
    page.goto('https://www.youtube.com/results?' + urlencode({'search_query': query}), wait_until='domcontentloaded', timeout=12000)
    # Only ordinary video search results. Never click ads, consent or sign-in buttons.
    first = page.locator('ytd-video-renderer a#video-title:visible').first
    first.wait_for(state='visible', timeout=8000)
    href = first.get_attribute('href') or ''
    parsed = urlparse(href)
    if parsed.scheme not in {'', 'https'} or parsed.netloc not in {'', 'www.youtube.com', 'youtube.com'} or parsed.path != '/watch' or not parse_qs(parsed.query).get('v'):
        raise RuntimeError('First video link could not be validated.')
    check_cancelled()
    first.click(timeout=5000)
    page.wait_for_url('**/watch?**', timeout=8000)
    video = page.locator('video').first
    video.wait_for(state='visible', timeout=8000)
    # Real click grants a user gesture where autoplay is blocked.
    button = page.locator('button.ytp-play-button').first
    if video.evaluate('(v) => v.paused'):
        check_cancelled()
        button.click(timeout=5000)
    started_at = float(video.evaluate('(v) => v.currentTime'))
    page.wait_for_function('''(startedAt) => { const v = document.querySelector('video');
        return v && !v.paused && !v.ended && v.readyState >= 2 &&
            v.currentTime > startedAt + 0.15; }''', arg=started_at, timeout=8000)
    check_cancelled()
    destination = urlparse(page.url)
    if destination.hostname not in {'youtube.com', 'www.youtube.com'} or parse_qs(destination.query).get('v') != parse_qs(parsed.query).get('v'):
        raise RuntimeError('Playback moved away from the selected video.')
    ad = page.locator('.html5-video-player.ad-showing').count() > 0
    return {'url': page.url, 'playing': True, 'ad_playing': ad,
            'message': 'YouTube par ad play ho raha hai; selected video uske baad chalega.' if ad else 'YouTube ka pehla video play ho raha hai.'}


def _reply(reply, result):
    try:
        reply.put_nowait(result)
    except queue.Full:
        pass


def _drain_pending(message):
    # Caller holds _lock, shared with job submission and worker retirement.
    while True:
        try:
            _, reply, cancelled = _jobs.get_nowait()
            cancelled.set()
            _reply(reply, {'playing': False, 'message': message})
        except queue.Empty:
            break


def _worker():
    global _thread, _active_cancel
    browser = None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            try:
                while not _stopping.is_set():
                    try:
                        query, reply, cancelled = _jobs.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    with _lock:
                        _active_cancel = cancelled
                        if _stopping.is_set():
                            cancelled.set()
                    try:
                        if cancelled.is_set():
                            result = {'playing': False, 'message': 'YouTube request cancelled.'}
                        else:
                            if browser is None or not browser.is_connected():
                                browser = playwright.chromium.launch(channel='msedge', headless=False, timeout=15000)
                            if cancelled.is_set():
                                raise RuntimeError('YouTube request cancelled.')
                            page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else browser.new_page()
                            result = play_on_page(page, query, cancelled)
                    except Exception:
                        result = {'playing': False, 'message': 'YouTube playback verify nahi hua. Edge/Playwright installation, internet, consent ya autoplay check kijiye. Khuli browser window mein zarurat ho to Play dabaiye.'}
                    finally:
                        with _lock:
                            _active_cancel = None
                    _reply(reply, result)
            finally:
                if browser and browser.is_connected():
                    browser.close()
    except Exception:
        pass  # All pending callers receive the failure below.
    finally:
        with _lock:
            _drain_pending('YouTube player unavailable. Run setup_windows.ps1 and install Microsoft Edge.')
            # Atomic retirement: a concurrent submitter must start a new worker.
            _thread = None
            _active_cancel = None


def play_first_video(query):
    from .config import settings
    if not settings.enable_desktop_automation:
        raise RuntimeError('Desktop automation is disabled in settings.')
    query = str(query).strip()
    if not query or len(query) > 300:
        raise ValueError('YouTube song/search query must contain 1–300 characters.')
    reply, cancelled = queue.Queue(maxsize=1), threading.Event()
    global _thread
    with _lock:
        if _stopping.is_set():
            raise RuntimeError('YouTube player is shutting down.')
        _jobs.put((query, reply, cancelled))
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_worker, daemon=True, name='jarvis-youtube')
            _thread.start()
    try:
        return reply.get(timeout=100)
    except queue.Empty:
        cancelled.set()
        return {'playing': False, 'message': 'YouTube request timed out. Check the browser before retrying.'}


def shutdown():
    with _lock:
        _stopping.set()
        if _active_cancel is not None:
            _active_cancel.set()
        _drain_pending('YouTube player is shutting down.')
        worker = _thread
    if worker and worker is not threading.current_thread():
        worker.join(timeout=2)
