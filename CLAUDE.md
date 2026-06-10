# crabcc-autoresearch

Autonomous ML training loop (Karpathy autoresearch) with telemetry to Hetzner VM.

## Components
- `worker/` — runs on ephemeral GPU spot instance
- `receiver/` — runs on Hetzner VM, serves research.crabcc.app
- `nix/` — drop-in module for nix-base

## Quick start (Hetzner)
cd receiver && task serve

## Quick start (GPU worker)
export TS_AUTHKEY=tskey-auth-...
export ANTHROPIC_API_KEY=sk-ant-...
export CRABCC_RECEIVER_URL=http://<hetzner-tailscale-ip>:8787
export RUN_ID=crabcc-run-001
cd worker && task run

## NixOS integration
Copy nix/crabcc-research-sync.nix into nix-base and import in the host config.
