from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.services import document_service


def _make_vectorstore(tmp_path, embeddings):
    return Chroma(
        collection_name="test-documents",
        embedding_function=embeddings,
        persist_directory=str(tmp_path / "chroma"),
    )


def test_embed_and_store_adds_chunks_and_returns_count(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore(tmp_path, fake_embeddings)
    chunks = [
        Document(page_content="chunk one", metadata={"document_id": "doc1", "filename": "a.pdf", "page": 1}),
        Document(page_content="chunk two", metadata={"document_id": "doc1", "filename": "a.pdf", "page": 2}),
    ]

    count = document_service.embed_and_store(vectorstore, chunks)

    assert count == 2
    stored = vectorstore.get(where={"document_id": "doc1"})
    assert len(stored["ids"]) == 2


def test_embed_and_store_returns_zero_for_empty_chunks(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore(tmp_path, fake_embeddings)
    assert document_service.embed_and_store(vectorstore, []) == 0


def test_delete_document_vectors_removes_only_matching_document(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore(tmp_path, fake_embeddings)
    document_service.embed_and_store(
        vectorstore,
        [Document(page_content="doc1 chunk", metadata={"document_id": "doc1", "filename": "a.pdf", "page": 1})],
    )
    document_service.embed_and_store(
        vectorstore,
        [Document(page_content="doc2 chunk", metadata={"document_id": "doc2", "filename": "b.pdf", "page": 1})],
    )

    document_service.delete_document_vectors(vectorstore, "doc1")

    remaining = vectorstore.get()
    remaining_doc_ids = {meta["document_id"] for meta in remaining["metadatas"]}
    assert remaining_doc_ids == {"doc2"}
