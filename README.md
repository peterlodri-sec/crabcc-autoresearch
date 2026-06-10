# crabcc-autoresearch

> autonomous ml training loop — headless, cost-transparent, 8 hours unattended

Runs Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch) loop on an ephemeral GPU spot instance. Every 5-minute training cycle reports validation loss, API cost, and status back to a FastAPI receiver on your Hetzner VM over Tailscale. No babysitting. Full cost transparency. Results visible at `research.crabcc.app`.

---

## architecture

```
[ hetzner nixos vm ]  ←── tailscale mesh ───→  [ ephemeral gpu (vast.ai) ]
  receiver/                                        worker/
  fastapi + sqlite                                 autoresearch loop
  research.crabcc.app                              telemetry.py hook
  systemd rsync timer                              cloud-init.sh
```

Two components. One repo.

| component | runs on | purpose |
|-----------|---------|---------|
| `worker/` | GPU spot instance | training loop + telemetry client |
| `receiver/` | hetzner vm | telemetry ingest, SQLite store, dashboard |
| `nix/` | nix-base (snippet) | systemd rsync timer for `results.tsv` backup |

---

## quick start

**1 — start the receiver on hetzner**

```bash
cd receiver
task serve          # fastapi on :8787, tailscale-only
curl localhost:8787/health  # → {"ok":true}
```

**2 — spin up a gpu instance and run**

See [`deploy.md`](deploy.md) for the full step-by-step. Short version:

```bash
# on the gpu worker (after cloud-init)
export ANTHROPIC_API_KEY=sk-ant-...
export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787
export RUN_ID=crabcc-run-001
export BUDGET_USD=12

task prepare   # one-time tokenizer build
task run       # autonomous loop starts — gpu type and budget auto-reported
```

**3 — monitor**

Open `http://<hetzner-tailscale-ip>:8787` (or `research.crabcc.app` if caddy is wired up).

Dashboard shows two tables:

— **run sessions** — gpu type, provider, budget, actual cost, best `val_bpb`, start/end time  
— **step log** — every 5-minute cycle: `val_bpb`, status (`SUCCESS` / `REVERTED` / `CRASHED`), per-step api cost

Or from the cli on hetzner:

```bash
task sessions                              # last 10 runs
task tail RUN_ID=crabcc-run-001            # last 20 steps for a run
```

---

## cost

Typical 8-hour RTX 4090 run on Vast.ai:

| line item | estimate |
|-----------|----------|
| gpu compute (~$0.40/hr × 8h) | $3.20 |
| anthropic api (~96 iterations × 12k tokens) | ~$5.60 |
| **total** | **~$8–10** |

Swap in Haiku for mutations → total drops under $5.

---

## repo layout

```
.github/workflows/ci.yml   ruff + pytest on push + pr
deploy.md                  step-by-step vast.ai guide
worker/
  telemetry.py             report_start / report_run / report_end
  push_dataset.py          push run artifacts to research.crabcc.app repo
  cloud-init.sh            tailscale + uv + nvidia-smi auto-detect
  Taskfile.yml             prepare · run · publish · test
  program.md               baseline research constraints
receiver/
  main.py                  post /api/telemetry, /api/runs/start|end,
                           get /health, /api/sessions, /api/runs/{id}, /
  schema.sql               runs + run_sessions tables
  Taskfile.yml             serve · migrate · tail · sessions
nix/
  crabcc-research-sync.nix  drop-in systemd timer for nix-base
```

---

## telemetry api

The receiver exposes five endpoints:

```
POST /api/runs/start    → log gpu, provider, budget before loop begins
POST /api/telemetry     → one call per 5-min cycle (val_bpb, status, cost)
POST /api/runs/end      → seal the run with total cost
GET  /api/runs/{id}     → full step log for a run (JSON)
GET  /api/sessions      → last 50 run sessions with best val_bpb
GET  /health            → {"ok":true}
```

All writes travel over the Tailscale mesh. No public write endpoint.

---

## dataset archive

After each run, `task publish` pushes three files to `peterlodri-sec/lambda-normalization-census`:

```
data/autoresearch/autoresearch-YYYYMMDD-HHMM/
  results.tsv      autoresearch native step log
  train.py         final best model code
  run_meta.json    {run_id, gpu_type, provider, budget_usd, total_cost_usd, best_val_bpb}
```

Requires `GITHUB_TOKEN` env var with `contents: write` on that repo. `task run` calls `task publish` automatically — no manual step needed.

---

## dev

```bash
# receiver
cd receiver && uv sync --dev && task test

# worker
cd worker && uv sync --dev && task test
```

CI runs `ruff check`, `ruff format --check`, and `pytest` for both components on every push.

---

## nix integration

Copy `nix/crabcc-research-sync.nix` into `nix-base` and import in the host config:

```nix
imports = [ ./crabcc-research-sync.nix ];
```

Syncs `results.tsv` from the gpu worker over Tailscale every 10 minutes as a backup artifact alongside the live SQLite telemetry.

---

*fast · exact · frugal*
