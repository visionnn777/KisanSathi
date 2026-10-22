"""Direct Market abuse protections: weak PINs, PIN lockout, duplicate interests, expiry, OTP."""
from starlette.requests import Request
from app.services.rate_limit import client_key
from datetime import timedelta

from app import config
from app.models import Listing
from app.timeutil import now_utc

LISTING = {"farmer_name": "Ramesh Kumar", "phone": "9876543210", "owner_pin": "farmer-secure-pin-123",
           "crop": "Tomato", "quantity_kg": 500, "price_per_kg": 14, "district": "Agra", "state": "Uttar Pradesh"}


def test_weak_pins_are_refused(client):
    for pin in ("12345678", "abcdefgh", "11111111", "password", "9876543210"):
        response = client.post("/api/listings", json={**LISTING, "owner_pin": pin})
        assert response.status_code == 422, pin


def test_wrong_pin_lockout_after_five_failures(client):
    assert client.post("/api/listings", json=LISTING).status_code == 201
    for _ in range(config.PIN_FAILURES_PER_HOUR):
        assert client.post("/api/listings/mine", json={"phone": "9876543210", "owner_pin": "wrong-guess-99"}).status_code == 403
    locked = client.post("/api/listings/mine", json={"phone": "9876543210", "owner_pin": "farmer-secure-pin-123"})
    assert locked.status_code == 429 and "Retry-After" in locked.headers


def test_one_interest_per_buyer_and_short_public_name(client):
    listing = client.post("/api/listings", json=LISTING).json()
    assert listing["farmer_name"] == "Ramesh K."
    buyer = {"buyer_name": "Shyam Traders", "phone": "9123456789"}
    assert client.post(f"/api/listings/{listing['id']}/interest", json=buyer).status_code == 201
    again = client.post(f"/api/listings/{listing['id']}/interest", json=buyer)
    assert again.status_code == 409 and "already sent" in again.json()["detail"]


def test_expired_listings_are_hidden_and_refuse_interest(client, db):
    listing = client.post("/api/listings", json=LISTING).json()
    row = db.get(Listing, listing["id"])
    row.created_at = now_utc() - timedelta(days=config.LISTING_EXPIRY_DAYS + 1)
    db.commit()
    assert client.get("/api/listings").json() == []
    assert client.get(f"/api/listings/{listing['id']}").json()["status"] == "expired"
    assert client.post(f"/api/listings/{listing['id']}/interest", json={"buyer_name": "Shyam", "phone": "9123456789"}).status_code == 409


def test_withdraw_needs_pin(client):
    listing = client.post("/api/listings", json=LISTING).json()
    bad = client.post(f"/api/listings/{listing['id']}/withdraw", json={"phone": "9876543210", "owner_pin": "wrong-guess-99"})
    assert bad.status_code == 403
    ok = client.post(f"/api/listings/{listing['id']}/withdraw", json={"phone": "9876543210", "owner_pin": "farmer-secure-pin-123"})
    assert ok.status_code == 200 and ok.json()["status"] == "withdrawn"
    assert client.get("/api/listings").json() == []
    late = client.post(f"/api/listings/{listing['id']}/interest", json={"buyer_name": "Late Buyer", "phone": "9123456780"})
    assert late.status_code == 409 and late.json()["detail"] == "This listing is no longer available"


def test_search_wildcards_are_literal(client):
    client.post("/api/listings", json=LISTING)
    assert client.get("/api/listings", params={"crop": "%"}).json() == []
    assert len(client.get("/api/listings", params={"crop": "tom"}).json()) == 1


def test_rate_limit_on_listing_creation(client):
    codes = [client.post("/api/listings", json={**LISTING, "phone": f"98765432{i:02d}"}).status_code for i in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


def test_otp_flow_when_enabled(client, monkeypatch, caplog):
    monkeypatch.setattr(config, "OTP_PROVIDER", "console")
    assert client.get("/api/auth/config").json()["otp_required"] is True
    assert client.post("/api/listings", json=LISTING).status_code == 401           # no phone token
    with caplog.at_level("WARNING", logger="kisansaathi.otp"):
        assert client.post("/api/auth/otp/request", json={"phone": "9876543210"}).status_code == 200
    code = caplog.records[-1].getMessage().split(": ")[1].split(" ")[0]
    assert client.post("/api/auth/otp/verify", json={"phone": "9876543210", "code": "000000" if code != "000000" else "111111"}).status_code == 403
    token = client.post("/api/auth/otp/verify", json={"phone": "9876543210", "code": code}).json()["phone_token"]
    replay = client.post(
        "/api/auth/otp/verify",
        json={"phone": "9876543210", "code": code},
    )
    assert replay.status_code == 403
    assert client.post("/api/listings", json={**LISTING, "phone_token": token}).status_code == 201
    # A token for one number does not work for another number.
    assert client.post("/api/listings", json={**LISTING, "phone": "9811122333", "phone_token": token}).status_code == 401

def test_client_key_respects_proxy_trust_setting(monkeypatch):
    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [
            (
                b"x-forwarded-for",
                b"203.0.113.15, 10.0.0.8",
            )
        ],
        "client": ("192.0.2.10", 50000),
        "server": ("testserver", 80),
    })

    monkeypatch.setattr(
        config, "TRUST_PROXY_HEADERS", False
    )
    assert client_key(request) == "192.0.2.10"

    monkeypatch.setattr(
        config, "TRUST_PROXY_HEADERS", True
    )
    assert client_key(request) == "203.0.113.15"