# receiver/tests/test_api.py
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_ingest_returns_ok():
    resp = client.post("/api/telemetry", json={
        "run_id": "t-ok-1",
        "step": 1,
        "val_bpb": 2.34,
        "status": "SUCCESS",
    })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_ingest_persists_row():
    client.post("/api/telemetry", json={
        "run_id": "t-persist-1",
        "step": 5,
        "val_bpb": 1.99,
        "status": "SUCCESS",
    })
    resp = client.get("/api/runs/t-persist-1")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["step"] == 5
    assert rows[0]["val_bpb"] == 1.99
    assert rows[0]["status"] == "SUCCESS"


def test_ingest_reverted_null_val():
    resp = client.post("/api/telemetry", json={
        "run_id": "t-rev-1",
        "step": 3,
        "val_bpb": None,
        "status": "REVERTED",
        "diff": "- old\n+ new",
    })
    assert resp.status_code == 200


def test_unknown_run_returns_empty_list():
    resp = client.get("/api/runs/does-not-exist")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_returns_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "autoresearch runs" in resp.text
    assert "<table" in resp.text
