from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

TOKEN_RE = re.compile(r'[\w-]{2,}', flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def hashed_vector(text: str, dimensions: int = 512) -> dict[int, float]:
    """Create a deterministic sparse hashing vector without external ML dependencies."""
    counts = Counter(tokenize(text))
    vec: dict[int, float] = {}
    for token, count in counts.items():
        digest = hashlib.blake2b(token.encode('utf-8'), digest_size=8).digest()
        raw = int.from_bytes(digest, 'big')
        index = raw % dimensions
        sign = -1.0 if (raw >> 9) & 1 else 1.0
        vec[index] = vec.get(index, 0.0) + sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vec.values())) or 1.0
    return {key: value / norm for key, value in vec.items()}


def cosine_sparse(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(key, 0.0) for key, value in a.items())


def rank_texts(query: str, rows: list[dict], text_key: str = 'content', limit: int = 8) -> list[dict]:
    qvec = hashed_vector(query)
    if not qvec:
        return []
    ranked: list[tuple[float, dict]] = []
    qtokens = set(tokenize(query))
    for row in rows:
        text = str(row.get(text_key, ''))
        if not text:
            continue
        score = cosine_sparse(qvec, hashed_vector(text))
        # Add a small exact-token bonus while keeping vector similarity as the main rank signal.
        tokens = set(tokenize(text))
        overlap = len(qtokens & tokens) / max(1, len(qtokens))
        score += overlap * 0.25
        if score > 0:
            ranked.append((score, row))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [row | {'vector_score': round(score, 4)} for score, row in ranked[:max(1, min(limit, 20))]]
