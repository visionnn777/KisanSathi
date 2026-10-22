"""Client for the keyless community Mandi Price API.

Provider docs: https://mandi-api.vercel.app/docs
Base URL: https://mandi-api.onrender.com/v1
No API key is required. Data is sourced upstream from data.gov.in, so it can
still be delayed; always retain each row's arrival_date and show freshness.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .. import config

DEFAULT_BASE_URL = "https://mandi-api.onrender.com/v1"
SUPPORTED_STATES = (
    "Maharashtra",
    "Uttar Pradesh",
    "Punjab",
    "Madhya Pradesh",
    "Karnataka",
)


class CommunityMandiAPIError(RuntimeError):
    """A network, HTTP, or response-schema error from the keyless price provider."""


def base_url() -> str:
    return (getattr(config, "MANDI_API_BASE_URL", "") or DEFAULT_BASE_URL).rstrip("/")


def _request_json(path: str, params: dict[str, Any] | None = None, *, session=None,
                  retries: int = 2, timeout: tuple[int, int] = (5, 45)) -> dict:
    http = session or requests
    last_error: Exception | None = None
    url = f"{base_url()}/{path.lstrip('/')}"
    for attempt in range(1, retries + 1):
        try:
            response = http.get(url, params=params or {}, timeout=timeout,
                                headers={"Accept": "application/json", "User-Agent": "KisanSaathi/1.0"})
            if response.status_code == 429:
                raise CommunityMandiAPIError(
                    "Mandi Price API rate limit reached (HTTP 429). Wait before retrying; do not loop requests."
                )
            if response.status_code in (401, 403):
                raise CommunityMandiAPIError(
                    f"Mandi Price API denied access (HTTP {response.status_code}). Check provider status/docs."
                )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise CommunityMandiAPIError("Mandi Price API returned JSON in an unexpected format.")
            if body.get("success") is False:
                raise CommunityMandiAPIError(str(body.get("message") or "Mandi Price API reported failure."))
            return body
        except CommunityMandiAPIError:
            raise
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(attempt)
    raise CommunityMandiAPIError(
        f"Could not reach Mandi Price API after {retries} attempts: {last_error}. "
        "Check internet access and https://mandi-api.vercel.app/status."
    )


def fetch_states(*, session=None) -> list[str]:
    body = _request_json("states", session=session)
    data = body.get("data", body.get("states", []))
    if isinstance(data, dict):
        data = data.get("states", [])
    if not isinstance(data, list):
        raise CommunityMandiAPIError("Mandi Price API states response did not contain a list.")
    states: list[str] = []
    for item in data:
        value = item.get("state") if isinstance(item, dict) else item
        if isinstance(value, str) and value.strip():
            states.append(value.strip())
    # Use the documented allow-list; don't accidentally expose arbitrary data as supported coverage.
    available = {state.casefold(): state for state in states}
    return [available[state.casefold()] for state in SUPPORTED_STATES if state.casefold() in available]


def fetch_prices(*, state: str, commodity: str | None = None,
                 market: str | None = None, session=None) -> list[dict]:
    """Fetch normalized-provider records for one supported state.

    The upstream API currently documents state OR commodity as required input.
    Requesting a state provides state-level coverage; optional commodity/market
    filters reduce the result set. Pagination is not documented by the provider.
    """
    canonical = next((s for s in SUPPORTED_STATES if s.casefold() == state.strip().casefold()), None)
    if canonical is None:
        raise CommunityMandiAPIError(
            f"Unsupported state {state!r}. This provider currently documents: {', '.join(SUPPORTED_STATES)}."
        )
    params: dict[str, str] = {"state": canonical}
    if commodity and commodity.strip():
        params["commodity"] = commodity.strip()
    if market and market.strip():
        params["market"] = market.strip()
    body = _request_json("prices", params=params, session=session)
    data = body.get("data")
    if data is None and isinstance(body.get("records"), list):
        data = body["records"]  # tolerate old provider response envelopes
    if not isinstance(data, list):
        raise CommunityMandiAPIError("Mandi Price API response is missing its data list.")
    records = [row for row in data if isinstance(row, dict)]
    # Empty means no records matching those filters; it is not a zero-priced crop.
    return records


def fetch_price_history(*, state: str, commodity: str, from_date: str, to_date: str, session=None) -> list[dict]:
    """Fetch a state's historical commodity price series from the provider's history endpoint.

    Provider documentation describes this endpoint as a trend series aggregated across
    reporting mandis. It is not a substitute for individual market quotations.
    """
    canonical = next((s for s in SUPPORTED_STATES if s.casefold() == state.strip().casefold()), None)
    if canonical is None:
        raise CommunityMandiAPIError(
            f"Unsupported state {state!r}. This provider currently documents: {', '.join(SUPPORTED_STATES)}."
        )
    commodity = (commodity or "").strip()
    if not commodity:
        raise CommunityMandiAPIError("A commodity is required for historical price retrieval.")
    try:
        from datetime import date
        start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
    except (TypeError, ValueError) as exc:
        raise CommunityMandiAPIError("History dates must be valid ISO dates (YYYY-MM-DD).") from exc
    if start > end:
        raise CommunityMandiAPIError("History start date cannot be after its end date.")
    if (end - start).days > 366 * 6:
        raise CommunityMandiAPIError("A single history request is limited to six years.")

    body = _request_json("prices/history", params={
        "state": canonical, "commodity": commodity,
        "from": start.isoformat(), "to": end.isoformat(),
    }, session=session)
    data = body.get("data")
    if data is None and isinstance(body.get("records"), list):
        data = body["records"]
    if not isinstance(data, list):
        raise CommunityMandiAPIError("Mandi Price API history response is missing its data list.")
    return [row for row in data if isinstance(row, dict)]
