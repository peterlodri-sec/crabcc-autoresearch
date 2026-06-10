#!/bin/bash
# Spot-instance bootstrap. Run as cloud-init user-data or paste into provider startup script.
# Required env: TS_AUTHKEY
# Optional env: PROVIDER, BUDGET_USD
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

# --- this repo ---
git clone https://github.com/peterlodri-sec/crabcc-autoresearch.git
cd crabcc-autoresearch/worker
uv sync

# --- karpathy/autoresearch (provides main_loop.py, prepare.py, train.py) ---
git clone --depth 1 https://github.com/karpathy/autoresearch.git /tmp/autoresearch
cp /tmp/autoresearch/main_loop.py .
cp /tmp/autoresearch/prepare.py . 2>/dev/null || true
cp /tmp/autoresearch/train.py .  2>/dev/null || true

# --- data directory ---
mkdir -p data

# lambda slot: census dataset for λ-term normalization classification
curl -fsSL \
  "https://raw.githubusercontent.com/peterlodri-sec/lambda-normalization-census/main/data/census_dataset.csv" \
  -o data/census_dataset.csv

# charlm slot: Shakespeare corpus from autoresearch (fallback to char-rnn copy)
if [ -f /tmp/autoresearch/data/input.txt ]; then
  cp /tmp/autoresearch/data/input.txt data/input.txt
else
  curl -fsSL \
    "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt" \
    -o data/input.txt
fi

# --- patch main_loop.py → OpenRouter + LangSmith ---
uv run python patch_llm.py main_loop.py

# --- auto-detect GPU ---
if command -v nvidia-smi &>/dev/null; then
  GPU_TYPE=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | tr -d '\r\n')
  GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l | tr -d ' ')
else
  GPU_TYPE="unknown"
  GPU_COUNT="1"
fi

export GPU_TYPE GPU_COUNT PROVIDER BUDGET_USD

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Worker ready"
echo "  GPU:      ${GPU_COUNT}x ${GPU_TYPE}"
echo "  Provider: ${PROVIDER}"
echo "  Budget:   \$${BUDGET_USD}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Set these, then run:"
echo ""
echo "  export OPENROUTER_API_KEY=sk-or-..."
echo "  export GITHUB_TOKEN=github_pat_..."
echo "  export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787"
echo "  export RUN_ID=crabcc-run-\$(date +%Y%m%d-%H%M)"
echo ""
echo "  # optional"
echo "  export LLM_MODEL=anthropic/claude-sonnet-4-6"
echo "  export LANGSMITH_API_KEY=ls__..."
echo ""
echo "  task prepare   # one-time tokenizer build (~2 min)"
echo "  task run       # launches both slots in parallel"
