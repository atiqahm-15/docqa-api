from app import db


def test_insert_and_list_documents(tmp_path):
    with db.get_connection(tmp_path) as conn:
        db.insert_document(conn, "doc1", "a.pdf", str(tmp_path / "a.pdf"), 3)
        db.insert_document(conn, "doc2", "b.pdf", str(tmp_path / "b.pdf"), 5)

    with db.get_connection(tmp_path) as conn:
        rows = db.list_documents(conn)

    assert len(rows) == 2
    assert {row["document_id"] for row in rows} == {"doc1", "doc2"}


def test_get_document_returns_none_when_missing(tmp_path):
    with db.get_connection(tmp_path) as conn:
        row = db.get_document(conn, "nonexistent")
    assert row is None


def test_get_document_returns_matching_row(tmp_path):
    with db.get_connection(tmp_path) as conn:
        db.insert_document(conn, "doc1", "a.pdf", str(tmp_path / "a.pdf"), 3)

    with db.get_connection(tmp_path) as conn:
        row = db.get_document(conn, "doc1")

    assert row["filename"] == "a.pdf"
    assert row["chunk_count"] == 3


def test_delete_document_removes_row(tmp_path):
    with db.get_connection(tmp_path) as conn:
        db.insert_document(conn, "doc1", "a.pdf", str(tmp_path / "a.pdf"), 3)

    with db.get_connection(tmp_path) as conn:
        db.delete_document(conn, "doc1")

    with db.get_connection(tmp_path) as conn:
        assert db.get_document(conn, "doc1") is None
