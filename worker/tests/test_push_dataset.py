import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from push_dataset import _best_val_bpb, push_dataset


def _mock_response(data: dict, status: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = data
    m.raise_for_status = MagicMock()
    return m


def _make_responses():
    return [
        _mock_response({"object": {"sha": "head-sha-abc"}}),  # GET ref
        _mock_response({"tree": {"sha": "base-tree-sha"}}),  # GET commit
        _mock_response({"sha": "blob-sha-1"}),  # POST blob results.tsv
        _mock_response({"sha": "blob-sha-2"}),  # POST blob train.py
        _mock_response({"sha": "blob-sha-3"}),  # POST blob run_meta.json
        _mock_response({"sha": "new-tree-sha"}),  # POST tree
        _mock_response({"sha": "new-commit-sha-12345678"}),  # POST commit
        _mock_response({"sha": "new-commit-sha-12345678"}),  # PATCH ref
    ]


def test_push_dataset_calls_github_api():
    with (
        patch("push_dataset.requests.get") as mock_get,
        patch("push_dataset.requests.post") as mock_post,
        patch("push_dataset.requests.patch") as mock_patch,
    ):
        mock_get.side_effect = [
            _mock_response({"object": {"sha": "head-sha"}}),
            _mock_response({"tree": {"sha": "tree-sha"}}),
        ]
        mock_post.return_value = _mock_response({"sha": "sha-x"})
        mock_patch.return_value = _mock_response({"sha": "sha-x"})

        push_dataset(
            "run-001", gpu_type="RTX 4090", provider="vast.ai", budget_usd=12.0
        )

        assert mock_get.call_count == 2
        assert mock_post.call_count == 5  # 3 blobs + 1 tree + 1 commit
        assert mock_patch.call_count == 1


def test_push_dataset_dir_prefix_pattern():
    with (
        patch("push_dataset.requests.get") as mock_get,
        patch("push_dataset.requests.post") as mock_post,
        patch("push_dataset.requests.patch") as mock_patch,
    ):
        mock_get.side_effect = [
            _mock_response({"object": {"sha": "head-sha"}}),
            _mock_response({"tree": {"sha": "tree-sha"}}),
        ]
        mock_post.return_value = _mock_response({"sha": "sha-x"})
        mock_patch.return_value = _mock_response({"sha": "sha-x"})

        push_dataset("run-002")

        # check that tree POST contains paths under datasets/autoresearch-YYYYMMDD-HHMM/
        tree_call = [c for c in mock_post.call_args_list if "trees" in str(c)][0]
        tree_items = tree_call.kwargs["json"]["tree"]
        paths = [item["path"] for item in tree_items]
        assert any(p.startswith("datasets/autoresearch-") for p in paths)
        assert any(p.endswith("results.tsv") for p in paths)
        assert any(p.endswith("train.py") for p in paths)
        assert any(p.endswith("run_meta.json") for p in paths)


def test_push_dataset_run_meta_contains_correct_fields():
    with (
        patch("push_dataset.requests.get") as mock_get,
        patch("push_dataset.requests.post") as mock_post,
        patch("push_dataset.requests.patch") as mock_patch,
    ):
        mock_get.side_effect = [
            _mock_response({"object": {"sha": "head-sha"}}),
            _mock_response({"tree": {"sha": "tree-sha"}}),
        ]
        mock_post.return_value = _mock_response({"sha": "sha-x"})
        mock_patch.return_value = _mock_response({"sha": "sha-x"})

        push_dataset(
            "run-meta-test",
            gpu_type="A100",
            provider="runpod",
            budget_usd=15.0,
            total_cost_usd=9.5,
        )

        # find the run_meta.json blob POST
        import base64

        meta_blob_call = None
        for c in mock_post.call_args_list:
            if "blobs" in str(c):
                raw = base64.b64decode(c.kwargs["json"]["content"]).decode()
                if "run_id" in raw:
                    meta_blob_call = json.loads(raw)
                    break

        assert meta_blob_call is not None
        assert meta_blob_call["run_id"] == "run-meta-test"
        assert meta_blob_call["gpu_type"] == "A100"
        assert meta_blob_call["provider"] == "runpod"
        assert meta_blob_call["budget_usd"] == 15.0
        assert meta_blob_call["total_cost_usd"] == 9.5


def test_push_dataset_silent_on_http_error():
    with patch(
        "push_dataset.requests.get", side_effect=ConnectionError("network down")
    ):
        push_dataset("run-err")  # must not raise


def test_push_dataset_silent_on_auth_failure():
    import requests as req_lib

    err_response = MagicMock()
    err_response.raise_for_status.side_effect = req_lib.HTTPError("401 Unauthorized")

    with patch("push_dataset.requests.get", return_value=err_response):
        push_dataset("run-auth-err")  # must not raise


def test_push_dataset_reads_real_results_tsv():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
        f.write("step\tval_bpb\tstatus\n")
        f.write("1\t2.50\tSUCCESS\n")
        f.write("2\t2.30\tSUCCESS\n")
        f.write("3\t2.10\tSUCCESS\n")
        tsv_path = f.name

    try:
        with (
            patch("push_dataset.requests.get") as mock_get,
            patch("push_dataset.requests.post") as mock_post,
            patch("push_dataset.requests.patch") as mock_patch,
        ):
            mock_get.side_effect = [
                _mock_response({"object": {"sha": "head-sha"}}),
                _mock_response({"tree": {"sha": "tree-sha"}}),
            ]
            mock_post.return_value = _mock_response({"sha": "sha-x"})
            mock_patch.return_value = _mock_response({"sha": "sha-x"})

            push_dataset("run-tsv", results_tsv_path=tsv_path)

            # run_meta.json blob should have best_val_bpb=2.10
            import base64

            for c in mock_post.call_args_list:
                if "blobs" in str(c):
                    raw = base64.b64decode(c.kwargs["json"]["content"]).decode()
                    if "best_val_bpb" in raw:
                        meta = json.loads(raw)
                        assert meta["best_val_bpb"] == 2.10
                        break
    finally:
        os.unlink(tsv_path)


def test_best_val_bpb_missing_file():
    assert _best_val_bpb("/nonexistent/results.tsv") is None


def test_best_val_bpb_no_val_bpb_column():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
        f.write("step\tstatus\n1\tSUCCESS\n")
        tsv_path = f.name
    try:
        assert _best_val_bpb(tsv_path) is None
    finally:
        os.unlink(tsv_path)


def test_best_val_bpb_returns_minimum():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
        f.write("step\tval_bpb\n")
        f.write("1\t3.0\n2\t1.5\n3\t2.0\n")
        tsv_path = f.name
    try:
        assert _best_val_bpb(tsv_path) == 1.5
    finally:
        os.unlink(tsv_path)
