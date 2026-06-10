# receiver/main.py
import os
import pathlib
import sqlite3
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DB_PATH = pathlib.Path(os.environ.get("CRABCC_DB", "/var/lib/crabcc-research/runs.db"))
SCHEMA = pathlib.Path(__file__).parent / "schema.sql"

app = FastAPI()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def migrate():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(SCHEMA.read_text())


# Run migration eagerly at import time so TestClient (no lifespan) also works
migrate()


@app.on_event("startup")
def startup():
    # Idempotent: schema uses CREATE TABLE IF NOT EXISTS
    migrate()


class RunEvent(BaseModel):
    run_id: str
    step: int
    val_bpb: Optional[float] = None
    status: str
    diff: str = ""


@app.post("/api/telemetry", status_code=200)
def ingest(event: RunEvent):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, step, val_bpb, status, diff) VALUES (?, ?, ?, ?, ?)",
            (event.run_id, event.step, event.val_bpb, event.status, event.diff),
        )
    return {"ok": True}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE run_id = ? ORDER BY step",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY ts DESC LIMIT 200"
        ).fetchall()
    rows_html = "".join(
        f"<tr><td>{r['run_id']}</td><td>{r['step']}</td>"
        f"<td>{r['val_bpb']}</td><td>{r['status']}</td><td>{r['ts']}</td></tr>"
        for r in rows
    )
    return f"""<!DOCTYPE html>
<html>
<head><title>crabcc research</title>
<style>body{{font-family:monospace;padding:2rem}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:.4rem .8rem}}th{{background:#f5f5f5}}</style>
</head>
<body>
<h1>autoresearch runs</h1>
<table>
<thead><tr><th>run_id</th><th>step</th><th>val_bpb</th><th>status</th><th>ts</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
</body></html>"""
