from __future__ import annotations

from urllib.parse import urlparse

from ddgs import DDGS


def _clean_result(item: dict) -> dict:
    return {
        'title': str(item.get('title') or '').strip(),
        'url': str(item.get('href') or item.get('url') or '').strip(),
        'snippet': str(item.get('body') or item.get('description') or '').strip(),
        'source': str(item.get('source') or '').strip(),
        'date': str(item.get('date') or '').strip(),
    }


def search_web(query: str, max_results: int = 6) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    cap = max(1, min(int(max_results), 10))
    results = DDGS(timeout=10).text(query, safesearch='moderate', max_results=cap)
    return [_clean_result(item) for item in results]


def search_news(query: str, max_results: int = 6, timelimit: str = 'w') -> list[dict]:
    query = query.strip()
    if not query:
        return []
    cap = max(1, min(int(max_results), 10))
    window = timelimit if timelimit in {'d', 'w', 'm', 'y'} else 'w'
    results = DDGS(timeout=10).news(query, safesearch='moderate', timelimit=window, max_results=cap)
    return [_clean_result(item) for item in results]


def read_web_page(url: str, max_chars: int = 12000) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Only valid http/https URLs are allowed.')
    cap = max(1000, min(int(max_chars), 20000))
    result = DDGS(timeout=12).extract(url, fmt='text_plain')
    if isinstance(result, dict):
        text = str(result.get('content') or result.get('text') or result)
    else:
        text = str(result)
    return text[:cap]
