import { useEffect, useState } from "react";
import { askQuestion, getChatHistory } from "../api";

const SESSION_STORAGE_KEY = "docqa-session-id";

export default function ChatWindow({ hasDocuments }) {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_STORAGE_KEY));
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    getChatHistory(sessionId)
      .then((history) => {
        setMessages(history.messages.map((m) => ({ role: m.role, content: m.content })));
      })
      .catch(() => {
        localStorage.removeItem(SESSION_STORAGE_KEY);
        setSessionId(null);
      });
  }, [sessionId]);

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
      const result = await askQuestion(question, sessionId);
      setMessages((prev) => [...prev, { role: "ai", content: result.answer, sources: result.sources }]);
      if (result.session_id !== sessionId) {
        setSessionId(result.session_id);
        localStorage.setItem(SESSION_STORAGE_KEY, result.session_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter") {
      handleSend();
    }
  }

  return (
    <div className="chat-window">
      {!hasDocuments && <p>Upload a PDF above before asking questions.</p>}
      <ul className="chat-window__messages">
        {messages.map((message, index) => (
          <li key={index} className={`chat-window__message chat-window__message--${message.role}`}>
            <p>{message.content}</p>
            {message.sources && message.sources.length > 0 && (
              <ul className="chat-window__sources">
                {message.sources.map((source, sourceIndex) => (
                  <li key={sourceIndex}>
                    {source.filename}, p.{source.page}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
      {error && <p role="alert">{error}</p>}
      <input
        type="text"
        value={input}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={!hasDocuments || sending}
        placeholder="Ask a question about your documents…"
      />
      <button onClick={handleSend} disabled={!hasDocuments || sending}>
        {sending ? "Thinking…" : "Ask"}
      </button>
    </div>
  );
}
