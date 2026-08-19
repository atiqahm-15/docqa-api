import re
import time
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

_RATE_LIMIT_MARKERS = ("RESOURCE_EXHAUSTED", "429")
_MAX_EMBED_ATTEMPTS = 3
_DEFAULT_RETRY_DELAY_SECONDS = 10.0
_RETRY_DELAY_PATTERN = re.compile(r"retry in (\d+(?:\.\d+)?)s", re.IGNORECASE)


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _RATE_LIMIT_MARKERS)


def _rate_limit_retry_delay(exc: Exception, attempt: int) -> float:
    match = _RETRY_DELAY_PATTERN.search(str(exc))
    if match:
        return float(match.group(1)) + 1  # small buffer past Google's suggested wait
    return _DEFAULT_RETRY_DELAY_SECONDS * attempt


def chunk_pdf(
    file_path: Path,
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    filename: str | None = None,
) -> list[Document]:
    loader = PyPDFLoader(str(file_path))
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = splitter.split_documents(pages)

    filename = filename or Path(file_path).name
    for chunk in chunks:
        page_number = chunk.metadata.get("page", 0) + 1
        chunk.metadata = {
            "document_id": document_id,
            "filename": filename,
            "page": page_number,
        }
    return chunks


def embed_and_store(vectorstore, chunks: list[Document]) -> int:
    if not chunks:
        return 0
    document_id = chunks[0].metadata["document_id"]
    ids = [f"{document_id}-{i}" for i in range(len(chunks))]

    for attempt in range(1, _MAX_EMBED_ATTEMPTS + 1):
        try:
            vectorstore.add_documents(chunks, ids=ids)
            return len(chunks)
        except Exception as exc:
            if attempt == _MAX_EMBED_ATTEMPTS or not _is_rate_limit_error(exc):
                raise
            time.sleep(_rate_limit_retry_delay(exc, attempt))


def delete_document_vectors(vectorstore, document_id: str) -> None:
    existing = vectorstore.get(where={"document_id": document_id})
    ids = existing.get("ids", [])
    if ids:
        vectorstore.delete(ids=ids)
