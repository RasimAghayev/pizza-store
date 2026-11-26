def test_ping_returns_pong(client):
    response = client.get("/api/v1/ping/")

    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_ping_rejects_an_unknown_version(client):
    response = client.get("/api/v2/ping/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
