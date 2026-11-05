"""In-memory, thread-safe record of what each live run has published, for the SSE stream.

Event types:
  "stage" - a StageResult (published when a stage starts and when it finishes)
  "done"  - the final Decision and run_id
  "error" - processing failed (the run is still saved as PENDING)

Finished runs are forgotten after 10 minutes; after that the stream is rebuilt from the database.
This lives in one process's memory, which is fine for a single-server demo.
"""

import threading
import time
from dataclasses import dataclass, field

FINAL_EVENTS = {"done", "error"}
KEEP_FINISHED_SECONDS = 10 * 60


@dataclass
class _RunLog:
    events: list[dict] = field(default_factory=list)
    done: bool = False
    finished_at: float | None = None
    meta: dict = field(default_factory=dict)


class RunEvents:
    def __init__(self, keep_finished_seconds: float = KEEP_FINISHED_SECONDS):
        self._lock = threading.Lock()
        self._runs: dict[str, _RunLog] = {}
        self._keep = keep_finished_seconds

    def create(self, run_id: str, **meta) -> None:
        """Register a run before it starts. meta: e.g. upload_id and filenames for document serving."""
        with self._lock:
            self._drop_old()
            self._runs[run_id] = _RunLog(meta=meta)

    def publish(self, run_id: str, event_type: str, data: dict) -> None:
        with self._lock:
            log = self._runs.setdefault(run_id, _RunLog())
            log.events.append({"type": event_type, "data": data})
            if event_type in FINAL_EVENTS:
                log.done, log.finished_at = True, time.monotonic()

    def exists(self, run_id: str) -> bool:
        with self._lock:
            self._drop_old()
            return run_id in self._runs

    def since(self, run_id: str, index: int) -> tuple[list[dict], bool]:
        """Events published after position `index`, and whether the run has finished."""
        with self._lock:
            log = self._runs.get(run_id)
            if log is None:
                return [], True
            return list(log.events[index:]), log.done

    def meta(self, run_id: str) -> dict | None:
        with self._lock:
            log = self._runs.get(run_id)
            return dict(log.meta) if log else None

    def _drop_old(self) -> None:
        """Forget finished runs older than the keep time. Caller holds the lock."""
        cutoff = time.monotonic() - self._keep
        for run_id in [r for r, log in self._runs.items() if log.done and log.finished_at < cutoff]:
            del self._runs[run_id]


registry = RunEvents()
