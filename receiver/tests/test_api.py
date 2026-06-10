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
    assert "crabcc autoresearch" in resp.text
    assert "<table" in resp.text


def test_run_start():
    resp = client.post("/api/runs/start", json={
        "run_id": "t-session-1",
        "machine_type": "2x RTX 4090",
        "gpu_type": "RTX 4090",
        "provider": "vast.ai",
        "budget_usd": 10.0,
    })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_run_end():
    client.post("/api/runs/start", json={"run_id": "t-end-1", "budget_usd": 5.0})
    resp = client.post("/api/runs/end", json={"run_id": "t-end-1", "total_cost_usd": 4.23})
    assert resp.status_code == 200


def test_run_end_unknown_run_returns_404():
    resp = client.post("/api/runs/end", json={"run_id": "no-such-run", "total_cost_usd": 0.0})
    assert resp.status_code == 404


def test_list_sessions():
    client.post("/api/runs/start", json={"run_id": "t-list-1", "gpu_type": "A100", "provider": "runpod"})
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    ids = [s["run_id"] for s in resp.json()]
    assert "t-list-1" in ids


def test_ingest_with_cost():
    resp = client.post("/api/telemetry", json={
        "run_id": "t-cost-1",
        "step": 1,
        "val_bpb": 2.10,
        "status": "SUCCESS",
        "api_cost_usd": 0.0523,
    })
    assert resp.status_code == 200
    rows = client.get("/api/runs/t-cost-1").json()
    assert rows[0]["api_cost_usd"] == 0.0523
