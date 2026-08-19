import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { askQuestion, getChatHistory } from "../api";
import { IconClose, IconFile, IconRefresh, IconSend, IconSpark } from "../icons";

function sessionStorageKey(documentId) {
  return documentId ? `docqa-session-id:doc:${documentId}` : "docqa-session-id:all";
}

export default function ChatWindow({ documentCount, documentId = null, documentName = null }) {
  const hasDocuments = documentCount > 0;
  const storageKey = sessionStorageKey(documentId);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(storageKey));
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [activeSource, setActiveSource] = useState(null);

  useEffect(() => {
    // Restore history once on mount if a session survived a page reload
    // (or a switch back to this tab — each tab is a fresh ChatWindow
    // instance, keyed by documentId in the parent).
    // Deliberately NOT keyed on `sessionId` — handleSend also sets that
    // state after a successful reply, and refetching then would overwrite
    // the just-received message with history rows that lack `sources`
    // (the backend's history endpoint only returns role/content).
    const storedSessionId = localStorage.getItem(storageKey);
    if (!storedSessionId) {
      return;
    }
    getChatHistory(storedSessionId)
      .then((history) => {
        setMessages(history.messages.map((m) => ({ role: m.role, content: m.content })));
      })
      .catch(() => {
        localStorage.removeItem(storageKey);
        setSessionId(null);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSend() {
    const question = input.trim();
    if (!question || sending) {
      return;
    }
    setSending(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "human", content: question }]);
    setInput("");
    try {
      const result = await askQuestion(question, sessionId, documentId);
      setMessages((prev) => [...prev, { role: "ai", content: result.answer, sources: result.sources }]);
      if (result.session_id !== sessionId) {
        setSessionId(result.session_id);
        localStorage.setItem(storageKey, result.session_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    handleSend();
  }

  function handleNewSession() {
    localStorage.removeItem(storageKey);
    setSessionId(null);
    setMessages([]);
    setError(null);
  }

  return (
    <div className="chat-window">
      <div className="topbar">
        <div>
          <h2>{documentName ? `Ask about ${documentName}` : "Ask about your documents"}</h2>
          <p>
            {documentName
              ? "Answers are grounded in this document only."
              : `${documentCount} document${documentCount === 1 ? "" : "s"} indexed`}
          </p>
        </div>
        <button className="icon-btn" onClick={handleNewSession} title="Start a new session">
          <IconRefresh />
        </button>
      </div>

      <ul className="chat-window__messages">
        {messages.length === 0 && (
          <li className="chat-window__empty">
            {hasDocuments
              ? `Start the conversation — ask a question about ${documentName ?? "your documents"}.`
              : "Upload a PDF to get started."}
          </li>
        )}
        {messages.map((message, index) => (
          <li key={index} className={`chat-window__message chat-window__message--${message.role}`}>
            {message.role === "ai" && (
              <span className="chat-window__avatar">
                <IconSpark />
              </span>
            )}
            <div className="chat-window__bubble-col">
              <div className="chat-window__bubble">
                {message.role === "ai" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                ) : (
                  <p>{message.content}</p>
                )}
              </div>
              {message.sources && message.sources.length > 0 && (
                <ul className="chat-window__sources">
                  {message.sources.map((source, sourceIndex) => (
                    <li key={sourceIndex}>
                      <button type="button" onClick={() => setActiveSource(source)}>
                        <IconFile />
                        {source.filename} <span>· p.{source.page}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        ))}
      </ul>

      {error && <p role="alert">{error}</p>}

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          disabled={!hasDocuments || sending}
          placeholder="Ask a question about your documents…"
        />
        <button
          type="submit"
          className="chat-window__send"
          disabled={!hasDocuments || sending}
          aria-label={sending ? "Thinking…" : "Ask"}
        >
          <IconSend />
        </button>
      </form>

      {activeSource && (
        <div className="source-modal__backdrop" onClick={() => setActiveSource(null)}>
          <div className="source-modal" onClick={(event) => event.stopPropagation()}>
            <div className="source-modal__header">
              <span className="source-modal__title">
                <IconFile />
                {activeSource.filename} · p.{activeSource.page}
              </span>
              <button
                type="button"
                className="icon-btn"
                onClick={() => setActiveSource(null)}
                aria-label="Close"
              >
                <IconClose />
              </button>
            </div>
            <p className="source-modal__snippet">{activeSource.snippet}</p>
          </div>
        </div>
      )}
    </div>
  );
}
