import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

DATASETS_REPO = os.environ.get(
    "DATASETS_REPO", "peterlodri-sec/lambda-normalization-census"
)
GITHUB_API = "https://api.github.com"
BRANCH = "main"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


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
) -> None:
    try:
        _push(
            run_id,
            results_tsv_path,
            train_py_path,
            gpu_type,
            provider,
            total_cost_usd,
            budget_usd,
        )
    except Exception as exc:
        print(f"[push_dataset] warning: {exc}", file=sys.stderr)


def _push(
    run_id: str,
    results_tsv_path: str,
    train_py_path: str,
    gpu_type: str,
    provider: str,
    total_cost_usd: float,
    budget_usd: float,
) -> None:
    now = datetime.now(timezone.utc)
    date_tag = now.strftime("%Y%m%d-%H%M")
    dir_prefix = f"data/autoresearch/autoresearch-{date_tag}"
    headers = _headers()
    repo = DATASETS_REPO
    api = GITHUB_API

    results_content = _read_artifact(results_tsv_path, "# no results.tsv found\n")
    train_content = _read_artifact(train_py_path, "# no train.py found\n")
    meta = {
        "run_id": run_id,
        "gpu_type": gpu_type,
        "provider": provider,
        "budget_usd": budget_usd,
        "total_cost_usd": total_cost_usd,
        "best_val_bpb": _best_val_bpb(results_tsv_path),
        "published_at": now.isoformat(),
    }
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
    push_dataset(
        run_id=os.environ.get("RUN_ID", "unnamed"),
        gpu_type=os.environ.get("GPU_TYPE", ""),
        provider=os.environ.get("PROVIDER", ""),
        total_cost_usd=float(os.environ.get("TOTAL_COST_USD", "0")),
        budget_usd=float(os.environ.get("BUDGET_USD", "0")),
    )
