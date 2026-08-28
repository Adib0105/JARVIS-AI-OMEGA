from __future__ import annotations

import http.client
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from ddgs import DDGS

from .computer_use.browser_security import assess_public_url, resolve_public_addresses


_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_TEXT_CONTENT_TYPES = (
    'text/',
    'application/json',
    'application/xml',
    'application/xhtml+xml',
)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag.lower() in {'script', 'style', 'noscript', 'template', 'svg'}:
            self._ignored += 1
        elif not self._ignored and tag.lower() in {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4'}:
            self._parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {'script', 'style', 'noscript', 'template', 'svg'} and self._ignored:
            self._ignored -= 1
        elif not self._ignored and tag.lower() in {'p', 'div', 'li', 'tr'}:
            self._parts.append('\n')

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            self._parts.append(data)

    def text(self) -> str:
        lines = (' '.join(part.split()) for part in ''.join(self._parts).splitlines())
        return '\n'.join(line for line in lines if line)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._validated_address = address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._validated_address, self.port), self.timeout, self.source_address
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._validated_address = address

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._validated_address, self.port), self.timeout, self.source_address
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _clean_result(item: dict) -> dict:
    return {
        'title': str(item.get('title') or '').strip(),
        'url': str(item.get('href') or item.get('url') or '').strip(),
        'snippet': str(item.get('body') or item.get('description') or '').strip(),
        'source': str(item.get('source') or '').strip(),
        'date': str(item.get('date') or '').strip(),
    }


def _public_url(url: str):
    trust = assess_public_url(url, resolve_dns=True)
    if not trust.allowed:
        raise ValueError('; '.join(trust.reasons))
    parsed = urlparse(url.strip())
    return parsed


def _request_once(url: str, *, timeout: float, max_bytes: int) -> tuple[int, dict[str, str], bytes]:
    parsed = _public_url(url)
    host = str(parsed.hostname)
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    addresses = resolve_public_addresses(host, port)
    target = parsed.path or '/'
    if parsed.query:
        target += '?' + parsed.query
    last_error: OSError | None = None
    for address in addresses:
        connection_class = _PinnedHTTPSConnection if parsed.scheme == 'https' else _PinnedHTTPConnection
        connection = connection_class(host, port, address, timeout)
        try:
            connection.request(
                'GET',
                target,
                headers={
                    'Accept': 'text/html, text/plain, application/json, application/xml;q=0.9',
                    'Accept-Encoding': 'identity',
                    'Connection': 'close',
                    'User-Agent': 'JARVIS-AI-OMEGA-V7.5-SafeReader/1.0',
                },
            )
            response = connection.getresponse()
            headers = {key.lower(): value for key, value in response.getheaders()}
            content_length = headers.get('content-length', '')
            if content_length.isdigit() and int(content_length) > max_bytes:
                raise ValueError('Web response exceeds the configured size limit.')
            if headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
                raise ValueError('Compressed web responses are not accepted by the safe reader.')
            body = bytearray()
            while True:
                chunk = response.read(min(65536, max_bytes + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise ValueError('Web response exceeds the configured size limit.')
            return response.status, headers, bytes(body)
        except (OSError, http.client.HTTPException) as exc:
            last_error = OSError(str(exc))
        finally:
            connection.close()
    raise last_error or OSError('Unable to connect to the validated public destination.')


def _decode_text(body: bytes, content_type: str) -> str:
    charset = 'utf-8'
    for part in content_type.split(';')[1:]:
        key, _, value = part.strip().partition('=')
        if key.lower() == 'charset' and value.strip():
            charset = value.strip().strip('"\'')[:40]
            break
    try:
        return body.decode(charset, errors='replace')
    except LookupError:
        return body.decode('utf-8', errors='replace')


def fetch_public_text(
    url: str,
    *,
    max_chars: int = 12000,
    max_bytes: int = 2_000_000,
    max_redirects: int = 5,
    timeout: float = 12.0,
) -> str:
    """Fetch public text with DNS pinning and per-hop redirect validation."""
    current = str(url).strip()
    for redirect_count in range(max(0, min(int(max_redirects), 10)) + 1):
        status, headers, body = _request_once(
            current,
            timeout=max(1.0, min(float(timeout), 30.0)),
            max_bytes=max(1024, min(int(max_bytes), 5_000_000)),
        )
        if status in _REDIRECT_STATUSES:
            if redirect_count >= max_redirects:
                raise ValueError('Web redirect limit exceeded.')
            location = headers.get('location', '').strip()
            if not location:
                raise ValueError('Web redirect did not provide a destination.')
            current = urljoin(current, location)
            trust = assess_public_url(current, resolve_dns=True)
            if not trust.allowed:
                raise ValueError('Blocked redirect destination: ' + '; '.join(trust.reasons))
            continue
        if not 200 <= status < 300:
            raise RuntimeError(f'Public web request failed with HTTP {status}.')
        content_type = headers.get('content-type', 'text/plain').lower()
        if not content_type.startswith(_TEXT_CONTENT_TYPES):
            raise ValueError(f'Unsupported web content type: {content_type[:120]}')
        text = _decode_text(body, content_type)
        if 'html' in content_type:
            parser = _HTMLTextExtractor()
            parser.feed(text)
            text = parser.text()
        cap = max(1000, min(int(max_chars), 20000))
        return text[:cap]
    raise ValueError('Web redirect limit exceeded.')


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
    return fetch_public_text(url, max_chars=max_chars)
