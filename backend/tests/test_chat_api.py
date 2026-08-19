from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.dependencies import get_chat_model


def _upload_sample(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        return client.post("/documents/upload", files={"file": ("sample.pdf", f, "application/pdf")})


def test_chat_without_documents_returns_400(client):
    response = client.post("/chat", json={"question": "What is this about?"})
    assert response.status_code == 400


def test_chat_returns_answer_with_sources(client, sample_pdf_path):
    _upload_sample(client, sample_pdf_path)
    client.app.dependency_overrides[get_chat_model] = lambda: FakeListChatModel(
        responses=["LangChain helps build LLM apps."]
    )

    response = client.post("/chat", json={"question": "What is LangChain?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "LangChain helps build LLM apps."
    assert body["session_id"]
    assert len(body["sources"]) >= 1


def test_chat_reuses_provided_session_id(client, sample_pdf_path):
    _upload_sample(client, sample_pdf_path)
    client.app.dependency_overrides[get_chat_model] = lambda: FakeListChatModel(
        responses=["First answer.", "standalone question", "Second answer."]
    )

    first = client.post("/chat", json={"question": "What is LangChain?"})
    session_id = first.json()["session_id"]

    second = client.post("/chat", json={"question": "What about agents?", "session_id": session_id})

    assert second.status_code == 200
    assert second.json()["session_id"] == session_id


def test_get_history_returns_messages_for_known_session(client, sample_pdf_path):
    _upload_sample(client, sample_pdf_path)
    client.app.dependency_overrides[get_chat_model] = lambda: FakeListChatModel(
        responses=["LangChain helps build LLM apps."]
    )
    chat_response = client.post("/chat", json={"question": "What is LangChain?"})
    session_id = chat_response.json()["session_id"]

    response = client.get(f"/chat/{session_id}/history")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "human"
    assert body["messages"][1]["role"] == "ai"


def test_get_history_returns_404_for_unknown_session(client):
    response = client.get("/chat/nonexistent-session/history")
    assert response.status_code == 404


def test_chat_with_unknown_document_id_returns_404(client, sample_pdf_path):
    _upload_sample(client, sample_pdf_path)

    response = client.post(
        "/chat", json={"question": "What is this about?", "document_id": "does-not-exist"}
    )

    assert response.status_code == 404


def test_chat_scoped_to_document_id_returns_answer(client, sample_pdf_path):
    upload = _upload_sample(client, sample_pdf_path)
    document_id = upload.json()["document_id"]
    client.app.dependency_overrides[get_chat_model] = lambda: FakeListChatModel(
        responses=["LangChain helps build LLM apps."]
    )

    response = client.post(
        "/chat",
        json={"question": "What is LangChain?", "document_id": document_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "LangChain helps build LLM apps."
    assert len(body["sources"]) >= 1
