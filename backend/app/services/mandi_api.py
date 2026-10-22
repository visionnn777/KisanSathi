"""Downloads daily mandi prices from the Government of India Open Data API (data.gov.in).

Owner: Member C

Dataset: "Current Daily Price of Various Commodities from Various Markets (Mandi)"
Resource ID: 9ef84268-d588-465a-a308-a864a43d0070
Prices are in Rs per quintal (1 quintal = 100 kg).

DATA YOU MUST PROVIDE: your free API key in backend/.env as DATA_GOV_API_KEY
(sign up at data.gov.in, then My Account -> API key).
"""
import time

import requests

from .. import config

BASE_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"


class MandiAPIError(Exception):
    pass


def api_key() -> str:
    key = config.DATA_GOV_API_KEY
    if not key or key == config.PLACEHOLDER_API_KEY:
        raise MandiAPIError(
            "DATA_GOV_API_KEY is not set. Put your data.gov.in key in backend/.env "
            "(replace YOUR_DATA_GOV_IN_API_KEY)."
        )
    return key


def fetch_page(offset: int = 0, limit: int = 1000, filters: dict | None = None,
               retries: int = 3, session=None) -> dict:
    """One page of records. Retries a few times because the API is sometimes slow."""
    http = session or requests
    params = {"api-key": api_key(), "format": "json", "limit": limit, "offset": offset}
    params.update(filters or {})
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = http.get(BASE_URL, params=params, timeout=40)
            if resp.status_code in (401, 403):
                raise MandiAPIError(f"The API refused the key (HTTP {resp.status_code}). Check DATA_GOV_API_KEY.")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or "records" not in data:
                message = data.get("message") if isinstance(data, dict) else None
                raise MandiAPIError(f"Unexpected reply from data.gov.in: {message or str(data)[:200]}")
            return data
        except MandiAPIError:
            raise
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 * attempt)
    raise MandiAPIError(f"Could not reach data.gov.in after {retries} tries: {last_error}")


def fetch_all(state: str | None = None, page_size: int = 1000, max_records: int = 100_000,
              session=None) -> list[dict]:
    """Every record for today (optionally one state), page by page."""
    filters = {}
    first = None
    if state:
        # The API accepts exact-match filters as filters[state.keyword]; older
        # examples use filters[state]. Try the first, fall back to the second.
        filters = {"filters[state.keyword]": state}
        first = fetch_page(0, page_size, filters, session=session)
        if not first.get("records"):
            filters = {"filters[state]": state}
            first = None

    records: list[dict] = []
    offset = 0
    while offset < max_records:
        if first is not None and offset == 0:
            page = first
        else:
            page = fetch_page(offset, page_size, filters, session=session)
        batch = page.get("records") or []
        records.extend(batch)
        offset += len(batch)
        try:
            total = int(page.get("total") or 0)
        except (TypeError, ValueError):
            total = 0
        if not batch:
            break
        # When the API says how many records exist, keep going until we have them all
        # (it may send fewer per page than we asked for). Otherwise a short page means "done".
        if (total and offset >= total) or (not total and len(batch) < page_size):
            break
    return records
