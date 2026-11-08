"""Deployment-readiness behaviour: database URLs, the admin token, SSE headers, vanished uploads."""

import logging
import shutil

import pytest
from fastapi.testclient import TestClient

from app.db import get_engine, normalise_database_url
from app.main import app
from app.settings import storage_dir
from tests.test_api import case_upload, client, run_demo, wait_for_run  # noqa: F401  (client is a fixture)


# ---------- database URL ----------

@pytest.mark.parametrize("given, expected", [
    ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("sqlite:///./x.db", "sqlite:///./x.db"),
])
def test_database_urls_are_converted_to_the_psycopg_driver(given, expected):
    assert normalise_database_url(given) == expected


def test_a_postgres_url_gets_a_psycopg_engine_without_connecting():
    engine = get_engine("postgres://user:secret@localhost:1/none")
    assert engine.dialect.name == "postgresql" and engine.dialect.driver == "psycopg"


def test_unreachable_database_fails_startup_with_a_clear_error_and_no_secret(monkeypatch, caplog):
    monkeypatch.setenv("DATABASE_URL", "postgres://someuser:s3cret-pw@127.0.0.1:1/nodb?connect_timeout=2")
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="Database connection failed"):
            with TestClient(app):
                pass
    logged = caplog.text
    assert "DATABASE_URL" in logged and "OperationalError" in logged
    assert "s3cret-pw" not in logged and "someuser" not in logged and "127.0.0.1" not in logged


# ---------- admin token ----------

def test_reset_needs_no_token_when_none_is_configured(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    assert client.get("/api/health").json()["reset_requires_token"] is False
    assert client.post("/api/admin/reset-demo").status_code == 200


def test_reset_requires_the_token_when_one_is_configured(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("ADMIN_TOKEN", "t0ken")
    run_demo(client, "01_happy_path")
    assert client.get("/api/health").json()["reset_requires_token"] is True
    assert client.post("/api/admin/reset-demo").status_code == 403
    assert client.post("/api/admin/reset-demo", headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert len(client.get("/api/vendors").json()) == 1  # nothing was deleted
    assert client.post("/api/admin/reset-demo", headers={"X-Admin-Token": "t0ken"}).status_code == 200
    assert client.get("/api/vendors").json() == []


def test_a_token_alone_does_not_enable_reset(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "t0ken")  # DEMO_MODE stays false
    assert client.get("/api/health").json()["reset_requires_token"] is False
    assert client.post("/api/admin/reset-demo", headers={"X-Admin-Token": "t0ken"}).status_code == 403


# ---------- SSE behind a proxy ----------

def test_event_streams_ask_proxies_not_to_cache_or_buffer(client):
    started, _ = run_demo(client, "01_happy_path")
    live_or_replay = client.stream("GET", f"/api/runs/{started['run_id']}/events")
    with live_or_replay as response:
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"


def test_event_streams_send_a_keep_alive_ping_every_15_seconds():
    from app.main import SSE_PING_SECONDS
    assert SSE_PING_SECONDS == 15


# ---------- uploads that vanished ----------

def test_a_vanished_upload_is_reported_not_an_error(client):
    data, files = case_upload("08_us_vendor")
    run_id = client.post("/api/vendors", data=data, files=files).json()["run_id"]
    wait_for_run(client, run_id)
    assert client.get(f"/api/runs/{run_id}").json()["document_available"] == {"w9_form.pdf": True, "bank_letter.pdf": True}

    shutil.rmtree(storage_dir() / "uploads")  # what a redeploy on temporary disk does
    run = client.get(f"/api/runs/{run_id}")
    assert run.status_code == 200 and run.json()["document_available"] == {"w9_form.pdf": False, "bank_letter.pdf": False}
    gone = client.get(f"/api/runs/{run_id}/documents/w9_form.pdf")
    assert gone.status_code == 410 and gone.json()["detail"] == "Document no longer available."


def test_sample_documents_are_always_available(client):
    started, _ = run_demo(client, "01_happy_path")
    shutil.rmtree(storage_dir() / "uploads", ignore_errors=True)
    run = client.get(f"/api/runs/{started['run_id']}").json()
    assert run["document_available"] and all(run["document_available"].values())
