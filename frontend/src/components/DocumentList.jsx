export default function DocumentList({ documents, loading, error, onDelete }) {
  if (loading) {
    return <p>Loading documents…</p>;
  }

  if (error) {
    return <p role="alert">Could not load documents: {error}</p>;
  }

  if (documents.length === 0) {
    return <p>No documents uploaded yet. Upload a PDF to get started.</p>;
  }

  return (
    <ul className="document-list">
      {documents.map((doc) => (
        <li key={doc.document_id} className="document-list__item">
          <span>{doc.filename}</span>
          <span className="document-list__meta">{doc.chunk_count} chunks</span>
          <button onClick={() => onDelete(doc.document_id)}>Delete</button>
        </li>
      ))}
    </ul>
  );
}
