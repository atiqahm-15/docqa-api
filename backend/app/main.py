import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pypdf.errors import PdfReadError

from app import db
from app.config import Settings, get_settings
from app.dependencies import get_embeddings, get_vectorstore
from app.exceptions import ProviderUnavailableError
from app.schemas import DocumentUploadResponse
from app.services import document_service

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
