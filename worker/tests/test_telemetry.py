from unittest.mock import patch, MagicMock
from telemetry import report_run, report_start, report_end


def test_report_run_posts_correct_payload():
    with patch("telemetry.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        report_run("run-abc", 7, 2.11, "SUCCESS", api_cost_usd=0.0312)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["run_id"] == "run-abc"
        assert payload["step"] == 7
        assert payload["val_bpb"] == 2.11
        assert payload["status"] == "SUCCESS"
        assert payload["api_cost_usd"] == 0.0312
        assert kwargs["timeout"] == 5


def test_report_run_posts_to_correct_url():
    with patch("telemetry.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        report_run("run-url", 1, None, "CRASHED")
        url = mock_post.call_args[0][0]
        assert url == "http://fake-hetzner:8787/api/telemetry"


def test_report_run_null_val_bpb():
    with patch("telemetry.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        report_run("run-null", 2, None, "REVERTED")
        payload = mock_post.call_args[1]["json"]
        assert payload["val_bpb"] is None


def test_report_run_silent_on_connection_error():
    with patch("telemetry.requests.post", side_effect=ConnectionError("timeout")):
        report_run("run-err", 1, None, "CRASHED")  # must not raise


def test_report_run_silent_on_timeout():
    import requests as req_lib
    with patch("telemetry.requests.post", side_effect=req_lib.Timeout("timed out")):
        report_run("run-timeout", 3, 1.5, "SUCCESS")  # must not raise


def test_report_start_posts_correct_payload():
    with patch("telemetry.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        report_start(
            run_id="run-start-1",
            machine_type="2x RTX 4090",
            gpu_type="RTX 4090",
            provider="vast.ai",
            budget_usd=10.0,
        )
        url = mock_post.call_args[0][0]
        assert url == "http://fake-hetzner:8787/api/runs/start"
        payload = mock_post.call_args[1]["json"]
        assert payload["run_id"] == "run-start-1"
        assert payload["gpu_type"] == "RTX 4090"
        assert payload["provider"] == "vast.ai"
        assert payload["budget_usd"] == 10.0


def test_report_end_posts_correct_payload():
    with patch("telemetry.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        report_end("run-end-1", total_cost_usd=7.84)
        url = mock_post.call_args[0][0]
        assert url == "http://fake-hetzner:8787/api/runs/end"
        payload = mock_post.call_args[1]["json"]
        assert payload["run_id"] == "run-end-1"
        assert payload["total_cost_usd"] == 7.84


def test_report_start_silent_on_error():
    with patch("telemetry.requests.post", side_effect=ConnectionError("down")):
        report_start("run-err", budget_usd=5.0)  # must not raise


def test_report_end_silent_on_error():
    with patch("telemetry.requests.post", side_effect=ConnectionError("down")):
        report_end("run-err", total_cost_usd=3.0)  # must not raise
