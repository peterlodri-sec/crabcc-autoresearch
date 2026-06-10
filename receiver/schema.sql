CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT    NOT NULL,
    step         INTEGER NOT NULL,
    val_bpb      REAL,
    status       TEXT    NOT NULL,
    diff         TEXT    DEFAULT '',
    api_cost_usd REAL    DEFAULT 0.0,
    ts           DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_run_id ON runs (run_id);

CREATE TABLE IF NOT EXISTS run_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT    NOT NULL UNIQUE,
    machine_type   TEXT    NOT NULL DEFAULT '',
    gpu_type       TEXT    NOT NULL DEFAULT '',
    provider       TEXT    NOT NULL DEFAULT '',
    budget_usd     REAL    NOT NULL DEFAULT 0.0,
    started_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at       DATETIME,
    total_cost_usd REAL    DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_sessions_run_id ON run_sessions (run_id);
