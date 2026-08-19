import { IconFile, IconTrash } from "../icons";

export default function DocumentList({ documents, loading, error, onDelete, onSelect, activeDocumentId }) {
  if (loading) {
    return <p className="empty-state">Loading documents…</p>;
  }

  if (error) {
    return <p role="alert">Could not load documents: {error}</p>;
  }

  if (documents.length === 0) {
    return <p className="empty-state">No documents uploaded yet. Upload a PDF to get started.</p>;
  }

  return (
    <ul className="document-list">
      {documents.map((doc) => (
        <li
          key={doc.document_id}
          className={`document-list__item${
            doc.document_id === activeDocumentId ? " document-list__item--active" : ""
          }`}
        >
          <button
            type="button"
            className="document-list__select"
            onClick={() => onSelect(doc.document_id)}
            aria-pressed={doc.document_id === activeDocumentId}
          >
            <span className="doc-icon">
              <IconFile />
            </span>
            <span className="document-list__info">
              <span className="document-list__name">{doc.filename}</span>
              <span className="document-list__meta">{doc.chunk_count} chunks</span>
            </span>
          </button>
          <button
            className="document-list__delete"
            onClick={() => onDelete(doc.document_id)}
            aria-label={`Delete ${doc.filename}`}
          >
            <IconTrash />
          </button>
        </li>
      ))}
    </ul>
  );
}
