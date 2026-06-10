#!/bin/bash
# Spot-instance bootstrap. Run as cloud-init user-data or paste into provider startup script.
# Required env: TS_AUTHKEY
# Optional env: PROVIDER (e.g. "vast.ai"), BUDGET_USD (default: 0)
set -euo pipefail

export TS_AUTHKEY="${TS_AUTHKEY:?TS_AUTHKEY env var required}"
PROVIDER="${PROVIDER:-unknown}"
BUDGET_USD="${BUDGET_USD:-0}"

# --- Tailscale ---
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up \
  --authkey="$TS_AUTHKEY" \
  --hostname=gpu-research-worker-01 \
  --accept-dns=false

# --- uv ---
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

# --- repo ---
git clone https://github.com/peterlodri-sec/crabcc-autoresearch.git
cd crabcc-autoresearch/worker
uv sync

# --- patch autoresearch LLM client → OpenRouter ---
# expects main_loop.py in cwd (copy from karpathy/autoresearch before running task run)
uv run python patch_llm.py main_loop.py || true

# --- auto-detect GPU info ---
if command -v nvidia-smi &>/dev/null; then
  GPU_TYPE=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | tr -d '\r\n')
  GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l | tr -d ' ')
  MACHINE_TYPE="${GPU_COUNT}x ${GPU_TYPE}"
else
  GPU_TYPE="unknown"
  MACHINE_TYPE="unknown"
fi

# --- export for the run ---
export GPU_TYPE
export MACHINE_TYPE
export PROVIDER
export BUDGET_USD

echo ""
echo "Worker ready."
echo "  GPU:      ${MACHINE_TYPE}"
echo "  Provider: ${PROVIDER}"
echo "  Budget:   \$${BUDGET_USD}"
echo ""
echo "Next steps:"
echo "  export OPENROUTER_API_KEY=sk-or-..."
echo "  export LLM_MODEL=anthropic/claude-sonnet-4-6   # optional"
echo "  export LANGSMITH_API_KEY=ls__...                # optional — enables tracing"
echo "  export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787"
echo "  export RUN_ID=crabcc-run-001"
echo "  task prepare   # one-time tokenizer build"
echo "  task run       # start autonomous loop"
