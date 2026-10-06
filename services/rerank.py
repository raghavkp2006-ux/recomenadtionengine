"""Exposure-aware sampled recommendations with MMR diversity."""
from __future__ import annotations

import os
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
           temperature: float = 0.15) -> list[dict[str, Any]]:
    """Penalize recent exposures, sample from the top 60, then apply MMR.

    Candidate vectors can be dense/sparse numeric arrays or sets of feature tokens.
    Feedback rows need item_id, action, created_at attributes.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    disliked = {str(row.item_id) for row in feedback if row.action == "dislike"}
    exposures: dict[str, list[datetime]] = {}
    for row in feedback:
        if row.action != "shown" or not row.created_at:
            continue
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created >= cutoff:
            exposures.setdefault(str(row.item_id), []).append(created)

    # Each response writes its impressions with one timestamp, grouping them
    # into a request for the exposure penalty.
    request_times = sorted({ts for timestamps in exposures.values() for ts in timestamps}, reverse=True)
    request_ranks = {timestamp: rank for rank, timestamp in enumerate(request_times)}
    penalties: dict[str, float] = {}
    for item_id, timestamps in exposures.items():
        latest = max(timestamps)
        age = (now - latest).total_seconds()
        rank = request_ranks[latest]
        factor = 1.0 if rank == 0 else (0.6 if rank <= 2 else 0.3)
        if age <= 24 * 60 * 60:
            penalties[item_id] = 0.35 * factor

    liked = {str(row.item_id) for row in feedback if row.action == "like"}

    def dense(value: Any) -> Any:
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
    negative = [vectors[lookup[str(row.item_id)]] for row in feedback
                if row.action == "dislike" and str(row.item_id) in lookup]
    adjusted = base.copy()
    for i, (candidate, vector) in enumerate(zip(candidates, vectors)):
        item_id = str(candidate.get("id"))
        adjusted[i] -= penalties.get(item_id, 0.0)
        if positive:
            adjusted[i] += 0.45 * max(cosine(vector, liked_vector) for liked_vector in positive)
        if negative:
            adjusted[i] -= 0.07 * max(cosine(vector, disliked_vector) for disliked_vector in negative)

    pool = [i for i, item in enumerate(candidates) if str(item.get("id")) not in disliked | liked]
    pool.sort(key=lambda i: adjusted[i], reverse=True)
    pool = pool[:60]
    if not pool:
        return []

    # Gumbel top-k samples without replacement from softmax(score / T).
    logits = np.asarray([adjusted[i] for i in pool], dtype=float) / max(temperature, 1e-6)
    logits -= np.max(logits)
    rng = np.random.default_rng(int.from_bytes(os.urandom(16), "big"))
    uniforms = np.clip(rng.random(len(pool)), 1e-12, 1.0 - 1e-12)
    gumbel = -np.log(-np.log(uniforms))
    sample_positions = np.argsort(-(logits + gumbel))[:min(k, len(pool))]
    sampled = [pool[int(position)] for position in sample_positions]

    # MMR diversity (lambda 0.7) reorders only the sampled slate.
    chosen: list[int] = []
    while sampled:
        best = max(sampled, key=lambda i: 0.7 * adjusted[i] - 0.3 * max(
            (cosine(vectors[i], vectors[j]) for j in chosen), default=0.0))
        sampled.remove(best)
        chosen.append(best)

    result = []
    for i in chosen:
        item = dict(candidates[i])
        item["score"] = round(float(np.clip(adjusted[i], 0, 1)), 4)
        result.append(item)
    return result
