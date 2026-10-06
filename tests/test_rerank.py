from datetime import datetime, timezone
from types import SimpleNamespace

from services.rerank import rerank


def test_excludes_recently_shown_and_disliked_forever():
    items = [{"id": str(i)} for i in range(8)]
    feedback = [
        SimpleNamespace(item_id="0", action="shown", created_at=datetime(2026, 10, 5, tzinfo=timezone.utc)),
        SimpleNamespace(item_id="1", action="dislike", created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
    ]
    result = rerank(items, list(range(8)), [{i} for i in range(8)], user_id="u", feedback=feedback,
                    k=10, today=datetime(2026, 10, 6, tzinfo=timezone.utc).date())
    assert "0" not in {x["id"] for x in result}
    assert "1" not in {x["id"] for x in result}


def test_same_day_impressions_preserve_daily_stability():
    items = [{"id": "0"}, {"id": "1"}]
    today = datetime(2026, 10, 6, tzinfo=timezone.utc).date()
    feedback = [SimpleNamespace(item_id="0", action="shown",
                                created_at=datetime(2026, 10, 6, 1, tzinfo=timezone.utc))]
    result = rerank(items, [1, 0], [{"a"}, {"b"}], user_id="u", feedback=feedback, k=2, today=today)
    assert {x["id"] for x in result} == {"0", "1"}


def test_mmr_introduces_feature_diversity():
    items = [{"id": str(i)} for i in range(5)]
    vectors = [{"shared", "a"}, {"shared", "a"}, {"shared", "a"}, {"other"}, {"third"}]
    result = rerank(items, [1, .7, .69, .65, .6], vectors, user_id="u", k=3,
                    today=datetime(2026, 10, 6, tzinfo=timezone.utc).date())
    assert len(set(x["id"] for x in result)) == 3
    assert any(x["id"] in {"3", "4"} for x in result[1:])


def test_seed_is_stable_same_day_and_rotates_next_day():
    items = [{"id": str(i)} for i in range(60)]
    vectors = [{str(i)} for i in range(60)]
    scores = [1.0] * len(items)
    first = rerank(items, scores, vectors, user_id="u", k=10, today="2026-10-06")
    same_day = rerank(items, scores, vectors, user_id="u", k=10, today="2026-10-06")
    next_day = rerank(items, scores, vectors, user_id="u", k=10, today="2026-10-07")
    assert [x["id"] for x in first] == [x["id"] for x in same_day]
    assert len(set(x["id"] for x in first) ^ set(x["id"] for x in next_day)) >= 6
