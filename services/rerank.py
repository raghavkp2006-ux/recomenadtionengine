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
           temperature: float = 0.15, controls: Any = None) -> list[dict[str, Any]]:
    """Penalize recent exposures, sample from the top 60, then apply MMR.

    Candidate vectors can be dense/sparse numeric arrays or sets of feature tokens.
    Feedback rows need item_id, action, created_at attributes.
    Optionally applies controls (pinned boost, hidden filtering, novelty-mapped MMR lambda).
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
    # Parse controls parameters if provided
    pinned_artists: set[str] = set()
    pinned_genres: set[str] = set()
    hidden_artists: set[str] = set()
    hidden_genres: set[str] = set()
    mmr_lambda = 0.7

    if controls is not None:
        if hasattr(controls, "get_pinned"):
            p = controls.get_pinned()
            pinned_artists = {str(x).lower() for x in p.get("artists", [])}
            pinned_genres = {str(x).lower() for x in p.get("genres", [])}
        elif isinstance(controls, dict) and "pinned" in controls:
            pinned_artists = {str(x).lower() for x in controls["pinned"].get("artists", [])}
            pinned_genres = {str(x).lower() for x in controls["pinned"].get("genres", [])}

        if hasattr(controls, "get_hidden"):
            h = controls.get_hidden()
            hidden_artists = {str(x).lower() for x in h.get("artists", [])}
            hidden_genres = {str(x).lower() for x in h.get("genres", [])}
        elif isinstance(controls, dict) and "hidden" in controls:
            hidden_artists = {str(x).lower() for x in controls["hidden"].get("artists", [])}
            hidden_genres = {str(x).lower() for x in controls["hidden"].get("genres", [])}

        if hasattr(controls, "get_sliders"):
            sliders = controls.get_sliders()
            # novelty 0 -> lambda 0.9 (relevance heavy), novelty 100 -> lambda 0.3 (diversity heavy)
            novelty = float(sliders.get("novelty", 50))
            mmr_lambda = max(0.2, min(0.9, 0.9 - (novelty / 100.0) * 0.6))
        elif isinstance(controls, dict) and "sliders" in controls:
            novelty = float(controls["sliders"].get("novelty", 50))
            mmr_lambda = max(0.2, min(0.9, 0.9 - (novelty / 100.0) * 0.6))

    # Apply pinned boost to raw scores before normalization if present
    mod_scores = list(scores)
    for i, candidate in enumerate(candidates):
        cand_artists = [str(a).lower() for a in candidate.get("artists", [])]
        cand_genres = [str(g).lower() for g in candidate.get("genres", [])]
        if any(a in pinned_artists for a in cand_artists) or any(g in pinned_genres for g in cand_genres):
            mod_scores[i] += 0.25

    base = normalize_scores(mod_scores)
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

        cand_artists = [str(a).lower() for a in candidate.get("artists", [])]
        cand_genres = [str(g).lower() for g in candidate.get("genres", [])]
        if any(a in pinned_artists for a in cand_artists) or any(g in pinned_genres for g in cand_genres):
            adjusted[i] += 0.25

    # Filter out disliked, liked, and hidden artists/genres
    def is_hidden(c: Mapping[str, Any]) -> bool:
        if not hidden_artists and not hidden_genres:
            return False
        c_artists = [str(a).lower() for a in c.get("artists", [])]
        c_genres = [str(g).lower() for g in c.get("genres", [])]
        return any(a in hidden_artists for a in c_artists) or any(g in hidden_genres for g in c_genres)

    pool = [i for i, item in enumerate(candidates) if str(item.get("id")) not in disliked | liked and not is_hidden(item)]
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

    # MMR diversity with novelty-mapped lambda reorders the sampled slate.
    chosen: list[int] = []
    while sampled:
        best = max(sampled, key=lambda i: mmr_lambda * adjusted[i] - (1.0 - mmr_lambda) * max(
            (cosine(vectors[i], vectors[j]) for j in chosen), default=0.0))
        sampled.remove(best)
        chosen.append(best)

    result = []
    for i in chosen:
        item = dict(candidates[i])
        item["score"] = round(float(np.clip(adjusted[i], 0, 1)), 4)
        result.append(item)
    return result
