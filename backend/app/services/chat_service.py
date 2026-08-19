from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

CONTEXTUALIZE_SYSTEM_PROMPT = (
    "Given a chat history and the latest user question, rephrase the "
    "question into a standalone question that can be understood without "
    "the chat history. Do not answer the question, just reformulate it "
    "if needed, and otherwise return it as-is."
)

QA_SYSTEM_PROMPT = (
    "You are an assistant that answers questions using only the provided "
    "context. If the context does not contain the answer, say you don't "
    "know. Keep answers concise.\n\nContext:\n{context}"
)


def get_session_history(db_path: Path, session_id: str) -> SQLChatMessageHistory:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return SQLChatMessageHistory(session_id=session_id, connection=f"sqlite:///{db_path}")


def _contextualize_question(chat_model: BaseChatModel, question: str, chat_history: list) -> str:
    if not chat_history:
        return question
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CONTEXTUALIZE_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )
    chain = prompt | chat_model | StrOutputParser()
    return chain.invoke({"chat_history": chat_history, "question": question})


def _format_docs(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def answer_question(
    vectorstore: Chroma,
    chat_model: BaseChatModel,
    history: SQLChatMessageHistory,
    question: str,
    k: int = 4,
) -> dict:
    standalone_question = _contextualize_question(chat_model, question, history.messages)

    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    retrieved_docs = retriever.invoke(standalone_question)
    context = _format_docs(retrieved_docs)

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", QA_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )
    qa_chain = qa_prompt | chat_model | StrOutputParser()
    answer = qa_chain.invoke(
        {"context": context, "chat_history": history.messages, "question": question}
    )

    history.add_user_message(question)
    history.add_ai_message(answer)

    sources = []
    seen = set()
    for doc in retrieved_docs:
        key = (doc.metadata.get("filename", "unknown"), doc.metadata.get("page", 0))
        if key not in seen:
            seen.add(key)
            sources.append(
                {"filename": key[0], "page": key[1], "snippet": _truncate(doc.page_content)}
            )

    return {"answer": answer, "sources": sources}


def _truncate(text: str, max_chars: int = 400) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"
