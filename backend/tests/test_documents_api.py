def test_upload_pdf_returns_document_id_and_chunk_count(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        response = client.post(
            "/documents/upload",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "sample.pdf"
    assert body["chunk_count"] >= 1
    assert body["document_id"]


def test_upload_rejects_non_pdf_file(client):
    response = client.post(
        "/documents/upload",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_corrupt_pdf(client):
    response = client.post(
        "/documents/upload",
        files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
    )
    assert response.status_code == 422
