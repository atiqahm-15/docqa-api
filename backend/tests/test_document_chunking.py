from app.services import document_service


def test_chunk_pdf_splits_into_chunks_with_metadata(sample_pdf_path):
    chunks = document_service.chunk_pdf(
        sample_pdf_path, document_id="doc1", chunk_size=1000, chunk_overlap=150
    )

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.metadata == {
            "document_id": "doc1",
            "filename": "sample.pdf",
            "page": chunk.metadata["page"],
        }
        assert chunk.page_content.strip() != ""


def test_chunk_pdf_page_numbers_are_one_indexed(sample_pdf_path):
    chunks = document_service.chunk_pdf(sample_pdf_path, document_id="doc1")
    pages = {chunk.metadata["page"] for chunk in chunks}
    assert min(pages) == 1
    assert max(pages) == 2
