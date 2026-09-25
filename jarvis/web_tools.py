from __future__ import annotations

import http.client
import re
import socket
import ssl
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from ddgs import DDGS

from .computer_use.browser_security import assess_public_url, resolve_public_addresses


_MAX_REDIRECTS = 5
_MAX_RESPONSE_BYTES = 1_000_000
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_USER_AGENT = 'JARVIS-AI-OMEGA/8 public-reader'


class _HTMLTextExtractor(HTMLParser):
    _BLOCKED = {'script', 'style', 'noscript', 'template'}
    _BREAKS = {'p', 'div', 'br', 'li', 'tr', 'section', 'article', 'header', 'footer', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in self._BLOCKED:
            self._blocked_depth += 1
        elif self._blocked_depth == 0 and lowered in self._BREAKS:
            self.parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self._BLOCKED:
            self._blocked_depth = max(0, self._blocked_depth - 1)
        elif self._blocked_depth == 0 and lowered in self._BREAKS:
            self.parts.append('\n')

    def handle_data(self, data: str) -> None:
        if self._blocked_depth == 0 and data:
            self.parts.append(data)

    def text(self) -> str:
        joined = unescape(''.join(self.parts)).replace('\r', '\n')
        lines = [' '.join(line.split()) for line in joined.split('\n')]
        return '\n'.join(line for line in lines if line).strip()


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, connect_address: str, family: int, port: int, *, timeout: float) -> None:
        self._connect_address = connect_address
        self._family = family
        super().__init__(host=host, port=port, timeout=timeout)

    def connect(self) -> None:
        sock = socket.socket(self._family, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect((self._connect_address, self.port))
            self.sock = sock
            if self._tunnel_host:
                self._tunnel()
        except Exception:
            sock.close()
            raise


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, connect_address: str, family: int, port: int, *, timeout: float) -> None:
        self._connect_address = connect_address
        self._family = family
        super().__init__(host=host, port=port, timeout=timeout, context=ssl.create_default_context())

    def connect(self) -> None:
        sock = socket.socket(self._family, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect((self._connect_address, self.port))
            if self._tunnel_host:
                self.sock = sock
                self._tunnel()
                sock = self.sock
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _clean_result(item: dict) -> dict:
    return {
        'title': str(item.get('title') or '').strip(),
        'url': str(item.get('href') or item.get('url') or '').strip(),
        'snippet': str(item.get('body') or item.get('description') or '').strip(),
        'source': str(item.get('source') or '').strip(),
        'date': str(item.get('date') or '').strip(),
    }


def _validated_endpoint(url: str):
    trust = assess_public_url(url, resolve_dns=False)
    if not trust.allowed:
        raise ValueError('; '.join(trust.reasons))
    parsed = urlparse(str(url).strip())
    host = str(parsed.hostname or '').strip().lower().rstrip('.')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    endpoints = resolve_public_addresses(host, port)
    return parsed, endpoints


def _public_url(url: str):
    """Compatibility validator used by existing callers and adversarial tests."""
    parsed, _endpoints = _validated_endpoint(url)
    return parsed


def _request_once(parsed, endpoint: tuple[int, str], *, timeout: float, max_bytes: int):
    family, address = endpoint
    host = str(parsed.hostname or '')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    target = parsed.path or '/'
    if parsed.params:
        target += ';' + parsed.params
    if parsed.query:
        target += '?' + parsed.query

    connection_cls = _PinnedHTTPSConnection if parsed.scheme == 'https' else _PinnedHTTPConnection
    connection = connection_cls(host, address, family, port, timeout=timeout)
    response = None
    try:
        connection.request(
            'GET',
            target,
            headers={
                'User-Agent': _USER_AGENT,
                'Accept': 'text/html,text/plain,application/xhtml+xml,application/json,application/xml;q=0.9,*/*;q=0.1',
                'Accept-Encoding': 'identity',
                'Connection': 'close',
            },
        )
        response = connection.getresponse()
        headers = {str(key).lower(): str(value) for key, value in response.getheaders()}
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError('Public page response exceeded the bounded reader limit.')
        return int(response.status), headers, body
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        connection.close()


def _decode_body(body: bytes, content_type: str) -> str:
    charset = 'utf-8'
    match = re.search(r'charset\s*=\s*["\']?([^;"\'\s]+)', content_type, re.I)
    if match:
        charset = match.group(1).strip()
    try:
        return body.decode(charset, errors='replace')
    except LookupError:
        return body.decode('utf-8', errors='replace')


def _plain_text(body: bytes, content_type: str) -> str:
    lowered = content_type.lower()
    if lowered and not (
        lowered.startswith('text/')
        or 'application/json' in lowered
        or 'application/xml' in lowered
        or 'application/xhtml+xml' in lowered
    ):
        raise ValueError(f'Unsupported public page content type: {content_type}')
    decoded = _decode_body(body, content_type)
    if 'html' not in lowered and 'xhtml' not in lowered:
        return decoded.strip()
    parser = _HTMLTextExtractor()
    parser.feed(decoded)
    parser.close()
    return parser.text()


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
    """Fetch public page text through a DNS/redirect-safe, address-pinned reader.

    Each hop is independently validated. Every DNS answer must be public, the socket
    connects to the already validated numeric address, HTTPS still verifies the original
    hostname via SNI/certificate validation, and redirects back to private/local networks
    are rejected before another request can be sent.
    """
    cap = max(1000, min(int(max_chars), 20000))
    byte_cap = min(_MAX_RESPONSE_BYTES, max(64_000, cap * 12))
    current = str(url).strip()

    for redirect_count in range(_MAX_REDIRECTS + 1):
        parsed, endpoints = _validated_endpoint(current)
        # Use one validated endpoint for this request. Because mixed public/private DNS
        # answers fail closed, choosing the first remaining endpoint cannot bypass policy.
        status, headers, body = _request_once(parsed, endpoints[0], timeout=12.0, max_bytes=byte_cap)

        if status in _REDIRECT_STATUSES:
            if redirect_count >= _MAX_REDIRECTS:
                raise ValueError('Public page exceeded the redirect limit.')
            location = str(headers.get('location') or '').strip()
            if not location:
                raise ValueError('Redirect response did not provide a Location header.')
            next_url = urljoin(current, location)
            next_parsed = urlparse(next_url)
            if parsed.scheme == 'https' and next_parsed.scheme == 'http':
                raise ValueError('HTTPS-to-HTTP redirect downgrade is blocked.')
            # The next loop validates DNS and pins the next hop before making a request.
            current = next_url
            continue

        if status < 200 or status >= 300:
            raise OSError(f'Public page request failed with HTTP {status}.')

        content_type = str(headers.get('content-type') or '')
        text = _plain_text(body, content_type)
        return text[:cap]

    raise ValueError('Public page redirect processing failed closed.')
