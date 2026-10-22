"""Owner: Member A"""

OWNER_PIN = "farmer-secure-pin-123"
LISTING = {
    "farmer_name": "Ramesh Kumar", "phone": "+91 98765 43210", "owner_pin": OWNER_PIN, "crop": "Tomato",
    "quantity_kg": 500, "price_per_kg": 14, "village": "Bichpuri", "district": "Agra",
    "state": "Uttar Pradesh",
}
BUYER = {"buyer_name": "Shyam Traders", "phone": "9123456789", "offered_price_per_kg": 15}


def create(client, **changes):
    r = client.post("/api/listings", json={**LISTING, **changes})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_hides_phone_and_cleans_number(client):
    listing = create(client)
    assert listing["status"] == "available"
    assert "phone" not in listing
    mine_response = client.post("/api/listings/mine", json={"phone": "9876543210", "owner_pin": OWNER_PIN})
    assert mine_response.status_code == 200
    mine = mine_response.json()
    assert mine[0]["phone"] == "9876543210"
    assert "owner_pin_hash" not in mine[0] and "owner_pin" not in mine[0]


def test_invalid_phone_and_quantity_rejected(client):
    assert client.post("/api/listings", json={**LISTING, "phone": "12345"}).status_code == 422
    assert client.post("/api/listings", json={**LISTING, "quantity_kg": 0}).status_code == 422


def test_browse_filters_and_newest_first(client):
    create(client, crop="Tomato")
    create(client, crop="Potato", district="Kanpur")
    all_items = client.get("/api/listings").json()
    assert [l["crop"] for l in all_items] == ["Potato", "Tomato"]
    assert [l["crop"] for l in client.get("/api/listings", params={"crop": "tom"}).json()] == ["Tomato"]
    assert [l["crop"] for l in client.get("/api/listings", params={"district": "kan"}).json()] == ["Potato"]


def test_interest_flow_and_mark_sold(client):
    listing = create(client)
    r = client.post(f"/api/listings/{listing['id']}/interest", json=BUYER)
    assert r.status_code == 201
    assert client.get(f"/api/listings/{listing['id']}").json()["interest_count"] == 1

    mine = client.post("/api/listings/mine", json={"phone": "9876543210", "owner_pin": OWNER_PIN}).json()
    assert mine[0]["interests"][0]["buyer_name"] == "Shyam Traders"

    # Neither phone-only knowledge nor a wrong PIN grants ownership.
    assert client.patch(f"/api/listings/{listing['id']}/sold", json={"phone": "9000000099", "owner_pin": OWNER_PIN}).status_code == 403
    assert client.patch(f"/api/listings/{listing['id']}/sold", json={"phone": "9876543210", "owner_pin": "wrong-pin-123"}).status_code == 403
    r = client.patch(f"/api/listings/{listing['id']}/sold", json={"phone": "9876543210", "owner_pin": OWNER_PIN})
    assert r.status_code == 200 and r.json()["status"] == "sold"

    # Sold listings leave the browse list and refuse new interest
    assert client.get("/api/listings").json() == []
    assert client.post(f"/api/listings/{listing['id']}/interest", json=BUYER).status_code == 409


def test_missing_listing_is_404(client):
    assert client.get("/api/listings/999").status_code == 404
    assert client.post("/api/listings/999/interest", json=BUYER).status_code == 404


def test_mine_needs_valid_phone_and_pin(client):
    assert client.post("/api/listings/mine", json={"phone": "abc", "owner_pin": OWNER_PIN}).status_code == 422
    assert client.post("/api/listings/mine", json={"phone": "9876543210", "owner_pin": "short"}).status_code == 422


def test_same_phone_must_reuse_same_pin(client):
    create(client)
    response = client.post("/api/listings", json={**LISTING, "owner_pin": "different-pin-456"})
    assert response.status_code == 403
    assert "same farmer PIN" in response.json()["detail"]


def test_wrong_pin_cannot_read_buyer_contacts(client):
    listing = create(client)
    client.post(f"/api/listings/{listing['id']}/interest", json=BUYER)
    response = client.post("/api/listings/mine", json={"phone": "9876543210", "owner_pin": "wrong-pin-123"})
    assert response.status_code == 403
    assert "phone number or farmer pin" in response.json()["detail"].lower()
