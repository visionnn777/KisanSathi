from datetime import date

import pytest

from app.services import community_mandi_api as client


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status_code = status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 429:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append((url, params, timeout, headers))
        return FakeResponse(self.body, self.status)


def test_states_response_is_restricted_to_documented_supported_states():
    session = FakeSession({"success": True, "data": [
        "Punjab", "Unknown State", "Karnataka", "Maharashtra", "Uttar Pradesh", "Madhya Pradesh"
    ]})
    assert client.fetch_states(session=session) == list(client.SUPPORTED_STATES)
    assert session.calls[0][0].endswith("/states")


def test_fetch_prices_returns_records_and_passes_filters():
    body = {"success": True, "data": [{
        "state": "Punjab", "district": "Ludhiana", "market": "Khanna",
        "commodity": "Wheat", "variety": "Dara", "arrival_date": "2026-10-16",
        "min_price": 2400, "max_price": 2550, "modal_price": 2480,
    }]}
    session = FakeSession(body)
    rows = client.fetch_prices(state="punjab", commodity="Wheat", session=session)
    assert rows == body["data"]
    assert session.calls[0][1] == {"state": "Punjab", "commodity": "Wheat"}


def test_fetch_prices_rejects_state_outside_provider_coverage():
    with pytest.raises(client.CommunityMandiAPIError, match="Unsupported state"):
        client.fetch_prices(state="Rajasthan", session=FakeSession({"success": True, "data": []}))


def test_empty_response_is_empty_not_a_fake_zero_price():
    assert client.fetch_prices(state="Punjab", commodity="Wheat",
                               session=FakeSession({"success": True, "data": []})) == []


def test_rate_limit_error_is_exposed_clearly():
    with pytest.raises(client.CommunityMandiAPIError, match="rate limit"):
        client.fetch_prices(state="Punjab", session=FakeSession({}, status=429))
