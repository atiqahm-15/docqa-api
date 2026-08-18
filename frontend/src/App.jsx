import { useCallback, useEffect, useState } from "react";
import "./App.css";
import ChatWindow from "./components/ChatWindow";
import DocumentList from "./components/DocumentList";
import UploadPanel from "./components/UploadPanel";
import { deleteDocument, listDocuments } from "./api";

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState(null);

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
    refreshDocuments();
  }

  return (
    <div className="app">
      <h1>Document Q&amp;A</h1>
      <section>
        <h2>Documents</h2>
        <UploadPanel onUploadSuccess={refreshDocuments} />
        <DocumentList
          documents={documents}
          loading={documentsLoading}
          error={documentsError}
          onDelete={handleDelete}
        />
      </section>
      <section>
        <h2>Chat</h2>
        <ChatWindow hasDocuments={documents.length > 0} />
      </section>
    </div>
  );
}
