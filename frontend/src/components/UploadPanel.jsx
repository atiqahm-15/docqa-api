import { useState } from "react";
import { uploadDocument } from "../api";

export default function UploadPanel({ onUploadSuccess }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  function handleFileChange(event) {
    setSelectedFile(event.target.files[0] ?? null);
    setError(null);
    setSuccessMessage(null);
  }

  async function handleUpload() {
    if (!selectedFile) {
      return;
    }
    setUploading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await uploadDocument(selectedFile);
      setSuccessMessage(`Uploaded "${result.filename}" (${result.chunk_count} chunks indexed).`);
      setSelectedFile(null);
      onUploadSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="upload-panel">
      <input
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        disabled={uploading}
      />
      <button onClick={handleUpload} disabled={!selectedFile || uploading}>
        {uploading ? "Uploading…" : "Upload PDF"}
      </button>
      {error && <p role="alert">{error}</p>}
      {successMessage && <p>{successMessage}</p>}
    </div>
  );
}
