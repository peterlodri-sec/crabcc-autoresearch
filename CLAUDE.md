# crabcc-autoresearch

Autonomous ML training loop (Karpathy autoresearch) — trains a small transformer
to classify λ-term normalization status using the lambda-normalization-census dataset.

## components

- `worker/` — runs on ephemeral GPU spot instance (Vast.ai)
- `receiver/` — runs on Hetzner VM, serves research.crabcc.app dashboard
- `nix/` — drop-in NixOS module for nix-base

## quick start (receiver — hetzner)

```bash
cd receiver && task serve
```

## quick start (worker — gpu instance)

```bash
export TS_AUTHKEY=tskey-auth-...
export OPENROUTER_API_KEY=sk-or-...
export LLM_MODEL=anthropic/claude-sonnet-4-6
export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787
export GITHUB_TOKEN=github_pat_...
export RUN_ID=crabcc-run-$(date +%Y%m%d-%H%M)
export BUDGET_USD=12
export PROVIDER=vast.ai

cd worker && task run
```

## tests

```bash
cd receiver && uv sync --dev && task test
cd worker   && uv sync --dev && task test
```

## nix integration

```nix
imports = [ ./nix/crabcc-research-sync.nix ];
```
