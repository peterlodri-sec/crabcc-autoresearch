CREATE TABLE IF NOT EXISTS runs (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  TEXT    NOT NULL,
    step    INTEGER NOT NULL,
    val_bpb REAL,
    status  TEXT    NOT NULL,
    diff    TEXT    DEFAULT '',
    ts      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_run_id ON runs (run_id);
