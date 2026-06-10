# Deploy Guide

Cheapest recommended provider: **Vast.ai** (~$0.30–0.50/hr for RTX 4090).  
For maximum reliability at slightly higher cost, use **RunPod** (~$0.50–0.74/hr).

---

## Prerequisites

| Item | Where to get it |
|------|----------------|
| Tailscale ephemeral auth key | https://login.tailscale.com/admin/settings/keys — "Ephemeral" checked |
| OpenRouter API key | https://openrouter.ai/keys — dedicated key recommended |
| GitHub PAT | https://github.com/settings/tokens — fine-grained, `contents: write` on `peterlodri-sec/lambda-normalization-census` |
| Vast.ai account | https://vast.ai |
| Hetzner NixOS VM (receiver host) | See Step 1 |

---

## Step 1 — Deploy the receiver on Hetzner

### Option A — NixOS module (recommended)

Add this repo as a flake input and enable the receiver module in your host config:

```nix
# flake.nix
inputs.crabcc.url = "github:peterlodri-sec/crabcc-autoresearch";

# hosts/hetzner/configuration.nix
imports = [ inputs.crabcc.nixosModules.receiver ];

services.crabcc.receiver = {
  enable   = true;
  repoPath = "/opt/crabcc-autoresearch";   # git clone path on the host
  host     = "127.0.0.1";                  # fronted by Caddy/nginx
  port     = 8787;
};
```

Clone the repo and rebuild:

```bash
git clone https://github.com/peterlodri-sec/crabcc-autoresearch /opt/crabcc-autoresearch
nixos-rebuild switch --flake .#hetzner
```

The receiver runs as a hardened systemd service (`crabcc-receiver.service`) and restarts on failure.

### Option B — manual (quick start)

```bash
git clone https://github.com/peterlodri-sec/crabcc-autoresearch
cd crabcc-autoresearch/receiver
tmux new -s receiver
task serve        # listens on :8787, Tailscale mesh only
# Ctrl-B D to detach
```

### Verify

```bash
curl http://localhost:8787/health
# → {"ok":true}

tailscale ip -4   # note this — you'll need it in Step 4
```

---

## Step 2 — (Optional) Enable the artifact sync timer

The sync timer pulls `results.tsv` and `train.py` from both slots every 10 minutes as a live backup alongside the SQLite telemetry.

```nix
imports = [ inputs.crabcc.nixosModules.research-sync ];

services.crabcc.researchSync = {
  enable     = true;
  workerHost = "gpu-research-worker-01";  # Tailscale hostname of the GPU instance
  slots      = [ "lambda" "charlm" ];
};
```

---

## Step 3 — Find a GPU instance on Vast.ai

```bash
pip install vastai
vastai set api-key <your-vastai-api-key>

# Search for RTX 4090 instances sorted by price
vastai search offers 'gpu_name=RTX_4090 num_gpus=1 inet_down>200 disk_space>30' \
  --order dph_total --limit 5
```

Avoid instances with reliability < 0.95. Note the instance ID.

---

## Step 4 — Launch the instance

```bash
vastai create instance <INSTANCE_ID> \
  --image pytorch/pytorch:2.3.0-cuda12.1-cudnn8-devel \
  --disk 30 \
  --env '-e TS_AUTHKEY=tskey-auth-XXXX -e PROVIDER=vast.ai -e BUDGET_USD=14' \
  --onstart worker/cloud-init.sh
```

The instance will:
1. Join your Tailscale mesh as `gpu-research-worker-01`
2. Auto-detect GPU type via `nvidia-smi`
3. Clone this repo, install deps, and patch `main_loop.py` for OpenRouter

Wait ~3 minutes for bootstrap, then verify:

```bash
tailscale status | grep gpu-research-worker-01
```

---

## Step 5 — Start the research loop

SSH into the worker over Tailscale:

```bash
ssh root@gpu-research-worker-01
cd crabcc-autoresearch/worker
```

Set your keys and start:

```bash
export OPENROUTER_API_KEY=sk-or-...                              # dedicated key for this project
export LLM_MODEL=anthropic/claude-sonnet-4-6                     # or deepseek/deepseek-chat to cut LLM cost ~50%
export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787   # from Step 1
export GITHUB_TOKEN=github_pat_...                               # contents:write on lambda-normalization-census
export RUN_ID=crabcc-run-$(date +%Y%m%d-%H%M)
export BUDGET_USD=14
export PROVIDER=vast.ai

# Optional — enables full LangSmith tracing across both slots
export LANGSMITH_API_KEY=ls__...
export LANGSMITH_PROJECT=crabcc-autoresearch

task prepare   # one-time tokenizer build (~2 min, skip on repeat runs)
task run       # launches both slots in parallel
```

`task run` starts two autoresearch loops simultaneously:

| slot | run_id | task |
|------|--------|------|
| `lambda` | `${RUN_ID}-lambda` | λ-term normalization classifier |
| `charlm` | `${RUN_ID}-charlm` | character-level LM benchmark |

Each slot reports telemetry independently. When both finish, `task publish` archives artifacts for each slot to `peterlodri-sec/lambda-normalization-census`:

```
data/autoresearch/${RUN_ID}-lambda/
  results.tsv   run_meta.json   train.py
data/autoresearch/${RUN_ID}-charlm/
  results.tsv   run_meta.json   train.py
```

---

## Step 6 — Monitor

**Dashboard:** `https://research.crabcc.app` or `http://<hetzner-tailscale-ip>:8787`

**CLI — watch both slots live:**

```bash
# on Hetzner
watch -n 30 "curl -s http://localhost:8787/api/sessions \
  | jq '[.[] | select(.run_id | startswith(\"'$RUN_ID'\")) | {run_id, best_val_bpb, total_cost_usd}]'"
```

**LangSmith trace** (if configured): URL is printed by `agent.py` at startup and stored in `worker/.langsmith_run_url`.

---

## Step 7 — Tear down

```bash
vastai destroy instance <INSTANCE_ID>
```

The Tailscale ephemeral node expires automatically. Run artifacts are safe in SQLite on Hetzner and archived to the census repo.

---

## Cost breakdown (typical 8-hour run, both slots)

| line item | estimate |
|-----------|----------|
| GPU compute — RTX 4090 spot, 8 hr | $2.40–$4.00 |
| OpenRouter (sonnet + prompt caching, 2 slots × 96 cycles) | $3–5 |
| **total** | **~$6–9** |

Switch `LLM_MODEL` to `deepseek/deepseek-chat` to cut LLM cost to ~$0.50, bringing the total under $5.  
Running on A100/H100 (80 GB) to unlock 7B+ model scale costs ~$20–28 per night.
