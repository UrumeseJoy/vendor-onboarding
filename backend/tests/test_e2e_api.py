"""End to end through the HTTP API, on a fresh database: reset the demo, run all 8 demo cases in
index.json order (case 05 as a resubmission of case 04's vendor), follow each live SSE stream to
"done", and check every final status against expected.json, plus the stats and vendor run histories.
"""

import json
from collections import Counter

from fastapi.testclient import TestClient

from app.demo_cases import load_expected, load_index
from app.main import app


def read_stream(client, run_id) -> list[tuple[str, dict]]:
    events, event_type = [], None
    with client.stream("GET", f"/api/runs/{run_id}/events") as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type:
                events.append((event_type, json.loads(line.split(":", 1)[1].strip())))
                event_type = None
    return events


def test_all_demo_cases_end_to_end_through_the_api(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/e2e.db")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("DEMO_MODE", "true")

    with TestClient(app) as client:
        assert client.post("/api/admin/reset-demo").status_code == 200
        assert client.get("/api/vendors").json() == []

        vendor_of: dict[str, str] = {}   # case_id -> vendor ID it ran under
        history: dict[str, list[str]] = {}  # vendor ID -> statuses of its runs, in order
        for entry in load_index():
            case_id, expected = entry["case_id"], load_expected(entry["case_id"])
            original = expected.get("resubmission_of")
            body = {"vendor_id": vendor_of[original]} if original else None
            started = client.post(f"/api/demo-cases/{case_id}/run", json=body)
            assert started.status_code == 202, started.text
            run_id, vendor_id = started.json()["run_id"], started.json()["vendor_id"]
            if original:
                assert vendor_id == vendor_of[original]  # same vendor, new run

            events = read_stream(client, run_id)
            assert events[-1][0] == "done", (case_id, events[-1:])
            finished = [d["stage"] for kind, d in events if kind == "stage" and d["status"] != "RUNNING"]
            assert len(finished) == 8, (case_id, finished)
            status = events[-1][1]["decision"]["status"]
            assert status == expected["expected_status"], case_id
            assert client.get(f"/api/runs/{run_id}").json()["decision"]["status"] == status

            vendor_of[case_id] = vendor_id
            history.setdefault(vendor_id, []).append(status)

        # stats: latest status per vendor, every run counted
        stats = client.get("/api/stats").json()
        latest = Counter(statuses[-1] for statuses in history.values())
        assert stats["status_counts"] == {s: latest.get(s, 0) for s in ("APPROVED", "PENDING", "REJECTED")}
        assert stats["total_vendors"] == len(history) == 7
        assert stats["total_runs"] == len(load_index()) == 8

        # vendor histories, including the resubmitted vendor's two runs
        for vendor_id, statuses in history.items():
            vendor = client.get(f"/api/vendors/{vendor_id}").json()
            assert [r["status"] for r in vendor["runs"]] == statuses
            assert [r["run_number"] for r in vendor["runs"]] == list(range(1, len(statuses) + 1))
            assert vendor["run_count"] == len(statuses) and vendor["status"] == statuses[-1]
            assert vendor["latest_run_id"] == vendor["runs"][-1]["run_id"]
        assert history[vendor_of["04_wrong_document"]] == ["PENDING", "APPROVED"]
