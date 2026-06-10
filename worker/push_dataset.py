import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

_MAX_RETRIES = 3

DATASETS_REPO = os.environ.get(
    "DATASETS_REPO", "peterlodri-sec/lambda-normalization-census"
)
GITHUB_API = "https://api.github.com"
BRANCH = "main"


def _headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _best_val_bpb(tsv_path: str) -> Optional[float]:
    p = Path(tsv_path)
    if not p.exists():
        return None
    try:
        lines = p.read_text().splitlines()
        if len(lines) < 2:
            return None
        header = lines[0].split("\t")
        if "val_bpb" not in header:
            return None
        col = header.index("val_bpb")
        values = []
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) > col and parts[col] not in ("", "None", "null"):
                try:
                    values.append(float(parts[col]))
                except ValueError:
                    pass
        return min(values) if values else None
    except Exception:
        return None


def _read_artifact(path: str, fallback: str) -> str:
    p = Path(path)
    return p.read_text() if p.exists() else fallback


def push_dataset(
    run_id: str,
    results_tsv_path: str = "results.tsv",
    train_py_path: str = "train.py",
    gpu_type: str = "",
    provider: str = "",
    total_cost_usd: float = 0.0,
    budget_usd: float = 0.0,
    langsmith_run_url: Optional[str] = None,
) -> None:
    for attempt in range(_MAX_RETRIES):
        try:
            _push(
                run_id,
                results_tsv_path,
                train_py_path,
                gpu_type,
                provider,
                total_cost_usd,
                budget_usd,
                langsmith_run_url,
            )
            return
        except requests.HTTPError as exc:
            # 422 means the ref advanced under us (parallel run); retry with fresh HEAD
            if exc.response is not None and exc.response.status_code == 422 and attempt < _MAX_RETRIES - 1:
                delay = 2 ** attempt + 1
                print(f"[push_dataset] ref conflict, retrying in {delay}s…", file=sys.stderr)
                time.sleep(delay)
            else:
                print(f"[push_dataset] warning: {exc}", file=sys.stderr)
                return
        except Exception as exc:
            print(f"[push_dataset] warning: {exc}", file=sys.stderr)
            return


def _push(
    run_id: str,
    results_tsv_path: str,
    train_py_path: str,
    gpu_type: str,
    provider: str,
    total_cost_usd: float,
    budget_usd: float,
    langsmith_run_url: Optional[str],
) -> None:
    now = datetime.now(timezone.utc)
    # Use run_id directly so parallel slots get distinct dirs even within the same minute
    dir_prefix = f"data/autoresearch/{run_id}"
    headers = _headers()
    repo = DATASETS_REPO
    api = GITHUB_API

    results_content = _read_artifact(results_tsv_path, "# no results.tsv found\n")
    train_content = _read_artifact(train_py_path, "# no train.py found\n")
    meta: dict = {
        "$schema": "https://github.com/peterlodri-sec/crabcc-autoresearch/blob/main/worker/run_meta_schema.json",
        "run_id": run_id,
        "gpu_type": gpu_type,
        "provider": provider,
        "budget_usd": budget_usd,
        "total_cost_usd": total_cost_usd,
        "best_val_bpb": _best_val_bpb(results_tsv_path),
        "published_at": now.isoformat(),
        "digests": {
            "results.tsv": _sha256(results_content),
            "train.py": _sha256(train_content),
        },
    }
    if langsmith_run_url:
        meta["langsmith_run_url"] = langsmith_run_url
    files = {
        "results.tsv": results_content,
        "train.py": train_content,
        "run_meta.json": json.dumps(meta, indent=2),
    }

    # get current HEAD
    r = requests.get(
        f"{api}/repos/{repo}/git/ref/heads/{BRANCH}", headers=headers, timeout=15
    )
    r.raise_for_status()
    head_sha = r.json()["object"]["sha"]

    # get base tree sha
    r = requests.get(
        f"{api}/repos/{repo}/git/commits/{head_sha}", headers=headers, timeout=15
    )
    r.raise_for_status()
    base_tree_sha = r.json()["tree"]["sha"]

    # create blobs
    tree_items = []
    for filename, content in files.items():
        r = requests.post(
            f"{api}/repos/{repo}/git/blobs",
            headers=headers,
            json={"content": _b64(content), "encoding": "base64"},
            timeout=30,
        )
        r.raise_for_status()
        tree_items.append(
            {
                "path": f"{dir_prefix}/{filename}",
                "mode": "100644",
                "type": "blob",
                "sha": r.json()["sha"],
            }
        )

    # create tree
    r = requests.post(
        f"{api}/repos/{repo}/git/trees",
        headers=headers,
        json={"base_tree": base_tree_sha, "tree": tree_items},
        timeout=30,
    )
    r.raise_for_status()
    new_tree_sha = r.json()["sha"]

    # create commit
    r = requests.post(
        f"{api}/repos/{repo}/git/commits",
        headers=headers,
        json={
            "message": f"dataset: autoresearch {run_id} — {date_tag}",
            "tree": new_tree_sha,
            "parents": [head_sha],
        },
        timeout=30,
    )
    r.raise_for_status()
    new_commit_sha = r.json()["sha"]

    # advance the branch ref
    r = requests.patch(
        f"{api}/repos/{repo}/git/refs/heads/{BRANCH}",
        headers=headers,
        json={"sha": new_commit_sha},
        timeout=15,
    )
    r.raise_for_status()

    print(f"[push_dataset] pushed {dir_prefix}/ to {repo} ({new_commit_sha[:8]})")


if __name__ == "__main__":
    _url = Path(".langsmith_run_url").read_text().strip() if Path(".langsmith_run_url").exists() else None
    _run_id = os.environ.get("RUN_ID", "unnamed")
    _gpu = os.environ.get("GPU_TYPE", "")
    _provider = os.environ.get("PROVIDER", "")
    _cost = float(os.environ.get("TOTAL_COST_USD", "0"))
    _budget = float(os.environ.get("BUDGET_USD", "0"))

    # Publish each slot that has a results.tsv, fall back to root CWD for single-slot runs
    from agent import SLOTS
    published = False
    for slot in SLOTS:
        slot_results = Path(f"slots/{slot}/results.tsv")
        slot_train = Path(f"slots/{slot}/train.py")
        if slot_results.exists():
            push_dataset(
                run_id=f"{_run_id}-{slot}",
                results_tsv_path=str(slot_results),
                train_py_path=str(slot_train),
                gpu_type=_gpu,
                provider=_provider,
                total_cost_usd=_cost,
                budget_usd=_budget,
                langsmith_run_url=_url,
            )
            published = True

    if not published:
        push_dataset(
            run_id=_run_id,
            gpu_type=_gpu,
            provider=_provider,
            total_cost_usd=_cost,
            budget_usd=_budget,
            langsmith_run_url=_url,
        )
