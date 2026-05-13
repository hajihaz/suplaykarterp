import Link from "next/link";

const PROMPTS = [
  "Who is Haji and what does HajiHaz AI help with?",
  "Give me a concise business strategy checklist for Suplaykart.",
  "Summarize my current knowledge base in plain language.",
  "What should I upload next to improve the RAG answers?"
];

export function ChatShell() {
  return (
    <main className="page-shell" data-chat-page="true">
      <section className="hero-card">
        <div className="hero-copy">
          <span className="eyebrow">Personal RAG assistant</span>
          <h1>HajiHaz AI</h1>
          <p>
            A minimal, premium workspace for live chat, knowledge retrieval, and business support. The UI stays fast,
            the backend stays modular, and the assistant stays grounded in your own knowledge base.
          </p>
        </div>
        <div className="hero-meta">
          <div className="meta-tile">
            <span>Status</span>
            <strong id="chatRuntimeStatus">Browser ready</strong>
          </div>
          <div className="meta-tile">
            <span>Admin</span>
            <strong>
              <Link href="/admin">Open workspace</Link>
            </strong>
          </div>
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="sidebar-card">
          <div>
            <span className="eyebrow">Prompt deck</span>
            <h2>Start faster</h2>
          </div>
          <div className="prompt-grid">
            {PROMPTS.map((prompt) => (
              <button className="prompt-card" data-prompt={prompt} key={prompt} type="button">
                {prompt}
              </button>
            ))}
          </div>
          <p className="sidebar-note">
            Add knowledge from the admin page, then return here to verify that new retrievals appear in citations.
          </p>
        </aside>

        <section className="chat-card">
          <div className="chat-scroll" id="chatMessages">
            <article className="message-bubble assistant">
              <div className="message-head">
                <span>HajiHaz AI</span>
              </div>
              <p>
                HajiHaz AI is ready. Ask a question about your business, plans, or knowledge base, and I will use the
                local RAG store first before falling back to general guidance.
              </p>
              <button className="ghost-button" data-copy-message type="button">
                Copy response
              </button>
            </article>
          </div>

          <div className="composer">
            <textarea
              className="composer-input"
              id="chatInput"
              placeholder="Ask about strategy, documents, operations, or anything stored in your knowledge base..."
              rows={4}
            />
            <div className="composer-row">
              <span className="helper-text" id="chatStatusText">
                Browser ready. App API route: POST /api/chat
              </span>
              <button className="primary-button" id="chatSendButton" type="button">
                Send
              </button>
            </div>
            <p className="error-text" hidden id="chatErrorText" />
          </div>
        </section>
      </section>
    </main>
  );
}
