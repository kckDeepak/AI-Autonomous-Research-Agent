from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator


@dataclass(slots=True)
class _StageToken:
    stage: str
    start_ts: datetime
    start_perf: float
    metadata: dict[str, Any]


class RunTracer:
    def __init__(
        self,
        *,
        run_id: str,
        root_dir: Path | None = None,
        log_path: Path | None = None,
    ) -> None:
        self._run_id = run_id
        self._root_dir = root_dir or Path("run_artifacts")
        self._log_path = log_path or Path("logs") / "run_traces.jsonl"
        self._events: list[dict[str, Any]] = []
        self._metrics: dict[str, Any] = {}

    @contextmanager
    def stage(self, stage: str, metadata: dict[str, Any] | None = None) -> Iterator[None]:
        token = _StageToken(
            stage=stage,
            start_ts=datetime.now(UTC),
            start_perf=perf_counter(),
            metadata=metadata or {},
        )
        error: str | None = None
        try:
            yield
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            end_ts = datetime.now(UTC)
            duration_ms = round((perf_counter() - token.start_perf) * 1000, 2)
            self._events.append(
                {
                    "run_id": self._run_id,
                    "stage": token.stage,
                    "status": "failed" if error else "completed",
                    "started_at": token.start_ts.isoformat(),
                    "ended_at": end_ts.isoformat(),
                    "duration_ms": duration_ms,
                    "metadata": token.metadata,
                    "error": error,
                }
            )

    def record_metric(self, key: str, value: Any) -> None:
        self._metrics[key] = value

    def flush(self, extra: dict[str, Any] | None = None) -> str:
        run_dir = self._root_dir / self._run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        trace_path = run_dir / "run_trace.json"

        payload = {
            "run_id": self._run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "events": self._events,
            "metrics": self._metrics,
            "extra": extra or {},
        }
        trace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=True) + "\n")

        return trace_path.as_posix()
