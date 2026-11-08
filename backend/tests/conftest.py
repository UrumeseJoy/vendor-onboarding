import os

import pytest
from sqlmodel import SQLModel

from app import llm
from app.db import get_engine


@pytest.fixture(autouse=True)
def offline_defaults(monkeypatch, tmp_path):
    """Tests never call the real Gemini, wherever EXTRACTOR_MODE and the API key in backend/.env point."""
    monkeypatch.setenv("EXTRACTOR_MODE", "mock")
    monkeypatch.setenv("STAGE_DELAY_MS", "0")
    monkeypatch.setenv("DEMO_MODE", "false")  # a test that needs it turns it on
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "extraction-cache"))
    monkeypatch.setenv("SEED_CACHE_DIR", str(tmp_path / "no-seed-cache"))  # a test that wants one sets it
    # Never touch the developer's real database, whatever backend/.env says.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/default-test.db")

    def no_network(**kwargs):
        raise llm.LLMError("The network is disabled in tests; fake app.llm functions instead.")

    llm._make_client.cache_clear()
    monkeypatch.setattr(llm.genai, "Client", no_network)  # a test that needs a client patches this itself
    yield
    llm._make_client.cache_clear()


@pytest.fixture
def db_url(tmp_path):
    """The database a test runs on: a fresh SQLite file, or, with TEST_ON_POSTGRES=1, the Postgres database in
    POSTGRES_TEST_URL (backend/.env). On Postgres our two tables are dropped before and after the test, so it
    starts empty and is left empty."""
    if os.getenv("TEST_ON_POSTGRES") != "1":
        yield f"sqlite:///{tmp_path}/test.db"
        return
    url = os.getenv("POSTGRES_TEST_URL", "")
    assert url, "TEST_ON_POSTGRES=1 needs POSTGRES_TEST_URL in backend/.env"
    engine = get_engine(url)
    SQLModel.metadata.drop_all(engine)
    yield url
    SQLModel.metadata.drop_all(engine)
    engine.dispose()
