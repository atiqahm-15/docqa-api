"""
Tests in this file call the real Gemini API. They require a valid
GOOGLE_API_KEY in the environment and network access, and are excluded from
the default `pytest` run (see pytest.ini). Run them explicitly with:

    pytest -m integration tests/integration -v
"""

import pytest

from app.config import Settings
from app.dependencies import get_chat_model, get_embeddings, get_vectorstore
from app.services import chat_service, document_service


@pytest.fixture
def real_settings(tmp_path):
    return Settings(data_dir=tmp_path)  # picks up GOOGLE_API_KEY from the real environment


@pytest.mark.integration
def test_upload_and_ask_round_trip_with_real_gemini(real_settings, sample_pdf_path):
    embeddings = get_embeddings(real_settings)
    vectorstore = get_vectorstore(embeddings, real_settings)
    chat_model = get_chat_model(real_settings)

    chunks = document_service.chunk_pdf(sample_pdf_path, document_id="integration-doc")
    chunk_count = document_service.embed_and_store(vectorstore, chunks)
    assert chunk_count >= 1

    history = chat_service.get_session_history(real_settings.data_dir / "chat.db", "integration-session")
    result = chat_service.answer_question(vectorstore, chat_model, history, "What is this document about?")

    assert result["answer"]
    assert len(result["sources"]) >= 1
