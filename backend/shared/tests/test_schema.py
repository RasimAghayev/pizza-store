def test_schema_is_a_structurally_valid_openapi_document(client):
    response = client.get("/api/schema/?format=json")

    assert response.status_code == 200
    schema = response.json()

    assert schema["openapi"].startswith("3.")
    assert "/api/v1/ping/" in schema["paths"]
