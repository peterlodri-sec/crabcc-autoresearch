---
name: launch-run
description: |
  Launch, monitor, and wrap up a crabcc-autoresearch run on vast.ai.
  Covers: picking a GPU, setting env vars for dual-slot execution,
  monitoring both slots via the receiver API, and publishing artifacts.
trigger: /launch-run
---

# crabcc-autoresearch: Launch Run

## 1. Pick a GPU

For a standard run (both slots, 8h):

| budget | GPU | VRAM | vast.ai search |
|--------|-----|------|---------------|
| $10–14 | RTX 4090 | 24 GB | `gpu_name=RTX_4090 num_gpus=1` |
| $20–28 | A100 SXM | 80 GB | `gpu_name=A100_SXM4_80GB num_gpus=1` |
| $30–44 | H100 SXM | 80 GB | `gpu_name=H100_SXM5_80GB num_gpus=1` |

Search via: `vastai search offers 'gpu_name=RTX_4090 num_gpus=1 inet_up>200 disk_space>20'`

## 2. Required env vars

```bash
export TS_AUTHKEY=tskey-auth-...            # Tailscale (joins the mesh)
export OPENROUTER_API_KEY=sk-or-...         # dedicated key for crabcc runs
export LLM_MODEL=anthropic/claude-sonnet-4-6
export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787
export GITHUB_TOKEN=github_pat_...          # push to lambda-normalization-census
export RUN_ID=crabcc-run-$(date +%Y%m%d-%H%M)
export BUDGET_USD=14                        # split evenly across two slots
export PROVIDER=vast.ai

# Optional
export LANGSMITH_API_KEY=ls__...
export LANGSMITH_PROJECT=crabcc-autoresearch
```

## 3. Start the run

```bash
cd worker && task run
```

This launches **two slots in parallel**:
- `${RUN_ID}-lambda` — λ-term normalization classifier (uses census dataset)
- `${RUN_ID}-charlm` — character-level LM (general architecture benchmark)

To run a single slot for debugging:
```bash
SLOT=lambda task run-single
```

## 4. Monitor

**Receiver dashboard** (live step log):
```bash
curl http://<hetzner-tailscale-ip>:8787/api/sessions | jq '.[-2:]'
```

**Watch val_bpb for both slots as they run:**
```bash
watch -n 30 "curl -s http://<hetzner-tailscale-ip>:8787/api/sessions | jq '.[] | select(.run_id | startswith(\"${RUN_ID}\")) | {run_id, best_val_bpb: .best_val_bpb}'"
```

**Tail receiver logs (from Hetzner):**
```bash
task tail   # in receiver/
```

**LangSmith trace** (if configured): URL is in `worker/.langsmith_run_url` after agent.py starts.

## 5. After the run

`task publish` is called automatically by `task run`. To re-publish manually:
```bash
RUN_ID=crabcc-run-YYYYMMDD-HHMM task publish
```

Check the census repo for the new directories:
- `data/autoresearch/${RUN_ID}-lambda/`
- `data/autoresearch/${RUN_ID}-charlm/`

## 6. What to log in FINDINGS.md

After reviewing results:
```markdown
## YYYY-MM

### run crabcc-run-YYYYMMDD-HHMM-lambda  best val_bpb: X.XX
<what mutation worked, what didn't>

### run crabcc-run-YYYYMMDD-HHMM-charlm  best val_bpb: X.XX
<comparison note — did the same mutation help both tasks?>
```

## Troubleshooting

| symptom | fix |
|---------|-----|
| `push_dataset` ref conflict | auto-retried 3× with backoff; check logs for `ref conflict` |
| slot exits immediately | `main_loop.py` not present — run `task prepare` first, then clone autoresearch |
| no telemetry appearing | check `CRABCC_RECEIVER_URL` and Tailscale mesh connectivity |
| LangSmith trace missing | `LANGSMITH_API_KEY` not set or `langsmith` package not installed |
