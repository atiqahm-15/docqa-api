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


def test_list_documents_returns_uploaded_documents(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        client.post("/documents/upload", files={"file": ("sample.pdf", f, "application/pdf")})

    response = client.get("/documents")

    assert response.status_code == 200
    documents = response.json()["documents"]
    assert len(documents) == 1
    assert documents[0]["filename"] == "sample.pdf"


def test_list_documents_empty_when_none_uploaded(client):
    response = client.get("/documents")
    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_delete_document_removes_it_from_list(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        upload_response = client.post(
            "/documents/upload", files={"file": ("sample.pdf", f, "application/pdf")}
        )
    document_id = upload_response.json()["document_id"]

    delete_response = client.delete(f"/documents/{document_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/documents")
    assert list_response.json()["documents"] == []


def test_delete_unknown_document_returns_404(client):
    response = client.delete("/documents/does-not-exist")
    assert response.status_code == 404
