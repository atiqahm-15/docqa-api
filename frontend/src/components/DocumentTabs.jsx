export default function DocumentTabs({ documents, activeDocumentId, onSelect }) {
  return (
    <div className="document-tabs" role="tablist" aria-label="Document scope">
      <button
        type="button"
        role="tab"
        aria-selected={activeDocumentId === null}
        className={`document-tabs__tab${activeDocumentId === null ? " document-tabs__tab--active" : ""}`}
        onClick={() => onSelect(null)}
      >
        All Documents
      </button>
      {documents.map((doc) => (
        <button
          key={doc.document_id}
          type="button"
          role="tab"
          aria-selected={activeDocumentId === doc.document_id}
          className={`document-tabs__tab${
            activeDocumentId === doc.document_id ? " document-tabs__tab--active" : ""
          }`}
          onClick={() => onSelect(doc.document_id)}
          title={doc.filename}
        >
          {doc.filename}
        </button>
      ))}
    </div>
  );
}
