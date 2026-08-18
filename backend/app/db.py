import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def get_db_path(data_dir: Path) -> Path:
    return Path(data_dir) / "app.db"


def init_documents_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            chunk_count INTEGER NOT NULL
        )
        """
    )


@contextmanager
def get_connection(data_dir: Path):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path(data_dir))
    conn.row_factory = sqlite3.Row
    try:
        init_documents_table(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_document(
    conn: sqlite3.Connection,
    document_id: str,
    filename: str,
    file_path: str,
    chunk_count: int,
) -> None:
    conn.execute(
        "INSERT INTO documents (document_id, filename, file_path, uploaded_at, chunk_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (document_id, filename, file_path, datetime.now(timezone.utc).isoformat(), chunk_count),
    )


def list_documents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()


def get_document(conn: sqlite3.Connection, document_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM documents WHERE document_id = ?", (document_id,)
    ).fetchone()


def delete_document(conn: sqlite3.Connection, document_id: str) -> None:
    conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
