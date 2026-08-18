from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_pdf(
    file_path: Path,
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[Document]:
    loader = PyPDFLoader(str(file_path))
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = splitter.split_documents(pages)

    filename = Path(file_path).name
    for chunk in chunks:
        page_number = chunk.metadata.get("page", 0) + 1
        chunk.metadata = {
            "document_id": document_id,
            "filename": filename,
            "page": page_number,
        }
    return chunks
