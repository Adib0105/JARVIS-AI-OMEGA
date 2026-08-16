from __future__ import annotations

import time
import urllib.parse
import webbrowser

import psutil

from ..web_tools import read_web_page, search_web
from .browser_security import assess_public_url, scan_prompt_injection


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
    """Browser abstraction with explicit domain trust and prompt-injection isolation.

    Browser opening/navigation uses the user's default browser. Public read/extract
    paths reject local/private addresses. Webpage text is always returned as untrusted
    data with an injection scan; it never becomes agent/system instructions.
    """

    SEARCH_ENGINES = {
        'google': 'https://www.google.com/search?q={query}',
        'bing': 'https://www.bing.com/search?q={query}',
        'youtube': 'https://www.youtube.com/results?search_query={query}',
        'github': 'https://github.com/search?q={query}',
    }

    @staticmethod
    def trust(url: str) -> dict:
        return assess_public_url(url).as_dict()

    def open(self, url: str) -> dict:
        trust = assess_public_url(url)
        if not trust.allowed:
            return {'ok': False, 'error': '; '.join(trust.reasons), 'trust': trust.as_dict()}
        before = _browser_processes()
        opened = bool(webbrowser.open(url, new=2))
        time.sleep(0.35)
        after = _browser_processes()
        return {
            'ok': opened,
            'action': 'open',
            'url': url,
            'trust': trust.as_dict(),
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
        trust = assess_public_url(url)
        if not trust.allowed:
            return {'ok': False, 'error': '; '.join(trust.reasons), 'trust': trust.as_dict(), 'untrusted_content': True}
        result = read_web_page(url, max_chars=max_chars)
        text = str(result)
        scan = scan_prompt_injection(text)
        return {
            'ok': True,
            'action': 'read',
            'url': url,
            'trust': trust.as_dict(),
            'untrusted_content': True,
            'prompt_injection_scan': scan.as_dict(),
            'result': text,
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': 'Public HTTP reader returned page content; content remains untrusted data.',
            },
        }

    @staticmethod
    def public_search(query: str, max_results: int = 5) -> dict:
        results = search_web(query, max_results=max_results)
        scans = []
        if isinstance(results, list):
            for row in results:
                combined = f"{row.get('title', '')}\n{row.get('snippet', '')}"
                scan = scan_prompt_injection(combined)
                if scan.suspicious:
                    scans.append({'url': row.get('url', ''), **scan.as_dict()})
        return {
            'ok': True,
            'action': 'public_search',
            'query': query,
            'untrusted_content': True,
            'prompt_injection_flags': scans,
            'results': results,
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': f'{len(results)} search result(s) returned.' if isinstance(results, list) else 'Search service returned data.',
            },
        }

    @staticmethod
    def extract(url: str, keyword: str = '', max_chars: int = 18000) -> dict:
        trust = assess_public_url(url)
        if not trust.allowed:
            return {'ok': False, 'error': '; '.join(trust.reasons), 'trust': trust.as_dict(), 'untrusted_content': True}
        page = read_web_page(url, max_chars=max_chars)
        # read_web_page returns plain text. Older BrowserAgent code expected a dict,
        # causing valid extraction calls to fail; normalize both forms for compatibility.
        if isinstance(page, dict):
            content = str(page.get('content') or page.get('text') or '')
        else:
            content = str(page)
        if keyword.strip():
            needle = keyword.strip().lower()
            chunks = [part.strip() for part in content.split('\n') if needle in part.lower()]
            extracted = '\n'.join(chunks)[:max_chars]
        else:
            extracted = content[:max_chars]
        scan = scan_prompt_injection(extracted)
        return {
            'ok': True,
            'action': 'extract',
            'url': url,
            'keyword': keyword,
            'trust': trust.as_dict(),
            'untrusted_content': True,
            'prompt_injection_scan': scan.as_dict(),
            'content': extracted,
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'characters': len(extracted),
                'evidence': 'Extracted text came from the requested public page and remains untrusted data.',
            },
        }
