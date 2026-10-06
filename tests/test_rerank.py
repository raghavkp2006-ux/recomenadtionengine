from datetime import datetime, timezone
from types import SimpleNamespace

from services.rerank import rerank


def test_excludes_recently_shown_and_disliked_forever():
    items = [{"id": str(i)} for i in range(8)]
    feedback = [
        SimpleNamespace(item_id="7", action="shown", created_at=datetime.now(timezone.utc)),
        SimpleNamespace(item_id="1", action="dislike", created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
    ]
    result = rerank(items, list(range(8)), [{i} for i in range(8)], user_id="u", feedback=feedback,
                    k=10)
    by_id = {x["id"]: x for x in result}
    assert "1" not in by_id
    assert by_id["7"]["score"] < 1.0


def test_mmr_introduces_feature_diversity():
    items = [{"id": str(i)} for i in range(5)]
    vectors = [{"shared", "a"}, {"shared", "a"}, {"shared", "a"}, {"other"}, {"third"}]
    result = rerank(items, [1, .7, .69, .65, .6], vectors, user_id="u", k=5)
    assert len(set(x["id"] for x in result)) == 5
    assert any(x["id"] in {"3", "4"} for x in result[1:])


def test_request_level_sampling_rotates_with_impressions():
    items = [{"id": str(i)} for i in range(60)]
    vectors = [{str(i)} for i in range(60)]
    scores = [1.0] * len(items)
    feedback = []
    all_seen = set()
    for _ in range(5):
        result = rerank(items, scores, vectors, user_id="u", feedback=feedback, k=10)
        all_seen.update(item["id"] for item in result)
        shown_at = datetime.now(timezone.utc)
        feedback.extend(SimpleNamespace(item_id=item["id"], action="shown", created_at=shown_at)
                        for item in result)
    assert len(all_seen) >= 25
