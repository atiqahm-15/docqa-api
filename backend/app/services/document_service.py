from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


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
    vectorstore.add_documents(chunks, ids=ids)
    return len(chunks)


def delete_document_vectors(vectorstore, document_id: str) -> None:
    existing = vectorstore.get(where={"document_id": document_id})
    ids = existing.get("ids", [])
    if ids:
        vectorstore.delete(ids=ids)
