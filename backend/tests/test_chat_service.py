from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.services import chat_service


def _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings):
    vectorstore = Chroma(
        collection_name="test-chat-documents",
        embedding_function=fake_embeddings,
        persist_directory=str(tmp_path / "chroma"),
    )
    vectorstore.add_documents(
        [Document(page_content="LangChain builds LLM apps.", metadata={"document_id": "d1", "filename": "a.pdf", "page": 1})],
        ids=["d1-0"],
    )
    return vectorstore


def test_answer_question_returns_answer_and_sources(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings)
    chat_model = FakeListChatModel(responses=["LangChain helps build LLM apps."])
    history = chat_service.get_session_history(tmp_path / "chat.db", "session-1")

    result = chat_service.answer_question(vectorstore, chat_model, history, "What is LangChain?")

    assert result["answer"] == "LangChain helps build LLM apps."
    assert result["sources"] == [{"filename": "a.pdf", "page": 1}]


def test_answer_question_persists_turn_to_history(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings)
    chat_model = FakeListChatModel(responses=["LangChain helps build LLM apps."])
    db_path = tmp_path / "chat.db"
    history = chat_service.get_session_history(db_path, "session-1")

    chat_service.answer_question(vectorstore, chat_model, history, "What is LangChain?")

    reloaded_history = chat_service.get_session_history(db_path, "session-1")
    assert len(reloaded_history.messages) == 2
    assert reloaded_history.messages[0].content == "What is LangChain?"
    assert reloaded_history.messages[1].content == "LangChain helps build LLM apps."


def test_answer_question_uses_history_on_second_turn(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings)
    chat_model = FakeListChatModel(
        responses=["First answer.", "standalone follow-up question", "Second answer."]
    )
    history = chat_service.get_session_history(tmp_path / "chat.db", "session-1")

    chat_service.answer_question(vectorstore, chat_model, history, "What is LangChain?")
    result = chat_service.answer_question(vectorstore, chat_model, history, "What about agents?")

    assert result["answer"] == "Second answer."
    assert len(history.messages) == 4


def test_get_session_history_creates_data_dir_if_missing(tmp_path):
    db_path = tmp_path / "nested" / "chat.db"
    history = chat_service.get_session_history(db_path, "session-1")
    assert history.messages == []
    assert db_path.parent.exists()
