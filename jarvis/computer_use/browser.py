from __future__ import annotations

import hashlib
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
    paths use a DNS/redirect-safe address-pinned reader. Webpage text is always returned
    as untrusted data with an injection scan; it never becomes agent/system instructions.
    Research mode gathers bounded multi-source evidence but deliberately does not claim
    that source agreement proves factual truth.
    """

    SEARCH_ENGINES = {
        'google': 'https://www.google.com/search?q={query}',
        'bing': 'https://www.bing.com/search?q={query}',
        'youtube': 'https://www.youtube.com/results?search_query={query}',
        'github': 'https://github.com/search?q={query}',
    }

    @staticmethod
    def trust(url: str) -> dict:
        return assess_public_url(url, resolve_dns=True).as_dict()

    def open(self, url: str) -> dict:
        # Opening a URL in the user's browser still performs a network/navigation side
        # effect, so resolve DNS up front and refuse private/mixed answers.
        trust = assess_public_url(url, resolve_dns=True)
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
        try:
            result = read_web_page(url, max_chars=max_chars)
        except (ValueError, OSError, TimeoutError) as exc:
            return {
                'ok': False,
                'action': 'read',
                'url': url,
                'trust': trust.as_dict(),
                'untrusted_content': True,
                'error': f'Public page read blocked/failed: {type(exc).__name__}: {exc}',
                'verification': {'status': 'FAILED', 'verified': False, 'evidence': 'No trusted fetch result was returned.'},
            }
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
                'evidence': 'Address-pinned public HTTP reader returned page content; content remains untrusted data.',
            },
        }

    @staticmethod
    def public_search(query: str, max_results: int = 5) -> dict:
        query = str(query).strip()
        if not query:
            return {'ok': False, 'action': 'public_search', 'query': '', 'error': 'Search query is empty.', 'untrusted_content': True}
        try:
            results = search_web(query, max_results=max_results)
        except Exception as exc:
            return {
                'ok': False,
                'action': 'public_search',
                'query': query,
                'error': f'Public search failed: {type(exc).__name__}: {exc}',
                'untrusted_content': True,
                'verification': {'status': 'FAILED', 'verified': False},
            }
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
        try:
            page = read_web_page(url, max_chars=max_chars)
        except (ValueError, OSError, TimeoutError) as exc:
            return {
                'ok': False,
                'action': 'extract',
                'url': url,
                'keyword': keyword,
                'trust': trust.as_dict(),
                'untrusted_content': True,
                'error': f'Public page extraction blocked/failed: {type(exc).__name__}: {exc}',
                'verification': {'status': 'FAILED', 'verified': False, 'evidence': 'No trusted fetch result was returned.'},
            }
        # read_web_page returns plain text. Normalize the old dict shape as a
        # compatibility courtesy for injected/test readers.
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
                'evidence': 'Extracted text came from the address-pinned public page and remains untrusted data.',
            },
        }

    @staticmethod
    def snapshot(url: str, max_chars: int = 18000) -> dict:
        """Return a deterministic content fingerprint for a safely fetched page."""
        read = BrowserAgent.read(url, max_chars=max_chars)
        if not read.get('ok'):
            return read | {'action': 'snapshot'}
        text = str(read.get('result') or '')
        digest = hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()
        return {
            'ok': True,
            'action': 'snapshot',
            'url': url,
            'sha256': digest,
            'characters': len(text),
            'trust': read.get('trust'),
            'untrusted_content': True,
            'prompt_injection_scan': read.get('prompt_injection_scan'),
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': 'Fingerprint was computed from content returned by the address-pinned public reader.',
            },
        }

    @staticmethod
    def changed(url: str, previous_sha256: str, max_chars: int = 18000) -> dict:
        """Compare a prior page fingerprint with a fresh safely fetched snapshot."""
        previous = str(previous_sha256).strip().lower()
        if len(previous) != 64 or any(ch not in '0123456789abcdef' for ch in previous):
            return {'ok': False, 'action': 'changed', 'url': url, 'error': 'previous_sha256 must be a 64-character hexadecimal SHA-256 digest.'}
        current = BrowserAgent.snapshot(url, max_chars=max_chars)
        if not current.get('ok'):
            return current | {'action': 'changed', 'previous_sha256': previous}
        current_hash = str(current['sha256'])
        return {
            'ok': True,
            'action': 'changed',
            'url': url,
            'previous_sha256': previous,
            'current_sha256': current_hash,
            'changed': current_hash != previous,
            'characters': current.get('characters', 0),
            'untrusted_content': True,
            'prompt_injection_scan': current.get('prompt_injection_scan'),
            'verification': {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': 'Fresh safe-reader content fingerprint was compared to the supplied prior fingerprint.',
            },
        }

    @staticmethod
    def research(query: str, *, max_results: int = 6, max_pages: int = 3, max_chars_per_page: int = 6000) -> dict:
        """Gather bounded multi-source web evidence without claiming factual verification."""
        query = str(query).strip()
        if not query:
            return {'ok': False, 'action': 'research', 'query': '', 'error': 'Research query is empty.'}
        result_cap = max(1, min(int(max_results), 10))
        page_cap = max(1, min(int(max_pages), 5))
        char_cap = max(1000, min(int(max_chars_per_page), 10000))
        search = BrowserAgent.public_search(query, max_results=result_cap)
        if not search.get('ok'):
            return search | {'action': 'research'}

        sources = []
        failures = []
        seen: set[str] = set()
        for row in search.get('results') or []:
            url = str(row.get('url') or '').strip()
            if not url or url in seen:
                continue
            seen.add(url)
            if len(sources) >= page_cap:
                break
            page = BrowserAgent.read(url, max_chars=char_cap)
            if not page.get('ok'):
                failures.append({'url': url, 'error': page.get('error', 'read failed')})
                continue
            sources.append({
                'title': str(row.get('title') or ''),
                'url': url,
                'snippet': str(row.get('snippet') or ''),
                'content': str(page.get('result') or ''),
                'prompt_injection_scan': page.get('prompt_injection_scan'),
                'trust': page.get('trust'),
            })

        return {
            'ok': bool(search.get('results')),
            'action': 'research',
            'query': query,
            'untrusted_content': True,
            'search_results': search.get('results') or [],
            'sources_read': sources,
            'source_failures': failures,
            'verification': {
                'status': 'PARTIAL',
                'verified': False,
                'evidence': (
                    f'Gathered {len(sources)} safely fetched source page(s). '
                    'Transport/read evidence is verified per page, but source claims are not automatically factual truth.'
                ),
            },
        }
