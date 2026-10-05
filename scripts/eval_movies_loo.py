"""Offline leave-one-out movie evaluation using the existing recommender API.

MRR is truncated at K=10, as are HitRate and NDCG. Rating provenance remains
unverified unless the correlation heuristic flags suspected synthetic ratings.
"""

import argparse
import json
import math
from pathlib import Path
import random
import sys

import numpy as np
from sqlalchemy import MetaData, Table, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.import_imdb_ratings import default_database_url, local_engine

K = 10
SEED = 42


def load_catalog(engine):
    movies = Table("movies", MetaData(), autoload_with=engine)
    with engine.connect() as db:
        return [dict(row) for row in db.execute(select(movies)).mappings()]


def rating_correlation(catalog):
    pairs = [(row["personal_rating"], row["vote_average"]) for row in catalog
             if row.get("personal_rating") is not None and row.get("vote_average") is not None]
    if len(pairs) < 2:
        return None
    ratings, votes = np.array(pairs, dtype=float).T
    if not np.isfinite(ratings).all() or not np.isfinite(votes).all():
        raise ValueError("Catalog has non-finite rating or popularity values")
    if np.std(ratings) == 0 or np.std(votes) == 0:
        return None
    return float(np.corrcoef(ratings, votes)[0, 1])


def summarize(ranks, recommended, n_catalog):
    n = len(ranks)
    return {
        "HitRate@10": sum(rank is not None for rank in ranks) / n,
        "NDCG@10": sum(1 / math.log2(rank + 1) for rank in ranks if rank is not None) / n,
        "MRR": sum(1 / rank for rank in ranks if rank is not None) / n,
        "coverage": len(recommended) / n_catalog,
    }


def evaluate(catalog, *, allow_synthetic=False, recommender=None):
    # Sort before sampling/folding so DB row order cannot change the result.
    catalog = sorted(catalog, key=lambda row: str(row["tmdb_id"]))
    ids = [str(row["tmdb_id"]) for row in catalog]
    if len(set(ids)) != len(ids):
        raise ValueError("Catalog contains duplicate TMDB IDs")
    liked = [str(row["tmdb_id"]) for row in catalog
             if row.get("personal_rating") is not None and row["personal_rating"] >= 7]
    if len(liked) < 20:
        raise ValueError(f"Need at least 20 liked movies (personal_rating >= 7.0); found {len(liked)}")
    correlation = rating_correlation(catalog)
    suspected = correlation is not None and correlation > 0.9
    if suspected and not allow_synthetic:
        raise ValueError(f"Ratings look synthetic (Pearson correlation {correlation:.4f} > 0.9). "
                         "Refusing evaluation; use --allow-synthetic to label this explicitly.")
    if recommender is None:
        from services import movie_recommender as recommender
    artifact_ids = {str(mid) for mid in recommender.movie_ids}
    if recommender.tfidf_matrix is None or not set(ids).issubset(artifact_ids):
        raise ValueError("Movie TF-IDF artifacts must cover the full database catalog; rebuild artifacts first")
    # The existing resolver also accepts DB primary keys; detect alias collisions
    # rather than accidentally seeding a different TMDB movie.
    for movie_id in ids:
        index = recommender.movie_id_to_idx.get(movie_id)
        if index is None or str(recommender.movie_ids[index]) != movie_id:
            raise ValueError(f"Movie artifact ID mapping is ambiguous for TMDB ID {movie_id}")
    rng = random.Random(SEED)
    ranks = {name: [] for name in ("model", "random", "popularity")}
    recommended = {name: set() for name in ranks}
    popularity = {str(row["tmdb_id"]): row.get("vote_average") for row in catalog}
    folds = []
    for held_out in liked:
        seeds = [movie_id for movie_id in liked if movie_id != held_out]
        candidates = set(ids) - set(seeds)
        # Request the complete artifact ranking, then restrict to this DB's
        # non-seed catalog; no stale cached personal ratings are auto-seeded.
        recs = recommender.get_taste_vector_recommendations(liked_ids=seeds, n=len(recommender.movie_ids))
        model_ranking = list(dict.fromkeys(str(row["id"]) for row in recs
                                          if str(row["id"]) in candidates))
        if set(model_ranking) != candidates:
            raise ValueError("Recommender did not rank the full non-seed catalog")
        candidate_list = sorted(candidates)
        fold_rankings = {
            "model": model_ranking[:K],
            "random": rng.sample(candidate_list, min(K, len(candidate_list))),
            "popularity": sorted(candidate_list, key=lambda mid: (
                -(popularity[mid] if popularity[mid] is not None else -math.inf), mid))[:K],
        }
        fold = {"held_out": held_out}
        for name, ranking in fold_rankings.items():
            rank = ranking.index(held_out) + 1 if held_out in ranking else None
            ranks[name].append(rank)
            recommended[name].update(ranking)
            fold[name] = rank
        folds.append(fold)
    scores = {name: summarize(ranks[name], recommended[name], len(ids)) for name in ranks}
    result = {
        "metrics": scores["model"],
        "baselines": {name: scores[name] for name in ("random", "popularity")},
        "lift": {name: {metric: {
            "absolute": scores["model"][metric] - scores[name][metric],
            "relative": (scores["model"][metric] / scores[name][metric] - 1)
            if scores[name][metric] else None,
        } for metric in ("HitRate@10", "NDCG@10", "MRR")}
                 for name in ("random", "popularity")},
        "n_liked": len(liked), "n_catalog": len(ids), "k": K, "seed": SEED,
        "rating_source": "synthetic_suspected" if suspected else "unverified",
        "rating_popularity_correlation": correlation, "folds": folds,
        "protocol": "One held-out liked item per fold; MRR truncated at 10; full non-seed catalog",
    }
    if suspected:
        result["caveat"] = "Ratings correlate with popularity above 0.9; results measure suspected synthetic taste."
    else:
        result["caveat"] = "Correlation alone cannot prove real rating provenance; verify the IMDb export before interpretation."
    return result


def write_report(result, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", default=default_database_url(), help="Local SQLite movie database")
    parser.add_argument("--output", default="data/eval/movies_loo.json")
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args(argv)
    engine = None
    try:
        engine = local_engine(args.db_url)
        result = evaluate(load_catalog(engine), allow_synthetic=args.allow_synthetic)
        write_report(result, args.output)
    except ValueError as exc:
        print(f"Evaluation refused: {exc}")
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
