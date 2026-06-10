# dataset schema

Each completed autoresearch run pushes three files to
[`peterlodri-sec/lambda-normalization-census`](https://github.com/peterlodri-sec/lambda-normalization-census)
under `data/autoresearch/autoresearch-YYYYMMDD-HHMM/`.

---

## run_meta.json

Structured metadata for the run. Schema: [`worker/run_meta_schema.json`](worker/run_meta_schema.json).

| field | type | description |
|-------|------|-------------|
| `run_id` | string | unique run identifier, e.g. `crabcc-run-20260610-1400` |
| `gpu_type` | string | GPU model as reported by `nvidia-smi`, e.g. `NVIDIA GeForce RTX 4090` |
| `provider` | string | compute provider, e.g. `vast.ai` |
| `budget_usd` | number | cost ceiling set before the run |
| `total_cost_usd` | number | actual total cost (GPU + LLM API) at run end |
| `best_val_bpb` | number \| null | minimum `val_bpb` achieved across all steps; null if no successful step |
| `published_at` | string (ISO 8601) | UTC timestamp when artifacts were pushed |

---

## results.tsv

Tab-separated step log written by the autoresearch loop. One row per 5-minute training cycle.

| column | type | description |
|--------|------|-------------|
| `step` | integer | cycle index, starting at 1 |
| `val_bpb` | float \| null | validation bits-per-byte for this cycle; null if training crashed |
| `status` | string | `SUCCESS` — mutation accepted; `REVERTED` — mutation rejected; `CRASHED` — training error |

Additional columns may be present depending on the autoresearch version.

---

## train.py

The final best-performing `train.py` as of the last accepted mutation — the Python training
script whose checkpoint produced the lowest `val_bpb` in this run. Executable with
`uv run python train.py` from the worker directory after `task prepare`.

---

## versioning

Dataset format version is tracked in `datapackage.json` alongside the artifacts in the
census repo. Breaking schema changes increment the major version and are noted in
[`FINDINGS.md`](FINDINGS.md).
