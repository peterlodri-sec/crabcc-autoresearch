"""
Run orchestrator: launches 1–2 autoresearch slots in parallel under a LangSmith
parent trace. Each slot gets an isolated CWD and its own run_id.
"""

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

SLOTS: dict[str, str] = {
    "lambda": "programs/lambda_normalization.md",
    "charlm": "programs/char_lm.md",
}


def _langsmith_parent(
    run_id: str,
    gpu_type: str,
    provider: str,
    budget_usd: float,
    active_slots: list[str],
) -> tuple[Optional[object], Optional[str]]:
    if not os.environ.get("LANGSMITH_API_KEY"):
        return None, None
    try:
        from langsmith.run_trees import RunTree

        project = os.environ.get("LANGSMITH_PROJECT", "crabcc-autoresearch")
        tree = RunTree(
            name=f"crabcc/{run_id}",
            run_type="chain",
            inputs={
                "run_id": run_id,
                "gpu_type": gpu_type,
                "provider": provider,
                "budget_usd": budget_usd,
                "slots": active_slots,
            },
            project_name=project,
        )
        tree.post()
        return tree, f"https://smith.langchain.com/runs/{tree.id}"
    except Exception as exc:
        print(f"[agent] langsmith init: {exc}", file=sys.stderr)
        return None, None


def _setup_slot_dir(slot: str, program_src: Path) -> Path:
    slot_dir = Path(f"slots/{slot}")
    slot_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(program_src, slot_dir / "program.md")

    # Symlink main_loop.py and data/ from the parent worker dir so the patched
    # script and census dataset are reachable without copying large files.
    for name in ("main_loop.py", "data"):
        src = Path(name).resolve()
        link = slot_dir / name
        if src.exists() and not link.exists():
            link.symlink_to(src)

    return slot_dir


def _run_slot(
    slot: str,
    base_run_id: str,
    base_env: dict[str, str],
    parent_run_id: Optional[str],
) -> dict:
    run_id = f"{base_run_id}-{slot}"
    program_src = Path(SLOTS[slot])
    if not program_src.exists():
        print(f"[agent] missing program {program_src}, skipping slot {slot}", file=sys.stderr)
        return {"slot": slot, "run_id": run_id, "exit_code": -1, "elapsed_seconds": 0.0}

    slot_dir = _setup_slot_dir(slot, program_src)

    env = {**base_env, "RUN_ID": run_id}
    if parent_run_id:
        env["LANGSMITH_PARENT_RUN_ID"] = parent_run_id

    print(f"[agent] slot {slot} starting → {run_id}")
    t0 = time.perf_counter()
    result = subprocess.run([sys.executable, "main_loop.py"], cwd=slot_dir, env=env)
    elapsed = round(time.perf_counter() - t0, 1)
    print(f"[agent] slot {slot} done in {elapsed}s (exit {result.returncode})")

    return {
        "slot": slot,
        "run_id": run_id,
        "exit_code": result.returncode,
        "elapsed_seconds": elapsed,
        "results_tsv": str(slot_dir / "results.tsv"),
        "train_py": str(slot_dir / "train.py"),
    }


def run(
    base_run_id: str,
    gpu_type: str = "",
    provider: str = "",
    budget_usd: float = 0.0,
    slots: Optional[list[str]] = None,
) -> list[dict]:
    """Launch slots in parallel under a single LangSmith parent trace."""
    active = [s for s in (slots or list(SLOTS.keys())) if s in SLOTS]
    if not active:
        print("[agent] no valid slots", file=sys.stderr)
        return []

    tree, parent_url = _langsmith_parent(base_run_id, gpu_type, provider, budget_usd, active)
    parent_id = str(tree.id) if tree else None

    base_env = os.environ.copy()
    results: dict[str, dict] = {}

    def _launch(slot: str) -> None:
        results[slot] = _run_slot(slot, base_run_id, base_env, parent_id)

    threads = [threading.Thread(target=_launch, args=(s,), daemon=True) for s in active]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if tree is not None:
        try:
            tree.end(outputs={s: r.get("exit_code") for s, r in results.items()})
            tree.patch()
        except Exception as exc:
            print(f"[agent] langsmith close: {exc}", file=sys.stderr)

    if parent_url:
        Path(".langsmith_run_url").write_text(parent_url)
        print(f"[agent] langsmith: {parent_url}")

    return list(results.values())


if __name__ == "__main__":
    slot_results = run(
        base_run_id=os.environ.get("RUN_ID", "unnamed"),
        gpu_type=os.environ.get("GPU_TYPE", ""),
        provider=os.environ.get("PROVIDER", ""),
        budget_usd=float(os.environ.get("BUDGET_USD", "0")),
    )
    failed = [r for r in slot_results if r.get("exit_code", -1) != 0]
    sys.exit(1 if failed else 0)
