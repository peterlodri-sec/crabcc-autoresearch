# Deploy Guide — Running crabcc-autoresearch

Cheapest recommended provider: **Vast.ai** (~$0.30–0.50/hr for RTX 4090).  
For maximum reliability at slightly higher cost, use **RunPod** (~$0.50–0.74/hr).

---

## Prerequisites

You need four things before starting:

| Item | Where to get it |
|------|----------------|
| Tailscale ephemeral auth key | https://login.tailscale.com/admin/settings/keys — create a key with "Ephemeral" checked |
| Anthropic API key | https://console.anthropic.com |
| Hetzner VM with receiver running | See **Step 1** below |
| Vast.ai account | https://vast.ai |

---

## Step 1 — Start the receiver on Hetzner

SSH into your Hetzner VM and start the FastAPI receiver:

```bash
cd ~/crabcc-autoresearch/receiver
task serve
```

The receiver listens on port 8787 (Tailscale mesh only). Verify it is up:

```bash
curl http://localhost:8787/health
# → {"ok":true}
```

Find your Hetzner Tailscale IP:

```bash
tailscale ip -4
# → 100.x.x.x  ← note this, you will need it
```

Leave the receiver running (use `tmux` or `screen` to keep it alive after SSH disconnect):

```bash
tmux new -s receiver
task serve
# Ctrl-B D to detach
```

---

## Step 2 — Find a GPU instance on Vast.ai

Install the Vast.ai CLI:

```bash
pip install vastai
vastai set api-key <your-vastai-api-key>
```

Search for available RTX 4090 instances, sorted by price:

```bash
vastai search offers 'gpu_name=RTX_4090 num_gpus=1 inet_down>200' --order dph_total --limit 5
```

Note the instance ID of the cheapest reliable offer (avoid instances with reliability < 0.95).

---

## Step 3 — Prepare your startup script

Copy `worker/cloud-init.sh` and fill in your values:

```bash
cp worker/cloud-init.sh /tmp/startup.sh
```

Edit `/tmp/startup.sh` — or pass everything via environment variables when launching. The required variables are:

| Variable | Description |
|----------|-------------|
| `TS_AUTHKEY` | Tailscale ephemeral key from Step 0 |
| `PROVIDER` | `"vast.ai"` |
| `BUDGET_USD` | Your cost ceiling, e.g. `"12"` |

---

## Step 4 — Launch the instance

```bash
vastai create instance <INSTANCE_ID> \
  --image pytorch/pytorch:2.3.0-cuda12.1-cudnn8-devel \
  --disk 30 \
  --env '-e TS_AUTHKEY=tskey-auth-XXXX -e PROVIDER=vast.ai -e BUDGET_USD=12' \
  --onstart worker/cloud-init.sh
```

The instance will:
1. Join your Tailscale mesh as `gpu-research-worker-01`
2. Auto-detect its GPU type
3. Clone this repo and install deps

Wait ~3 minutes for bootstrap. Verify it joined Tailscale:

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

Set your API key and receiver URL, then start:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787   # from Step 1
export RUN_ID=crabcc-run-$(date +%Y%m%d-%H%M)
export BUDGET_USD=12

task prepare   # one-time tokenizer build (~2 min)
task run       # starts the autonomous loop
```

`task run` automatically calls `report_start` (logs GPU + budget to receiver) before the loop begins, and `report_end` (logs total cost) when it finishes or is killed.

---

## Step 6 — Monitor

Open your browser to `https://research.crabcc.app` (or `http://<hetzner-tailscale-ip>:8787` directly).

You will see:
- **Run Sessions** table: GPU, provider, budget, actual cost so far, start time
- **Step Log**: every 5-minute cycle — val_bpb, status (SUCCESS/REVERTED/CRASHED), per-step API cost

Or query from the CLI on Hetzner:

```bash
task tail RUN_ID=crabcc-run-20260610-1400
task sessions
```

---

## Step 7 — Tear down

After 6–8 hours (or when the run completes), destroy the instance:

```bash
vastai destroy instance <INSTANCE_ID>
```

The Tailscale ephemeral node expires automatically. Your results are safe in SQLite on Hetzner.

---

## Cost breakdown (typical 8-hour RTX 4090 run)

| Line item | Estimate |
|-----------|----------|
| GPU compute (Vast.ai RTX 4090 spot, 8 hr) | $2.40–$4.00 |
| Anthropic API (96 iterations × ~12k tokens) | ~$5.60 |
| **Total** | **~$8–10** |

Using a smaller/cheaper model for mutations (e.g. Haiku) cuts the API cost to ~$0.80, bringing the total under $5.
