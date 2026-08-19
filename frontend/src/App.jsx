import { useCallback, useEffect, useState } from "react";
import "./App.css";
import ChatWindow from "./components/ChatWindow";
import DocumentList from "./components/DocumentList";
import DocumentTabs from "./components/DocumentTabs";
import UploadPanel from "./components/UploadPanel";
import { deleteDocument, listDocuments } from "./api";
import { IconBrand, IconSpark } from "./icons";

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState(null);
  const [activeDocumentId, setActiveDocumentId] = useState(null);

  const refreshDocuments = useCallback(() => {
    setDocumentsLoading(true);
    setDocumentsError(null);
    return listDocuments()
      .then((result) => setDocuments(result.documents))
      .catch((err) => setDocumentsError(err.message))
      .finally(() => setDocumentsLoading(false));
  }, []);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  async function handleDelete(documentId) {
    await deleteDocument(documentId);
    if (documentId === activeDocumentId) {
      setActiveDocumentId(null);
    }
    refreshDocuments();
  }

  const activeDocument = documents.find((doc) => doc.document_id === activeDocumentId) ?? null;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <IconBrand />
          </div>
          <div className="brand-text">
            <h1>DocQA</h1>
            <p>Chat with your PDFs</p>
          </div>
        </div>

        <UploadPanel onUploadSuccess={refreshDocuments} />

        <div className="section-label">Documents · {documents.length}</div>
        <DocumentList
          documents={documents}
          loading={documentsLoading}
          error={documentsError}
          onDelete={handleDelete}
          onSelect={setActiveDocumentId}
          activeDocumentId={activeDocumentId}
        />

        <div className="sidebar-footer">
          <IconSpark />
          Powered by Google Gemini
        </div>
      </aside>

      <div className="chat-pane">
        <DocumentTabs
          documents={documents}
          activeDocumentId={activeDocumentId}
          onSelect={setActiveDocumentId}
        />
        <ChatWindow
          key={activeDocumentId ?? "all"}
          documentCount={documents.length}
          documentId={activeDocumentId}
          documentName={activeDocument?.filename ?? null}
        />
      </div>
    </div>
  );
}
