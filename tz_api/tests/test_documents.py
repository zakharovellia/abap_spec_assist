async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_create_and_get_document(client):
    payload = {
        "author_id": "ivanov",
        "tz_type": "alv_report",
        "scenario": "new",
        "title": "Отчёт по остаткам",
    }
    resp = await client.post("/api/documents", json=payload)
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["id"]
    assert doc["status"] == "draft"
    assert doc["scenario"] == "new"
    assert doc["created_at"].endswith("Z")

    doc_id = doc["id"]
    resp = await client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Отчёт по остаткам"


async def test_revisions_flow(client):
    resp = await client.post(
        "/api/documents",
        json={"author_id": "petrov", "tz_type": "alv_report"},
    )
    doc_id = resp.json()["id"]

    rev_payload = {"payload": {"header": {"title": "v1"}}, "created_by": "human"}
    resp = await client.post(f"/api/documents/{doc_id}/revisions", json=rev_payload)
    assert resp.status_code == 200
    rev = resp.json()
    assert rev["payload"]["header"]["title"] == "v1"

    resp = await client.get(f"/api/documents/{doc_id}/revisions")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_conversation_and_generation(client):
    resp = await client.post(
        "/api/documents",
        json={"author_id": "sidorov", "tz_type": "alv_report"},
    )
    doc_id = resp.json()["id"]

    resp = await client.post(
        f"/api/documents/{doc_id}/conversation",
        json={"role": "user", "content": "Нужен отчёт по остаткам MARD"},
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/documents/{doc_id}/generation",
        json={"message": "Нужен отчёт по остаткам MARD"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"


async def test_404_on_missing_document(client):
    resp = await client.get("/api/documents/does-not-exist")
    assert resp.status_code == 404
