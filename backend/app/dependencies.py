from fastapi import Depends
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config import Settings, get_settings


def get_embeddings(settings: Settings = Depends(get_settings)) -> Embeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=settings.google_api_key,
    )


def get_chat_model(settings: Settings = Depends(get_settings)) -> BaseChatModel:
    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=settings.google_api_key,
    )


def get_vectorstore(
    embeddings: Embeddings = Depends(get_embeddings),
    settings: Settings = Depends(get_settings),
) -> Chroma:
    persist_dir = settings.data_dir / "chroma"
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name="documents",
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
