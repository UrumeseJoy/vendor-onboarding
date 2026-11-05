import pytest

from app import llm


@pytest.fixture(autouse=True)
def offline_defaults(monkeypatch, tmp_path):
    """Tests never call the real Gemini, wherever EXTRACTOR_MODE and the API key in backend/.env point."""
    monkeypatch.setenv("EXTRACTOR_MODE", "mock")
    monkeypatch.setenv("STAGE_DELAY_MS", "0")
    monkeypatch.setenv("DEMO_MODE", "false")  # a test that needs it turns it on
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "extraction-cache"))
    monkeypatch.setenv("SEED_CACHE_DIR", str(tmp_path / "no-seed-cache"))  # a test that wants one sets it

    def no_network(**kwargs):
        raise llm.LLMError("The network is disabled in tests; fake app.llm functions instead.")

    llm._make_client.cache_clear()
    monkeypatch.setattr(llm.genai, "Client", no_network)  # a test that needs a client patches this itself
    yield
    llm._make_client.cache_clear()
