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
