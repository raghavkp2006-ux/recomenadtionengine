"""Feedback-aware, deterministic-within-day recommendation reranking."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import numpy as np


def normalize_scores(scores: Sequence[float]) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    if not len(values):
        return values
    low, high = float(np.min(values)), float(np.max(values))
    return np.zeros_like(values) if high <= low else (values - low) / (high - low)


def rerank(candidates: Sequence[Mapping[str, Any]], scores: Sequence[float], vectors: Sequence[Any],
           *, user_id: str, feedback: Sequence[Any] = (), k: int = 10,
           today: Any = None) -> list[dict[str, Any]]:
    """Min-max normalize, exclude recent shown/disliked items, and apply MMR.

    Candidate vectors can be dense/sparse numeric arrays or sets of feature tokens.
    Feedback rows need item_id, action, created_at attributes.
    """
    day = today or datetime.now(timezone.utc).date()
    if isinstance(day, str):
        day = datetime.fromisoformat(day).date()
    now = datetime.combine(day, datetime.min.time(), timezone.utc) if not isinstance(day, datetime) else day
    cutoff = now - timedelta(days=7)
    disliked = {str(row.item_id) for row in feedback if row.action == "dislike"}
    def recent(ts: Any) -> bool:
        if not ts:
            return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts >= cutoff
    # Preserve a stable daily list on repeated fetches; impressions from prior
    # days still suppress repeats for the rest of the seven-day window. A skip
    # is an explicit same-day exclusion and does not wait for the next day.
    seen = {str(row.item_id) for row in feedback
            if ((row.action == "shown" and recent(row.created_at)
                and row.created_at.date() < now.date())
                or (row.action == "skip" and recent(row.created_at)))}
    liked = {str(row.item_id) for row in feedback if row.action == "like"}

    def dense(value: Any) -> np.ndarray:
        if isinstance(value, set):
            return value
        if hasattr(value, "toarray"):
            return np.asarray(value.toarray()).ravel().astype(float)
        return np.asarray(value, dtype=float).ravel()

    def cosine(a: Any, b: Any) -> float:
        a, b = dense(a), dense(b)
        if isinstance(a, set) or isinstance(b, set):
            aa, bb = set(a), set(b)
            return len(aa & bb) / max((len(aa) * len(bb)) ** 0.5, 1e-9)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom else 0.0

    base = normalize_scores(scores)
    lookup = {str(c.get("id")): i for i, c in enumerate(candidates)}
    positive = [vectors[lookup[x]] for x in liked if x in lookup]
    negative = [vectors[lookup[str(r.item_id)]] for r in feedback
                if r.action == "dislike" and str(r.item_id) in lookup]
    adjusted = base.copy()
    for i, vec in enumerate(vectors):
        if positive:
            adjusted[i] += 0.12 * max(cosine(vec, x) for x in positive)
        if negative:
            adjusted[i] -= 0.07 * max(cosine(vec, x) for x in negative)

    pool = [i for i, c in enumerate(candidates) if str(c.get("id")) not in seen | disliked]
    pool.sort(key=lambda i: adjusted[i], reverse=True)
    pool = pool[:40]
    seed = int(hashlib.sha256(f"{user_id}:{day}".encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    jitter = rng.uniform(0, 0.015, len(candidates))
    chosen: list[int] = []
    while pool and len(chosen) < k:
        best = max(pool, key=lambda i: 0.7 * adjusted[i] - 0.3 * max((cosine(vectors[i], vectors[j]) for j in chosen), default=0.0) + jitter[i])
        pool.remove(best)
        chosen.append(best)
    result = []
    for i in chosen:
        item = dict(candidates[i])
        item["score"] = round(float(np.clip(adjusted[i], 0, 1)), 4)
        result.append(item)
    return result
