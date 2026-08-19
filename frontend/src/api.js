function getApiUrl() {
  return import.meta.env.VITE_API_URL || "http://localhost:8000";
}

export async function parseResponse(response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

async function request(path, options = {}) {
  const response = await fetch(`${getApiUrl()}${path}`, options);
  return parseResponse(response);
}

export function listDocuments() {
  return request("/documents");
}

export function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/documents/upload", { method: "POST", body: formData });
}

export function deleteDocument(documentId) {
  return request(`/documents/${documentId}`, { method: "DELETE" });
}

export function askQuestion(question, sessionId, documentId) {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId, document_id: documentId ?? null }),
  });
}

export function getChatHistory(sessionId) {
  return request(`/chat/${sessionId}/history`);
}
