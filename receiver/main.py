# receiver/main.py
import os
import pathlib
import sqlite3
from contextlib import contextmanager
from html import escape
from typing import Optional

from fastapi import FastAPI, HTTPException
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
        # idempotent column migration for existing DBs
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN api_cost_usd REAL DEFAULT 0.0")
        except Exception:
            pass  # column already exists


migrate()


@app.on_event("startup")
def _startup_migrate():
    migrate()


# --- Models ---


class RunEvent(BaseModel):
    run_id: str
    step: int
    val_bpb: Optional[float] = None
    status: str
    diff: str = ""
    api_cost_usd: float = 0.0


class RunStart(BaseModel):
    run_id: str
    machine_type: str = ""
    gpu_type: str = ""
    provider: str = ""
    budget_usd: float = 0.0


class RunEnd(BaseModel):
    run_id: str
    total_cost_usd: float = 0.0


# --- Routes ---


@app.post("/api/telemetry", status_code=200)
def ingest(event: RunEvent):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, step, val_bpb, status, diff, api_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.run_id,
                event.step,
                event.val_bpb,
                event.status,
                event.diff,
                event.api_cost_usd,
            ),
        )
    return {"ok": True}


@app.post("/api/runs/start", status_code=200)
def run_start(body: RunStart):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO run_sessions (run_id, machine_type, gpu_type, provider, budget_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                body.run_id,
                body.machine_type,
                body.gpu_type,
                body.provider,
                body.budget_usd,
            ),
        )
    return {"ok": True}


@app.post("/api/runs/end", status_code=200)
def run_end(body: RunEnd):
    with get_db() as conn:
        updated = conn.execute(
            "UPDATE run_sessions SET ended_at = CURRENT_TIMESTAMP, total_cost_usd = ? "
            "WHERE run_id = ?",
            (body.total_cost_usd, body.run_id),
        ).rowcount
    if updated == 0:
        raise HTTPException(status_code=404, detail="run_id not found")
    return {"ok": True}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE run_id = ? ORDER BY step",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/sessions")
def list_sessions():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT s.*, MIN(r.val_bpb) AS best_val_bpb
            FROM run_sessions s
            LEFT JOIN runs r ON r.run_id = s.run_id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT 50
            """,
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with get_db() as conn:
        sessions = conn.execute(
            """
            SELECT s.*, MIN(r.val_bpb) AS best_val_bpb
            FROM run_sessions s
            LEFT JOIN runs r ON r.run_id = s.run_id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT 50
            """,
        ).fetchall()
        steps = conn.execute("SELECT * FROM runs ORDER BY ts DESC LIMIT 200").fetchall()

    session_rows = "".join(
        f"<tr>"
        f"<td>{escape(str(s['run_id']))}</td>"
        f"<td>{escape(str(s['gpu_type']))} ({escape(str(s['provider']))})</td>"
        f"<td>{escape(str(s['machine_type']))}</td>"
        f"<td>${escape(str(round(s['budget_usd'], 4)))}</td>"
        f"<td>${escape(str(round(s['total_cost_usd'] or 0, 4)))}</td>"
        f"<td>{escape(str(round(s['best_val_bpb'], 4) if s['best_val_bpb'] is not None else '—'))}</td>"
        f"<td>{escape(str(s['started_at']))}</td>"
        f"<td>{escape(str(s['ended_at'] or '—'))}</td>"
        f"</tr>"
        for s in sessions
    )

    step_rows = "".join(
        f"<tr>"
        f"<td>{escape(str(r['run_id']))}</td>"
        f"<td>{escape(str(r['step']))}</td>"
        f"<td>{escape(str(r['val_bpb']))}</td>"
        f"<td>{escape(str(r['status']))}</td>"
        f"<td>${escape(str(round(r['api_cost_usd'] or 0, 4)))}</td>"
        f"<td>{escape(str(r['ts']))}</td>"
        f"</tr>"
        for r in steps
    )

    return f"""<!DOCTYPE html>
<html>
<head><title>crabcc research</title>
<style>
  body{{font-family:monospace;padding:2rem;max-width:1400px;margin:0 auto}}
  h2{{margin-top:2rem}}
  table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}
  td,th{{border:1px solid #ccc;padding:.4rem .8rem;text-align:left}}
  th{{background:#f5f5f5}}
</style>
</head>
<body>
<h1>crabcc autoresearch</h1>

<h2>Run Sessions</h2>
<table>
<thead><tr>
  <th>run_id</th><th>GPU (provider)</th><th>machine</th>
  <th>budget</th><th>actual cost</th><th>best val_bpb</th><th>started</th><th>ended</th>
</tr></thead>
<tbody>{session_rows}</tbody>
</table>

<h2>Step Log</h2>
<table>
<thead><tr>
  <th>run_id</th><th>step</th><th>val_bpb</th><th>status</th><th>step cost</th><th>ts</th>
</tr></thead>
<tbody>{step_rows}</tbody>
</table>
</body></html>"""
