import { useRef, useState } from "react";
import { uploadDocument } from "../api";
import { IconUpload } from "../icons";

export default function UploadPanel({ onUploadSuccess }) {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  async function handleFileChange(event) {
    const file = event.target.files[0] ?? null;
    if (!file) {
      return;
    }
    setUploading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await uploadDocument(file);
      setSuccessMessage(`Uploaded "${result.filename}" (${result.chunk_count} chunks indexed).`);
      onUploadSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  return (
    <div className="upload-panel">
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        disabled={uploading}
        style={{ display: "none" }}
      />
      <button
        className="upload-btn"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
      >
        <IconUpload />
        {uploading ? "Uploading…" : "Upload PDF"}
      </button>
      {error && <p role="alert">{error}</p>}
      {successMessage && <p className="empty-state">{successMessage}</p>}
    </div>
  );
}
