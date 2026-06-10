import os
import sys
from typing import Optional

import requests

RECEIVER_URL = os.environ.get("CRABCC_RECEIVER_URL", "http://100.64.0.1:8787")


def _post(path: str, payload: dict) -> None:
    try:
        requests.post(f"{RECEIVER_URL}{path}", json=payload, timeout=5)
    except Exception as exc:
        print(f"[telemetry] warning: {exc}", file=sys.stderr)


def report_start(
    run_id: str,
    machine_type: str = "",
    gpu_type: str = "",
    provider: str = "",
    budget_usd: float = 0.0,
) -> None:
    _post(
        "/api/runs/start",
        {
            "run_id": run_id,
            "machine_type": machine_type,
            "gpu_type": gpu_type,
            "provider": provider,
            "budget_usd": budget_usd,
        },
    )


def report_run(
    run_id: str,
    step: int,
    val_bpb: Optional[float],
    status: str,
    diff: str = "",
    api_cost_usd: float = 0.0,
) -> None:
    _post(
        "/api/telemetry",
        {
            "run_id": run_id,
            "step": int(step),
            "val_bpb": float(val_bpb) if val_bpb is not None else None,
            "status": status,
            "diff": diff,
            "api_cost_usd": api_cost_usd,
        },
    )


def report_end(run_id: str, total_cost_usd: float = 0.0) -> None:
    _post(
        "/api/runs/end",
        {
            "run_id": run_id,
            "total_cost_usd": total_cost_usd,
        },
    )


if __name__ == "__main__":
    # CLI hook for autoresearch loop:
    # python telemetry.py <step> <val_bpb|None> <status> [api_cost_usd]
    if len(sys.argv) >= 4:
        report_run(
            run_id=os.environ.get("RUN_ID", "unnamed"),
            step=sys.argv[1],
            val_bpb=sys.argv[2] if sys.argv[2] != "None" else None,
            status=sys.argv[3],
            api_cost_usd=float(sys.argv[4]) if len(sys.argv) > 4 else 0.0,
        )
