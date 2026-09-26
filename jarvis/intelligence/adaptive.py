"""Small privacy-conscious online intent model for local route selection.

This is deliberately not marketed as an LLM.  It is a bounded multinomial
classifier that learns successful routing vocabulary without storing prompts or
plain-text tokens.  The expensive neural/LLM work remains in the later layers.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path

from ..security.secrets import contains_secret


ROUTE_CATEGORIES = ('FAST', 'SMART', 'CODING', 'PLANNING', 'REVIEW', 'SUMMARY')
_TOKEN_RE = re.compile(r"[^\W_][\w'-]{1,31}", flags=re.UNICODE)
_STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'for', 'from', 'i', 'in', 'is',
    'it', 'me', 'my', 'of', 'on', 'or', 'please', 'the', 'this', 'to', 'with',
    'hai', 'hain', 'ho', 'ka', 'ke', 'ki', 'ko', 'karo', 'karna', 'mera',
    'mere', 'mujhe', 'aur', 'ye', 'yr', 'yaar', 'jarvis', 'friday',
}

_SEED_EXAMPLES = {
    'FAST': (
        'hello good morning simple answer time date weather',
        'who are you tell me a joke short reply',
        'namaste kaise ho aaj mausam time batao',
        'open app volume media quick command',
    ),
    'SMART': (
        'analyze compare explain why research architecture advanced problem',
        'deep reasoning investigate evidence tradeoff complex decision',
        'samjhao kyon vishleshan detail gehra analysis',
        'security reliability performance root cause diagnosis',
    ),
    'CODING': (
        'code coding python javascript function class repository refactor',
        'debug bug error traceback tests implementation software project',
        'github repo pipeline build deploy package installer',
        'code banao bug thik karo project update test chalao',
    ),
    'PLANNING': (
        'plan roadmap strategy steps schedule mission milestones',
        'organize sequence checklist timeline priority execution',
        'pahla dusra teesra step yojana roadmap banao',
        'launch plan project phases requirements dependencies',
    ),
    'REVIEW': (
        'review verify validate audit inspect check result quality',
        'critique evidence regression acceptance correctness',
        'dobara check kami galti audit verification',
        'security review test report release gate',
    ),
    'SUMMARY': (
        'summarize summary recap shorten brief key points',
        'condense digest overview highlights notes',
        'short me batao saar summary banao',
        'conversation recap executive summary',
    ),
}


def _tokens(text: str) -> list[str]:
    output: list[str] = []
    for item in _TOKEN_RE.findall(str(text).lower()):
        token = item.strip("'-")
        if token and token not in _STOP_WORDS and not token.isdigit():
            output.append(token)
        if len(output) >= 64:
            break
    return output


def _fingerprint(token: str) -> str:
    return hashlib.blake2b(
        token.encode('utf-8', errors='ignore'),
        digest_size=10,
        person=b'JARVIS-ML',
    ).hexdigest()


@dataclass(frozen=True)
class MLPrediction:
    category: str
    confidence: float
    distribution: dict[str, float]
    matched_features: int
    learned_observations: int

    def as_dict(self) -> dict:
        return asdict(self)


class AdaptiveIntentModel:
    """Bounded online multinomial classifier with no raw-prompt persistence."""

    SCHEMA = 1
    MAX_FILE_BYTES = 8 * 1024 * 1024
    MAX_FEATURES_PER_CATEGORY = 4096

    def __init__(self, path: Path, *, enabled: bool = True, max_observations: int = 5000) -> None:
        self.path = Path(path)
        self.enabled = bool(enabled)
        self.max_observations = max(100, min(int(max_observations), 50_000))
        self._lock = threading.RLock()
        self.load_error = ''
        self._learned = self._empty()
        self._load()
        self._seed_counts, self._seed_docs = self._build_seed_counts()

    @staticmethod
    def _empty() -> dict:
        return {
            'schema': AdaptiveIntentModel.SCHEMA,
            'observations': 0,
            'categories': {
                category: {'documents': 0, 'tokens': {}}
                for category in ROUTE_CATEGORIES
            },
        }

    @staticmethod
    def _build_seed_counts() -> tuple[dict[str, Counter], dict[str, int]]:
        counts: dict[str, Counter] = {}
        documents: dict[str, int] = {}
        for category, examples in _SEED_EXAMPLES.items():
            counter: Counter = Counter()
            for example in examples:
                counter.update(_fingerprint(token) for token in _tokens(example))
            counts[category] = counter
            documents[category] = len(examples)
        return counts, documents

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            if self.path.stat().st_size > self.MAX_FILE_BYTES:
                raise ValueError('adaptive model exceeds the safe size limit')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema') != self.SCHEMA:
                raise ValueError('unsupported schema')
            clean = self._empty()
            clean['observations'] = max(0, min(int(data.get('observations') or 0), self.max_observations))
            incoming = data.get('categories')
            if not isinstance(incoming, dict):
                raise ValueError('categories missing')
            for category in ROUTE_CATEGORIES:
                row = incoming.get(category, {})
                if not isinstance(row, dict):
                    continue
                clean_row = clean['categories'][category]
                clean_row['documents'] = max(0, min(int(row.get('documents') or 0), self.max_observations))
                token_rows = row.get('tokens', {})
                if not isinstance(token_rows, dict):
                    continue
                clean_tokens = {
                    key: max(1, min(int(value), 255))
                    for key, value in token_rows.items()
                    if isinstance(key, str) and re.fullmatch(r'[0-9a-f]{20}', key)
                    and isinstance(value, int) and value > 0
                }
                clean_row['tokens'] = dict(sorted(
                    clean_tokens.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:self.MAX_FEATURES_PER_CATEGORY])
            self._learned = clean
        except Exception as exc:
            self.load_error = f'{type(exc).__name__}: {exc}'
            self._learned = self._empty()

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._learned, ensure_ascii=True, indent=2, sort_keys=True) + '\n'
        temp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=self.path.parent,
                prefix=f'.{self.path.name}.',
                suffix='.tmp',
                delete=False,
            ) as handle:
                temp = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                temp.chmod(0o600)
            except OSError:
                pass
            temp.replace(self.path)
            try:
                self.path.chmod(0o600)
            except OSError:
                pass
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def _combined(self) -> tuple[dict[str, Counter], dict[str, int]]:
        counts: dict[str, Counter] = {}
        docs: dict[str, int] = {}
        for category in ROUTE_CATEGORIES:
            learned = self._learned['categories'][category]
            counts[category] = self._seed_counts[category] + Counter(learned['tokens'])
            docs[category] = self._seed_docs[category] + int(learned['documents'])
        return counts, docs

    def predict(self, text: str) -> MLPrediction:
        if not self.enabled:
            return MLPrediction('FAST', 0.0, {category: 0.0 for category in ROUTE_CATEGORIES}, 0, self.observations)
        features = [_fingerprint(token) for token in _tokens(text)]
        if not features:
            return MLPrediction('FAST', 0.5, {'FAST': 1.0}, 0, self.observations)

        with self._lock:
            counts, documents = self._combined()
            vocabulary = set().union(*(set(counter) for counter in counts.values()))
            matched = [item for item in features if item in vocabulary]
            if not matched:
                return MLPrediction('FAST', 0.5, {'FAST': 1.0}, 0, self.observations)
            total_docs = sum(documents.values())
            vocab_size = max(1, len(vocabulary))
            scores: dict[str, float] = {}
            for category in ROUTE_CATEGORIES:
                counter = counts[category]
                total_tokens = sum(counter.values())
                score = math.log((documents[category] + 1) / (total_docs + len(ROUTE_CATEGORIES)))
                for feature in matched:
                    score += math.log((counter.get(feature, 0) + 1) / (total_tokens + vocab_size))
                scores[category] = score

        high = max(scores.values())
        exp_scores = {category: math.exp(value - high) for category, value in scores.items()}
        total = sum(exp_scores.values()) or 1.0
        distribution = {category: round(value / total, 6) for category, value in exp_scores.items()}
        category = max(distribution, key=distribution.get)
        return MLPrediction(
            category,
            float(distribution[category]),
            distribution,
            len(matched),
            self.observations,
        )

    @property
    def observations(self) -> int:
        return int(self._learned.get('observations') or 0)

    def learn(self, text: str, category: str, *, success: bool) -> bool:
        category = str(category or '').upper()
        if not self.enabled or not success or category not in ROUTE_CATEGORIES:
            return False
        value = str(text or '')
        if not value or len(value) > 4000 or contains_secret(value):
            return False
        features = Counter(_fingerprint(token) for token in _tokens(value))
        if not features:
            return False
        with self._lock:
            before = deepcopy(self._learned)
            if self.observations >= self.max_observations:
                for row in self._learned['categories'].values():
                    row['documents'] = max(0, int(row['documents']) // 2)
                    row['tokens'] = {
                        key: count // 2 for key, count in row['tokens'].items() if count // 2 > 0
                    }
                self._learned['observations'] = self.observations // 2
            row = self._learned['categories'][category]
            row['documents'] = int(row['documents']) + 1
            for feature, count in features.items():
                row['tokens'][feature] = min(255, int(row['tokens'].get(feature, 0)) + min(count, 3))
            if len(row['tokens']) > self.MAX_FEATURES_PER_CATEGORY:
                row['tokens'] = dict(sorted(
                    row['tokens'].items(),
                    key=lambda item: (-item[1], item[0]),
                )[:self.MAX_FEATURES_PER_CATEGORY])
            self._learned['observations'] = self.observations + 1
            try:
                self._persist()
            except OSError:
                self._learned = before
                return False
            self.load_error = ''
        return True

    def reset(self) -> None:
        with self._lock:
            self._learned = self._empty()
            self.load_error = ''
            self.path.unlink(missing_ok=True)
            self.path.with_suffix(self.path.suffix + '.tmp').unlink(missing_ok=True)

    def stats(self) -> dict:
        with self._lock:
            return {
                'enabled': self.enabled,
                'observations': self.observations,
                'stored_feature_hashes': sum(
                    len(row['tokens']) for row in self._learned['categories'].values()
                ),
                'raw_prompts_stored': False,
                'load_error': self.load_error,
            }
