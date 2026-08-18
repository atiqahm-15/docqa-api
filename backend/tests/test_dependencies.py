from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config import Settings
from app.dependencies import get_chat_model, get_embeddings, get_vectorstore


def test_get_embeddings_uses_configured_model():
    settings = Settings(_env_file=None, google_api_key="test-key", gemini_embedding_model="my-embed-model")
    embeddings = get_embeddings(settings)
    assert isinstance(embeddings, GoogleGenerativeAIEmbeddings)
    assert embeddings.model == "my-embed-model"


def test_get_chat_model_uses_configured_model():
    settings = Settings(_env_file=None, google_api_key="test-key", gemini_chat_model="my-chat-model")
    chat_model = get_chat_model(settings)
    assert isinstance(chat_model, ChatGoogleGenerativeAI)
    assert chat_model.model == "models/my-chat-model" or chat_model.model == "my-chat-model"


def test_get_vectorstore_persists_under_data_dir(tmp_path, fake_embeddings):
    settings = Settings(_env_file=None, google_api_key="test-key", data_dir=tmp_path)
    vectorstore = get_vectorstore(fake_embeddings, settings)
    assert isinstance(vectorstore, Chroma)
    assert (tmp_path / "chroma").exists()
