from __future__ import annotations

import time
import urllib.parse
import webbrowser

import psutil

from ..web_tools import read_web_page, search_web


_BROWSER_PROCESS_NAMES = {
    'chrome.exe', 'msedge.exe', 'firefox.exe', 'brave.exe', 'opera.exe',
    'chrome', 'msedge', 'firefox', 'brave', 'opera',
}


def _browser_processes() -> list[dict]:
    rows = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = str(proc.info.get('name') or '').lower()
            if name in _BROWSER_PROCESS_NAMES:
                rows.append({'pid': int(proc.info['pid']), 'name': name})
        except Exception:
            continue
    return rows


class BrowserAgent:
    """Browser abstraction that keeps network content explicitly untrusted.

    Browser opening/navigation uses the user's default browser. Read/extract uses an
    HTTP reader rather than pretending the visible browser DOM was inspected.
    Semantic visible-UI interaction is provided separately by the computer-use UIA
    engine and requires its own capability/approval path.
    """

    SEARCH_ENGINES = {
        'google': 'https://www.google.com/search?q={query}',
        'bing': 'https://www.bing.com/search?q={query}',
        'youtube': 'https://www.youtube.com/results?search_query={query}',
        'github': 'https://github.com/search?q={query}',
    }

    def open(self, url: str) -> dict:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            return {'ok': False, 'error': 'Only valid HTTP/HTTPS URLs are allowed.'}
        before = _browser_processes()
        opened = bool(webbrowser.open(url, new=2))
        time.sleep(0.35)
        after = _browser_processes()
        return {
            'ok': opened,
            'action': 'open',
            'url': url,
            'verification': {
                'status': 'PARTIAL',
                'verified': False,
                'browser_process_detected': bool(after),
                'process_count_before': len(before),
                'process_count_after': len(after),
                'reason': 'Browser process evidence cannot prove the requested page finished loading.',
            },
        }

    def search(self, engine: str, query: str) -> dict:
        engine = engine.strip().lower()
        if engine not in self.SEARCH_ENGINES:
            return {'ok': False, 'error': f'Unsupported browser search engine: {engine}'}
        query = query.strip()
        if not query:
            return {'ok': False, 'error': 'Search query is empty.'}
        url = self.SEARCH_ENGINES[engine].format(query=urllib.parse.quote_plus(query))
        result = self.open(url)
        return result | {'engine': engine, 'query': query, 'action': 'search'}

    @staticmethod
    def read(url: str, max_chars: int = 14000) -> dict:
        result = read_web_page(url, max_chars=max_chars)
        return {
            'ok': True,
            'action': 'read',
            'url': url,
            'untrusted_content': True,
            'result': result,
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': 'HTTP fetch returned page content.',
            },
        }

    @staticmethod
    def public_search(query: str, max_results: int = 5) -> dict:
        results = search_web(query, max_results=max_results)
        return {
            'ok': True,
            'action': 'public_search',
            'query': query,
            'untrusted_content': True,
            'results': results,
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': f'{len(results)} search result(s) returned.' if isinstance(results, list) else 'Search service returned data.',
            },
        }

    @staticmethod
    def extract(url: str, keyword: str = '', max_chars: int = 18000) -> dict:
        page = read_web_page(url, max_chars=max_chars)
        if not isinstance(page, dict):
            return {'ok': False, 'error': 'Page reader returned an unexpected payload.', 'untrusted_content': True}
        content = str(page.get('content') or page.get('text') or '')
        if keyword.strip():
            needle = keyword.strip().lower()
            chunks = [part.strip() for part in content.split('\n') if needle in part.lower()]
            extracted = '\n'.join(chunks)[:max_chars]
        else:
            extracted = content[:max_chars]
        return {
            'ok': True,
            'action': 'extract',
            'url': url,
            'keyword': keyword,
            'untrusted_content': True,
            'content': extracted,
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'characters': len(extracted),
            },
        }
