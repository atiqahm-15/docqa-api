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
