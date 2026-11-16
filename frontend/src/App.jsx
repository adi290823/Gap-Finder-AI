import api from "../services/api";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  BrainCircuit,
  BookOpen,
  Target,
  ChartNoAxesCombined,
  ClipboardList,
  CalendarDays,
  Bot,
  Upload,
  FileText,
  CheckCircle2,
  LoaderCircle,
  AlertCircle
} from "lucide-react";


import "./App.css";

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");
  const [aiStatus, setAiStatus] = useState("Checking...");
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadResult, setUploadResult] = useState(null);
  const [activeView, setActiveView] = useState("Dashboard");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [chatError, setChatError] = useState("");
  const [sendingQuestion, setSendingQuestion] = useState(false);

  const fileInputRef = useRef(null);

  const loadDocuments = useCallback(
    () => api.get("/api/documents")
      .then((response) => setDocuments(response.data.documents))
      .catch((error) => console.error("Could not load documents:", error)),
    []
  );

  useEffect(() => {
    api.get("/api/health")
      .then(() => setBackendStatus("Connected"))
      .catch(() => setBackendStatus("Disconnected"));

    api.get("/api/ai/status")
      .then((response) => {
        setAiStatus(
          response.data.configured ? "Key configured" : "Not configured"
        );
      })
      .catch(() => setAiStatus("Unavailable"));

    loadDocuments();
  }, [loadDocuments]);

  const handleAsk = async (event) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || sendingQuestion) return;

    setChatError("");
    setMessages((currentMessages) => [
      ...currentMessages,
      { role: "student", text: trimmedQuestion },
    ]);
    setQuestion("");
    setSendingQuestion(true);

    try {
      const response = await api.post(
        "/api/ai/ask",
        {
          question: trimmedQuestion,
          document_id: selectedDocumentId || null,
        },
        { timeout: 120000 }
      );

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          text: response.data.answer,
          sources: response.data.sources,
        },
      ]);
    } catch (error) {
      const detail = error.response?.data?.detail;
      setChatError(
        typeof detail === "string"
          ? detail
          : error.response
            ? "The request was invalid. Please check the question and selected study material."
            : "Could not reach the backend. Check that it is running and try again."
      );
    } finally {
      setSendingQuestion(false);
    }
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    setUploadError("");
    setUploadResult(null);

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Please select a PDF file.");
      event.target.value = "";
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setUploadError("File size must be less than 10 MB.");
      event.target.value = "";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);

    try {
      const response = await api.post(
        "/api/documents/upload",
        formData
      );

      setUploadResult(response.data);
      await loadDocuments();

    } catch (error) {
      setUploadError(
        error.response?.data?.detail ||
        "Upload failed. Please check your backend."
      );
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const menuItems = [
    { name: "Dashboard", icon: ChartNoAxesCombined },
    { name: "Study Materials", icon: BookOpen },
    { name: "Topic Map", icon: BrainCircuit },
    { name: "Diagnostic Quiz", icon: ClipboardList },
    { name: "Gap Analysis", icon: Target },
    { name: "Revision Planner", icon: CalendarDays },
    { name: "AI Study Assistant", icon: Bot }
  ];

  return (
    <div className="app">

      <aside className="sidebar">

        <div className="brand">
          <BrainCircuit size={30} />
          <span>GapFinder AI</span>
        </div>

        <p className="menu-heading">LEARNING SPACE</p>

        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.name === activeView;

          return (
            <button
              className={`menu-item ${isActive ? "active" : ""}`}
              key={item.name}
              onClick={() => {
                if (item.name === "Dashboard" || item.name === "AI Study Assistant") {
                  setActiveView(item.name);
                }
              }}
            >
              <Icon size={19} />
              {item.name}
            </button>
          );
        })}

        <div className="sidebar-footer">
          Find what you don't know.
        </div>

      </aside>

      <main className="main-content">

        <header className="topbar">
          <div>
            <h2>{activeView}</h2>
            <p>
              {activeView === "Dashboard"
                ? "Welcome to your personalised learning space."
                : "Ask questions about your uploaded study materials."}
            </p>
          </div>

          <div className="avatar">S</div>
        </header>

        <section className="welcome">

          <div>
            <span className="eyebrow">AI-POWERED LEARNING</span>

            <h1>Discover your knowledge gaps.</h1>

            <p>
              Understand what you know, identify what you don't,
              and improve with a personalised learning plan.
            </p>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              hidden
              onChange={handleUpload}
            />

            <button
              className="primary-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? (
                <LoaderCircle size={18} className="spin" />
              ) : (
                <Upload size={18} />
              )}

              {uploading ? "Uploading..." : "Upload Study Materials"}
            </button>
          </div>

          <BrainCircuit size={100} className="welcome-icon" />

        </section>

        {uploadError && (
          <div className="upload-feedback upload-error">
            <AlertCircle size={20} />
            <span>{uploadError}</span>
          </div>
        )}

        {uploadResult && (
          <section className="upload-feedback upload-success">
            <CheckCircle2 size={22} />

            <div>
              <strong>PDF uploaded successfully!</strong>

              <p>{uploadResult.filename}</p>

              <p>
                Pages: {uploadResult.page_count} |
                Characters extracted: {uploadResult.character_count}
              </p>
            </div>
          </section>
        )}

        {activeView === "AI Study Assistant" && (
          <section className="panel chat-panel">
            <div className="chat-heading">
              <div>
                <h3>Ask your study materials</h3>
                <p>Answers are grounded in the selected uploaded PDF.</p>
              </div>
              <label className="document-select">
                <span>Study material</span>
                <select
                  value={selectedDocumentId}
                  onChange={(event) => setSelectedDocumentId(event.target.value)}
                >
                  <option value="">All documents</option>
                  {documents.map((document) => (
                    <option key={document.document_id} value={document.document_id}>
                      {document.filename}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="chat-messages" aria-live="polite">
              {messages.length === 0 ? (
                <p className="chat-empty">
                  Ask a question to get started. For example: “Summarise the key ideas.”
                </p>
              ) : (
                messages.map((message, index) => (
                  <article className={`chat-message ${message.role}`} key={`${index}-${message.role}`}>
                    <strong>{message.role === "student" ? "You" : "GapFinder AI"}</strong>
                    <p>{message.text}</p>
                    {message.sources?.length > 0 && (
                      <small>
                        Sources: {message.sources.map((source) =>
                          `${source.filename}, page ${source.page}`
                        ).join("; ")}
                      </small>
                    )}
                  </article>
                ))
              )}
              {sendingQuestion && (
                <p className="chat-loading">
                  <LoaderCircle size={16} className="spin" /> Searching your materials...
                </p>
              )}
            </div>

            {chatError && (
              <div className="upload-feedback upload-error" role="alert">
                <AlertCircle size={20} />
                <span>{chatError}</span>
              </div>
            )}

            <form className="chat-form" onSubmit={handleAsk}>
              <input
                aria-label="Ask a question about your study material"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a question about your study material..."
                disabled={sendingQuestion || documents.length === 0}
              />
              <button
                className="primary-button"
                type="submit"
                disabled={sendingQuestion || !question.trim() || documents.length === 0}
              >
                {sendingQuestion ? "Thinking..." : "Ask"}
              </button>
            </form>
            {documents.length === 0 && (
              <p className="chat-empty">Upload a PDF before asking a question.</p>
            )}
          </section>
        )}

        {activeView === "Dashboard" && <>
        <section className="stats">

          <div className="stat-card">
            <BookOpen />
            <p>Study Materials</p>
            <h2>{documents.length}</h2>
            <span>Documents uploaded</span>
          </div>

          <div className="stat-card">
            <Target />
            <p>Topics Analysed</p>
            <h2>0</h2>
            <span>Topics assessed</span>
          </div>

          <div className="stat-card">
            <ClipboardList />
            <p>Quizzes Completed</p>
            <h2>0</h2>
            <span>Diagnostic assessments</span>
          </div>

          <div className="stat-card">
            <ChartNoAxesCombined />
            <p>Learning Progress</p>
            <h2>0%</h2>
            <span>Mastery score</span>
          </div>

        </section>

        <section className="bottom-grid">

          <div className="panel">

            <h3>Uploaded Study Materials</h3>

            <p>Your uploaded textbooks and notes.</p>

            {documents.length === 0 ? (
              <div className="empty-state">
                <FileText size={45} />
                <p>No documents uploaded yet.</p>
              </div>
            ) : (
              documents.map((document) => (
                <div className="document-row" key={document.document_id}>
                  <FileText size={22} />

                  <div>
                    <strong>{document.filename}</strong>
                    <p>
                      {document.character_count.toLocaleString()} characters extracted
                    </p>
                  </div>
                </div>
              ))
            )}

          </div>

          <div className="panel">

            <h3>System Status</h3>

            <div className="status-row">
              <span>Python Backend</span>
              <strong>{backendStatus}</strong>
            </div>

            <div className="status-row">
              <span>Gemini AI</span>
              <strong>{aiStatus}</strong>
            </div>

          </div>

        </section>

        {uploadResult && (
          <section className="panel preview-panel">
            <h3>Extracted Text Preview</h3>

            <p>
              Showing the first 3,000 characters extracted from your PDF.
            </p>

            <pre>{uploadResult.preview}</pre>
          </section>
        )}
        </>}

      </main>
    </div>
  );
}

export default App;
