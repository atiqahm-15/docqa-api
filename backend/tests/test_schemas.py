import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, ChatResponse, DocumentUploadResponse, SourceCitation


def test_chat_request_requires_question():
    with pytest.raises(ValidationError):
        ChatRequest()


def test_chat_request_session_id_defaults_to_none():
    request = ChatRequest(question="What is this document about?")
    assert request.session_id is None


def test_chat_response_accepts_list_of_sources():
    response = ChatResponse(
        answer="It's about LangChain.",
        sources=[SourceCitation(filename="a.pdf", page=1)],
        session_id="sess-1",
    )
    assert response.sources[0].page == 1


def test_document_upload_response_fields():
    response = DocumentUploadResponse(document_id="d1", filename="a.pdf", chunk_count=3)
    assert response.chunk_count == 3
