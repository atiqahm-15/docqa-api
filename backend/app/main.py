import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pypdf.errors import PdfReadError

from app import db
from app.config import Settings, get_settings
from app.dependencies import get_chat_model, get_embeddings, get_vectorstore
from app.exceptions import ProviderUnavailableError
from app.schemas import (
    ChatHistoryResponse,
    ChatMessageItem,
    ChatRequest,
    ChatResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentUploadResponse,
    SourceCitation,
)
from app.services import chat_service, document_service

settings = get_settings()

app = FastAPI(title="Document Q&A API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_handler(request: Request, exc: ProviderUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    vectorstore=Depends(get_vectorstore),
) -> DocumentUploadResponse:
    is_pdf = (file.content_type == "application/pdf") or file.filename.lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    document_id = uuid.uuid4().hex
    upload_dir = settings.data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{document_id}_{file.filename}"
    file_path.write_bytes(await file.read())

    try:
        chunks = document_service.chunk_pdf(
            file_path, document_id, settings.chunk_size, settings.chunk_overlap
        )
    except PdfReadError as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}") from exc

    try:
        chunk_count = document_service.embed_and_store(vectorstore, chunks)
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise ProviderUnavailableError("Gemini", str(exc)) from exc

    with db.get_connection(settings.data_dir) as conn:
        db.insert_document(conn, document_id, file.filename, str(file_path), chunk_count)

    return DocumentUploadResponse(document_id=document_id, filename=file.filename, chunk_count=chunk_count)


@app.get("/documents", response_model=DocumentListResponse)
def list_documents(settings: Settings = Depends(get_settings)) -> DocumentListResponse:
    with db.get_connection(settings.data_dir) as conn:
        rows = db.list_documents(conn)
    return DocumentListResponse(
        documents=[
            DocumentListItem(
                document_id=row["document_id"],
                filename=row["filename"],
                uploaded_at=row["uploaded_at"],
                chunk_count=row["chunk_count"],
            )
            for row in rows
        ]
    )


@app.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    settings: Settings = Depends(get_settings),
    vectorstore=Depends(get_vectorstore),
) -> None:
    with db.get_connection(settings.data_dir) as conn:
        row = db.get_document(conn, document_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        document_service.delete_document_vectors(vectorstore, document_id)
        Path(row["file_path"]).unlink(missing_ok=True)
        db.delete_document(conn, document_id)


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    chat_model=Depends(get_chat_model),
    vectorstore=Depends(get_vectorstore),
) -> ChatResponse:
    with db.get_connection(settings.data_dir) as conn:
        documents = db.list_documents(conn)
    if not documents:
        raise HTTPException(status_code=400, detail="No documents indexed yet. Upload a PDF first.")

    session_id = request.session_id or uuid.uuid4().hex
    history = chat_service.get_session_history(db.get_db_path(settings.data_dir), session_id)

    try:
        result = chat_service.answer_question(
            vectorstore, chat_model, history, request.question, settings.retrieval_k
        )
    except Exception as exc:
        raise ProviderUnavailableError("Gemini", str(exc)) from exc

    return ChatResponse(
        answer=result["answer"],
        sources=[SourceCitation(**source) for source in result["sources"]],
        session_id=session_id,
    )


@app.get("/chat/{session_id}/history", response_model=ChatHistoryResponse)
def get_chat_history(session_id: str, settings: Settings = Depends(get_settings)) -> ChatHistoryResponse:
    history = chat_service.get_session_history(db.get_db_path(settings.data_dir), session_id)
    if not history.messages:
        raise HTTPException(status_code=404, detail="Session not found.")
    return ChatHistoryResponse(
        session_id=session_id,
        messages=[ChatMessageItem(role=m.type, content=m.content) for m in history.messages],
    )
