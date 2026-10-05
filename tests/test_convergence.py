import pytest

from services.taste_profile import compute_convergence


CASES = [
    ("empty", {}, 0),
    ("single", {"breakdown": {"spotify": {"rock": 2}}}, 10),
    ("two_agree", {"breakdown": {"spotify": {"rock": 2}, "anime": {"action": 3}},
                   "crosswalk_anime": {"action": 2}}, 80),
    ("two_disagree", {"breakdown": {"spotify": {"rock": 2}, "anime": {"romance": 3}},
                      "crosswalk_anime": {"action": 2}}, 20),
    ("three_agree", {"breakdown": {"spotify": {"rock": 2}, "anime": {"action": 3},
                                  "movie": {"Action": 4}},
                     "crosswalk_anime": {"action": 2}, "crosswalk_movie": {"Action": 2}}, 90),
]


@pytest.mark.parametrize("name,profile,expected", CASES, ids=[case[0] for case in CASES])
def test_score_table(name, profile, expected):
    score = compute_convergence(profile)["score"]
    print(f"{name}: score={score}, expected={expected}")
    assert score == expected


def test_scores_monotonic():
    scores = {name: compute_convergence(profile)["score"] for name, profile, _ in CASES}
    assert scores["three_agree"] > scores["two_agree"] > scores["two_disagree"] > scores["single"] > scores["empty"]


def empty_myntra_profile():
    # Exact no-activity shape emitted by services.myntra_profile.rebuild_profile.
    return {**{name: {} for name in ("brands", "categories", "subcategories", "colours", "styles",
                                   "fits", "materials", "preferred_sizes", "occasions")},
            "price_range": {"min": None, "median": None, "max": None},
            "recent_interests": [], "strong_positive_signals": [], "negative_signals": []}


def test_empty_structured_myntra_has_no_coverage():
    score = compute_convergence({"breakdown": {"myntra": empty_myntra_profile()}})["score"]
    print(f"empty_structured_myntra: score={score}, expected=0")
    assert score == 0


def test_movie_and_empty_myntra_reproduces_constant_twenty():
    profile = {"breakdown": {"movie": {"Action": 2}, "myntra": empty_myntra_profile()},
               "crosswalk_movie": {"Action": 0, "Drama": 0}}
    score = compute_convergence(profile)["score"]
    print(f"movie_and_empty_myntra: score={score}, expected=10")
    assert score == 10


def test_zero_weight_domains_have_no_signal():
    score = compute_convergence({"breakdown": {"spotify": {"rock": 0}, "anime": {"action": 0}}})["score"]
    print(f"zero_weight_domains: score={score}, expected=0")
    assert score == 0


def test_real_structured_myntra_counts_once():
    myntra = empty_myntra_profile()
    myntra["categories"] = {"shirts": 2}
    assert compute_convergence({"breakdown": {"myntra": myntra}})["score"] == 10


def test_anilist_and_anime_are_one_domain():
    profile = {"breakdown": {"anime": {"action": 1}, "anilist": {"action": 2}}}
    assert compute_convergence(profile)["score"] == 10
