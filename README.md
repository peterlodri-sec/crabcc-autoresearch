# crabcc-autoresearch

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/peterlodri-sec/crabcc-autoresearch/actions/workflows/ci.yml/badge.svg)](https://github.com/peterlodri-sec/crabcc-autoresearch/actions/workflows/ci.yml)
[![Sponsor](https://img.shields.io/github/sponsors/peterlodri-sec?label=Sponsor&logo=githubsponsors&color=ea4aaa)](https://github.com/sponsors/peterlodri-sec)

> autonomous ml research loop — headless, cost-transparent, 8 hours unattended

The compute harness for the [`lambda-normalization-census`](https://github.com/peterlodri-sec/lambda-normalization-census) research project. Runs Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch) loop on an ephemeral GPU spot instance to train a small transformer that classifies λ-term normalization status (**SN** / **SEP** / **NWN** / **UND**). Every 5-minute cycle proposes a mutation to `train.py`, trains it, and reports `val_bpb` + cost back to a FastAPI receiver on Hetzner over Tailscale.

Each completed run archives its artifacts automatically into `data/autoresearch/` in the census repo — extending the public dataset without manual intervention. Findings are curated in [`FINDINGS.md`](FINDINGS.md).

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
export OPENROUTER_API_KEY=sk-or-...
export LLM_MODEL=anthropic/claude-sonnet-4-6   # optional
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
| gpu compute (~$0.40/hr × 8h) | ~$3.20 |
| openrouter — sonnet + prompt caching | ~$3–4 |
| **total** | **~$6–8** |

Prompt caching via OpenRouter cuts input token cost ~60–80% on the static `train.py` prefix. Swap model to DeepSeek-V3 via `LLM_MODEL` to halve the LLM cost further.

---

## roadmap

**sponsor goal: $500/month → nightly automation**

Once the [`lambda-normalization-census`](https://github.com/peterlodri-sec/lambda-normalization-census) hits its $500/month sponsorship threshold, the loop runs every night unattended:

| at scale | per night | per month | per year |
|----------|-----------|-----------|----------|
| gpu compute | ~$3.20 | ~$96 | ~$1,150 |
| llm (sonnet + caching) | ~$3–4 | ~$90–120 | ~$1,080–1,440 |
| **total** | **~$6–8** | **~$186–216** | **~$2,230–2,590** |
| training experiments | ~96 | ~2,880 | ~34,560 |

**why this matters:**

A learned normalization classifier that generalises beyond the decidability horizon (n>16, where exact enumeration is intractable) would be a genuine research contribution — useful for type-checkers, proof assistants, and anyone reasoning about λ-calculus reduction. The loop finds the architecture and training recipe; the census provides the data; [`FINDINGS.md`](FINDINGS.md) tracks what it discovers.

**usefulness to the public / ai research community: 4/5**  
open reproducible ML experiments at this granularity are scarce — full artifact trail, cost metadata, and a task that directly advances a published open dataset. the gap to 5/5 is frontier scale; this is solo-researcher scale compute doing targeted theory-adjacent work.

---

**stretch goal: $5,000/month → research-grade**

At 10× the nightly threshold the loop shifts from solo-researcher to small-lab scale. The key change is GPU class — A100/H100 (80 GB VRAM) vs RTX 4090 (24 GB) — which unlocks model sizes that can learn structural inductive biases about λ-reduction rather than surface patterns.

| at scale | per night | per month | per year |
|----------|-----------|-----------|----------|
| gpu (A100 / H100 80 GB) | ~$16–40 | ~$480–1,200 | ~$5,760–14,400 |
| llm (sonnet + caching) | ~$12–16 | ~$360–480 | ~$4,320–5,760 |
| **total** | **~$28–56** | **~$840–1,680** | **~$10,000–20,000** |
| parallel architectures / night | 4–8 | — | — |
| training experiments / month | 5,000+ | — | — |
| max model scale | 7B+ params | — | — |

what $5k unlocks:

- **parallel architecture search** — run 4–8 candidate `train.py` mutations simultaneously each night; the autoresearch LLM converges on the best design in weeks not years
- **7B-class models** — 80 GB VRAM opens transformer scales that can plausibly learn deep structural patterns in λ-term reduction sequences, not just token statistics
- **decidability horizon push** — a heuristic with meaningfully better accuracy above n > 20 (where exact enumeration is intractable) would be a novel result usable in proof assistants and type-checkers
- **publishable dataset** — ~60,000+ training experiments/year with full cost + metric provenance; sufficient for a formal-methods or ML workshop ablation study

**usefulness at $5k/month: 4.5/5** — the gap to 5/5 closes when a finding clears peer review; the infrastructure and reproducibility are already there.

---

## repo layout

```
.github/workflows/ci.yml   ruff + pytest on push + pr
FINDINGS.md                curated discoveries across nightly runs
deploy.md                  step-by-step vast.ai guide
worker/
  telemetry.py             report_start / report_run / report_end
  push_dataset.py          push run artifacts to lambda-normalization-census
  patch_llm.py             patches autoresearch → openrouter + langsmith
  cloud-init.sh            tailscale + uv + nvidia-smi auto-detect
  Taskfile.yml             prepare · run · publish · test
  program.md               research task: λ-term normalization classifier
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
