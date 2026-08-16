from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from .vector_memory import hashed_vector, cosine_sparse


TOKEN_RE = re.compile(r'[\w-]{2,}', flags=re.UNICODE)


def tokens(text: str) -> list[str]:
    return [item.lower() for item in TOKEN_RE.findall(str(text))]


class EmbeddingBackend(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAICompatibleEmbeddingBackend:
    """Optional embedding backend; disabled unless explicitly configured.

    It can point to a local or remote OpenAI-compatible embeddings endpoint. V7 does
    not silently send memory to an embedding service.
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        from openai import OpenAI
        self.model = model
        self.client = OpenAI(api_key=api_key or 'local', base_url=base_url or None, max_retries=0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [list(item.embedding) for item in response.data]


def configured_embedding_backend() -> EmbeddingBackend | None:
    model = os.getenv('EMBEDDING_MODEL', '').strip()
    if not model:
        return None
    base_url = os.getenv('EMBEDDING_BASE_URL', '').strip()
    api_key = os.getenv('EMBEDDING_API_KEY', '').strip()
    # External embeddings require an explicitly configured key/base/model. A local
    # server may use a dummy key but still requires an explicit base URL.
    if not base_url:
        return None
    return OpenAICompatibleEmbeddingBackend(base_url, api_key or 'local', model)


def _cosine_dense(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def bm25_scores(query: str, texts: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    q = tokens(query)
    docs = [tokens(text) for text in texts]
    if not q or not docs:
        return [0.0] * len(texts)
    avgdl = sum(len(doc) for doc in docs) / max(1, len(docs))
    doc_freq = Counter()
    for term in set(q):
        doc_freq[term] = sum(1 for doc in docs if term in doc)
    scores = []
    n = len(docs)
    for doc in docs:
        counts = Counter(doc)
        score = 0.0
        dl = len(doc)
        for term in q:
            df = doc_freq[term]
            if not df:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            tf = counts[term]
            denom = tf + k1 * (1 - b + b * dl / max(avgdl, 1.0))
            if denom:
                score += idf * (tf * (k1 + 1)) / denom
        scores.append(score)
    max_score = max(scores, default=0.0) or 1.0
    return [score / max_score for score in scores]


@dataclass
class HybridRetriever:
    embedder: EmbeddingBackend | None = None

    def rank(
        self,
        query: str,
        rows: list[dict],
        *,
        text_key: str = 'content',
        limit: int = 8,
        metadata_filter=None,
    ) -> list[dict]:
        candidates = [row for row in rows if str(row.get(text_key, '')).strip()]
        if metadata_filter:
            candidates = [row for row in candidates if metadata_filter(row)]
        if not candidates:
            return []

        texts = [str(row[text_key]) for row in candidates]
        qterms = set(tokens(query))
        bm25 = bm25_scores(query, texts)
        q_sparse = hashed_vector(query)
        lexical = []
        sparse = []
        for text in texts:
            terms = tokens(text)
            term_set = set(terms)
            lexical.append(len(qterms & term_set) / max(1, len(qterms)))
            sparse.append(max(0.0, cosine_sparse(q_sparse, hashed_vector(text))))

        preliminary = []
        for idx, row in enumerate(candidates):
            confidence = float(row.get('confidence', 0.7) or 0.7)
            importance = float(row.get('importance', 0.5) or 0.5)
            score = 0.28 * lexical[idx] + 0.37 * bm25[idx] + 0.25 * sparse[idx] + 0.06 * confidence + 0.04 * importance
            preliminary.append((score, idx, row))
        preliminary.sort(key=lambda item: item[0], reverse=True)

        # Embeddings are an optional explicit reranker, never a hidden data export.
        embedding_scores: dict[int, float] = {}
        if self.embedder and preliminary:
            top = preliminary[: min(24, len(preliminary))]
            try:
                vectors = self.embedder.embed([query] + [texts[idx] for _, idx, _ in top])
                qvec = vectors[0]
                for (_, idx, _), vec in zip(top, vectors[1:]):
                    embedding_scores[idx] = max(0.0, _cosine_dense(qvec, vec))
            except Exception:
                embedding_scores = {}

        ranked = []
        for base_score, idx, row in preliminary:
            emb = embedding_scores.get(idx)
            final = base_score if emb is None else 0.76 * base_score + 0.24 * emb
            ranked.append((final, row, {
                'keyword_score': round(lexical[idx], 4),
                'bm25_score': round(bm25[idx], 4),
                'sparse_score': round(sparse[idx], 4),
                'embedding_score': round(emb, 4) if emb is not None else None,
                'hybrid_score': round(final, 4),
            }))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [row | scores for _, row, scores in ranked[: max(1, min(int(limit), 30))]]
