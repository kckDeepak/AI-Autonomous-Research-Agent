from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.tracing import RunTracer


def test_run_tracer_persists_trace_artifact_and_log(tmp_path: Path) -> None:
    tracer = RunTracer(
        run_id="trace-run-1",
        root_dir=tmp_path / "run_artifacts",
        log_path=tmp_path / "logs" / "run_traces.jsonl",
    )

    with tracer.stage("planner", metadata={"depth": "standard"}):
        pass

    tracer.record_metric("raw_result_count", 3)
    trace_path = tracer.flush(extra={"status": "completed"})

    trace_file = Path(trace_path)
    assert trace_file.exists()

    payload = json.loads(trace_file.read_text(encoding="utf-8"))
    assert payload["run_id"] == "trace-run-1"
    assert payload["metrics"]["raw_result_count"] == 3
    assert len(payload["events"]) == 1
    assert payload["events"][0]["stage"] == "planner"
    assert payload["events"][0]["status"] == "completed"

    log_file = tmp_path / "logs" / "run_traces.jsonl"
    log_lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(log_lines) == 1


@pytest.mark.parametrize("stage_name", ["search", "summarize"])
def test_run_tracer_captures_stage_errors(tmp_path: Path, stage_name: str) -> None:
    tracer = RunTracer(
        run_id="trace-run-2",
        root_dir=tmp_path / "run_artifacts",
        log_path=tmp_path / "logs" / "run_traces.jsonl",
    )

    with pytest.raises(RuntimeError, match="forced failure"):
        with tracer.stage(stage_name):
            raise RuntimeError("forced failure")

    trace_path = tracer.flush(extra={"status": "failed"})
    payload = json.loads(Path(trace_path).read_text(encoding="utf-8"))

    assert payload["events"][0]["stage"] == stage_name
    assert payload["events"][0]["status"] == "failed"
    assert "forced failure" in payload["events"][0]["error"]
