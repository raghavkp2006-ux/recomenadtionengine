from services import myntra_rate_limit


def test_rate_limiter_rejects_requests_after_its_configured_window_capacity():
    myntra_rate_limit._requests.clear()
    user_id = "rate-limit-test"
    assert all(myntra_rate_limit.allow(user_id) for _ in range(myntra_rate_limit.MAX_REQUESTS))
    assert myntra_rate_limit.allow(user_id) is False
