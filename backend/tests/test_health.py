"""Owner: Member A"""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_website_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "KisanSaathi" in r.text
