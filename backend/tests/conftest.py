from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_embeddings():
    return DeterministicFakeEmbedding(size=768)


@pytest.fixture
def sample_pdf_path() -> Path:
    return FIXTURES_DIR / "sample.pdf"


from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_chat_model, get_embeddings
from app.main import app


@pytest.fixture
def test_settings(tmp_path):
    return Settings(_env_file=None, google_api_key="test-key", data_dir=tmp_path)


@pytest.fixture
def client(test_settings, fake_embeddings):
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_embeddings] = lambda: fake_embeddings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
