const TOKEN_KEY = "hajihaz-admin-token";
const ANSWER_MODE_KEY = "hajihaz-answer-mode";
const CHAT_SESSION_KEY = "hajihaz-chat-session";
const CHAT_SESSION_LIST_KEY = "hajihaz-chat-summaries";
const CHAT_ENTRY_MODE_KEY = "hajihaz-entry-mode";
const CHAT_USER_TOKEN_KEY = "hajihaz-user-token";
const CHAT_USER_PROFILE_KEY = "hajihaz-user-profile";
const ADMIN_THEME_KEY = "hajihaz-admin-theme";
const DEFAULT_REQUEST_TIMEOUT_MS = 45000;
const LONG_REQUEST_TIMEOUT_MS = 120000;
const ADMIN_THEME_CHOICES = new Set(["system", "dark", "light"]);

async function fetchWithTimeout(path, options = {}, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(path, {
      credentials: "same-origin",
      ...options,
      signal: controller.signal
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function api(path, options = {}) {
  const headers = {
    ...(options.token ? { Authorization: `Bearer ${options.token}` } : {})
  };
  if (!options.formData) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetchWithTimeout(
    path,
    {
      method: options.method || "GET",
      headers,
      body: options.formData || (options.body ? JSON.stringify(options.body) : undefined)
    },
    options.timeoutMs || DEFAULT_REQUEST_TIMEOUT_MS
  );

  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(data.detail || response.statusText || "Request failed");
  }

  return data;
}

async function downloadFile(path, token, filenameHint) {
  const response = await fetchWithTimeout(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!response.ok) {
    let detail = response.statusText || "Download failed";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = response.statusText || "Download failed";
    }
    throw new Error(detail);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filenameHint;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value;
  }
}

function setHidden(id, hidden) {
  const element = document.getElementById(id);
  if (element) {
    element.hidden = hidden;
  }
}

function setStatusPill(id, label, tone = "idle") {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }

  element.textContent = label;
  element.className = `status-pill ${tone}`;
}

function setMeter(id, value) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  const percentage = Math.max(0, Math.min(100, Number(value || 0)));
  element.style.setProperty("--meter", `${percentage}%`);
}

function systemAdminTheme() {
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    return "light";
  }
  return "dark";
}

function normalizedAdminTheme(choice) {
  return ADMIN_THEME_CHOICES.has(choice) ? choice : "system";
}

function adminThemeLabel(choice, resolved) {
  if (choice === "system") {
    return `System (${resolved})`;
  }
  return choice.charAt(0).toUpperCase() + choice.slice(1);
}

function applyAdminTheme(choice) {
  const selected = normalizedAdminTheme(choice);
  const resolved = selected === "system" ? systemAdminTheme() : selected;
  document.documentElement.dataset.adminTheme = resolved;
  document.documentElement.dataset.adminThemeChoice = selected;
  document.documentElement.style.colorScheme = resolved;
  if (document.body) {
    document.body.dataset.adminTheme = resolved;
    document.body.dataset.adminThemeChoice = selected;
  }
  setText("adminThemeStatus", adminThemeLabel(selected, resolved));
  document.querySelectorAll("[data-admin-theme-option]").forEach((button) => {
    if (button instanceof HTMLButtonElement) {
      const active = button.dataset.adminThemeOption === selected;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    }
  });
}

function initAdminThemeControls() {
  const stored = normalizedAdminTheme(window.localStorage.getItem(ADMIN_THEME_KEY) || "system");
  applyAdminTheme(stored);
  document.querySelectorAll("[data-admin-theme-option]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", () => {
      const nextTheme = normalizedAdminTheme(button.dataset.adminThemeOption || "system");
      window.localStorage.setItem(ADMIN_THEME_KEY, nextTheme);
      applyAdminTheme(nextTheme);
    });
  });
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
      const current = normalizedAdminTheme(window.localStorage.getItem(ADMIN_THEME_KEY) || "system");
      if (current === "system") {
        applyAdminTheme(current);
      }
    });
  }
}

function showError(id, message) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }

  element.hidden = !message;
  element.textContent = message;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatMessageHtml(content) {
  return escapeHtml(content)
    .replaceAll("\n\n", "<br><br>")
    .replaceAll("\n", "<br>");
}

function readStoredConversationSummaries() {
  try {
    const raw = window.localStorage.getItem(CHAT_SESSION_LIST_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item) => item && typeof item.id === "string" && typeof item.title === "string");
  } catch {
    return [];
  }
}

function writeStoredConversationSummaries(items) {
  window.localStorage.setItem(CHAT_SESSION_LIST_KEY, JSON.stringify(items.slice(0, 8)));
}

function readStoredUserProfile() {
  try {
    const raw = window.localStorage.getItem(CHAT_USER_PROFILE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    if (typeof parsed.email !== "string" || typeof parsed.name !== "string") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function writeStoredUserProfile(profile) {
  if (!profile) {
    window.localStorage.removeItem(CHAT_USER_PROFILE_KEY);
    return;
  }
  window.localStorage.setItem(CHAT_USER_PROFILE_KEY, JSON.stringify(profile));
}

function formatTimestamp(value) {
  if (!value) {
    return "Updated just now";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }

  return timestamp.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 60) {
    return `${Math.max(0, Math.round(seconds || 0))}s`;
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m`;
  }
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  const precision = size >= 100 || unitIndex === 0 ? 0 : 1;
  return `${size.toFixed(precision)} ${units[unitIndex]}`;
}

function humanizeMode(mode) {
  const modeLabels = {
    conversation: "conversational",
    knowledge: "knowledge-first",
    knowledge_web: "knowledge + web",
    web: "web-backed",
    anthropic: "live ai",
    ollama: "local ai"
  };
  return modeLabels[mode] || String(mode || "assistant").replaceAll("_", " ");
}

const CHAT_LOADING_STAGES = [
  {
    delay: 0,
    runtimeStatus: "Thinking",
    runtimeHint: "Grounding the reply in your knowledge and broader context.",
    knowledgeStatus: "Checking knowledge",
    modeStatus: "Thinking",
    panelNote: "Grounding the reply in your knowledge and broader context.",
    statusText: "Thinking through your question...",
    helperText: "Grounding the reply in your knowledge and broader context."
  },
  {
    delay: 2200,
    runtimeStatus: "Thinking",
    runtimeHint: "Checking your saved context before filling any gaps.",
    knowledgeStatus: "Checking sources",
    modeStatus: "Grounding",
    panelNote: "Checking your saved context before filling any gaps.",
    statusText: "Checking your knowledge base...",
    helperText: "Checking your saved context before filling any gaps."
  },
  {
    delay: 6200,
    runtimeStatus: "Thinking",
    runtimeHint: "Taking a little longer to shape the best answer.",
    knowledgeStatus: "Shaping answer",
    modeStatus: "Refining",
    panelNote: "Taking a little longer to shape the best answer.",
    statusText: "Taking a little longer to shape the best answer.",
    helperText: "Taking a little longer to shape the best answer."
  }
];

function buildThinkingWordMarkup() {
  return "Thinking"
    .split("")
    .map(
      (character, index) =>
        `<span class="loading-letter" style="--letter-index:${index}">${escapeHtml(character)}</span>`
    )
    .join("");
}

function appendMessage(role, content, citations, mode, notice) {
  const messages = document.getElementById("chatMessages");
  if (!messages) {
    return null;
  }

  const article = document.createElement("article");
  article.className = `message-bubble ${role}`;
  article.innerHTML = `
    <div class="message-head">
      <span>${role === "assistant" ? "HajiHaz AI" : "You"}</span>
      ${mode ? `<small>${escapeHtml(humanizeMode(mode))}</small>` : ""}
    </div>
    <div class="message-copy">${formatMessageHtml(content)}</div>
    ${
      notice
        ? `<div class="message-notice" role="note" aria-label="response mode note">
            <span class="message-notice-label">Response mode</span>
            <span>${escapeHtml(notice)}</span>
          </div>`
        : ""
    }
    ${
      citations && citations.length
        ? `<div class="citation-list">
            ${citations
              .map(
                (citation) => `
                  <div class="citation-card">
                    <div class="citation-head-row">
                      <strong>${
                        citation.url
                          ? `<a href="${escapeHtml(citation.url)}" target="_blank" rel="noreferrer">${escapeHtml(citation.title)}</a>`
                          : escapeHtml(citation.title)
                      }</strong>
                      <span class="citation-kind">${escapeHtml(
                        citation.kind === "knowledge"
                          ? citation.group_name || "knowledge"
                          : citation.kind === "web"
                            ? "web"
                            : citation.kind || "source"
                          )}</span>
                    </div>
                    <span>${escapeHtml(citation.excerpt)}</span>
                    ${
                      citation.url
                        ? `<div class="citation-actions">
                            <a
                              class="secondary-button secondary-button--inline"
                              href="${escapeHtml(citation.url)}"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open source
                            </a>
                          </div>`
                        : ""
                    }
                  </div>
                `
              )
              .join("")}
          </div>`
        : ""
    }
    ${role === "assistant" ? '<button class="ghost-button" data-copy-message type="button">Copy response</button>' : ""}
  `;

  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

function appendLoadingMessage() {
  const messages = document.getElementById("chatMessages");
  if (!messages) {
    return null;
  }

  const article = document.createElement("article");
  article.className = "message-bubble assistant loading";
  article.dataset.loadingBubble = "true";
  article.setAttribute("role", "status");
  article.setAttribute("aria-live", "polite");
  article.innerHTML = `
    <div class="message-head">
      <span>HajiHaz AI</span>
      <small>thinking</small>
    </div>
    <div class="loading-state">
      <div class="loading-title-row">
        <div class="loading-word" aria-label="Thinking">${buildThinkingWordMarkup()}</div>
        <div class="loading-dots" aria-hidden="true">
          <span class="loading-dot"></span>
          <span class="loading-dot"></span>
          <span class="loading-dot"></span>
        </div>
      </div>
      <p class="loading-helper">Grounding the reply in your knowledge and broader context.</p>
      <div class="loading-preview" aria-hidden="true">
        <span class="loading-bar loading-bar-long"></span>
        <span class="loading-bar loading-bar-mid"></span>
        <span class="loading-bar loading-bar-short"></span>
      </div>
    </div>
  `;

  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

function updateLoadingMessage(article, helperText) {
  if (!article) {
    return;
  }

  const helper = article.querySelector(".loading-helper");
  if (helper) {
    helper.textContent = helperText;
  }
}

function removeLoadingMessage(article) {
  if (article?.parentNode) {
    article.parentNode.removeChild(article);
  }
}

function bindCopyButtons() {
  document.querySelectorAll("[data-copy-message]").forEach((button) => {
    if (button.dataset.boundCopy === "true") {
      return;
    }

    button.dataset.boundCopy = "true";
    button.addEventListener("click", async () => {
      const content = button.parentElement?.querySelector(".message-copy")?.textContent || "";
      try {
        await navigator.clipboard.writeText(content);
        setText("chatStatusText", "Response copied.");
      } catch {
        showError("chatErrorText", "Clipboard access failed.");
      }
    });
  });
}

function initChatPage() {
  if (!document.querySelector("[data-chat-page='true']")) {
    return;
  }

  const messages = document.getElementById("chatMessages");
  const chatCard = document.querySelector(".chat-card");
  const entryGate = document.getElementById("chatEntryGate");
  const appShell = document.getElementById("chatAppShell");
  const entryGuestButton = document.getElementById("chatEntryGuestButton");
  const entryGoogleButtonHost = document.getElementById("chatEntryGoogleButton");
  const entryHelp = document.getElementById("chatEntryHelp");
  const input = document.getElementById("chatInput");
  const sendButton = document.getElementById("chatSendButton");
  const clearButton = document.getElementById("chatClearButton");
  const userCard = document.getElementById("chatUserCard");
  const userAvatar = document.getElementById("chatUserAvatar");
  const userName = document.getElementById("chatUserName");
  const userEmail = document.getElementById("chatUserEmail");
  const userStatus = document.getElementById("chatUserStatus");
  const userPill = document.getElementById("chatUserPill");
  const userLogoutButton = document.getElementById("chatUserLogoutButton");
  const newThreadButton = document.getElementById("chatNewThreadButton");
  const memoryList = document.getElementById("chatMemoryList");
  const answerModeButtons = document.querySelectorAll("[data-answer-mode]");

  if (
    !(messages instanceof HTMLDivElement) ||
    !(chatCard instanceof HTMLElement) ||
    !(entryGate instanceof HTMLElement) ||
    !(appShell instanceof HTMLElement) ||
    !(entryGuestButton instanceof HTMLButtonElement) ||
    !(entryGoogleButtonHost instanceof HTMLDivElement) ||
    !(entryHelp instanceof HTMLElement) ||
    !(input instanceof HTMLTextAreaElement) ||
    !(sendButton instanceof HTMLButtonElement) ||
    !(clearButton instanceof HTMLButtonElement) ||
    !(userCard instanceof HTMLDivElement) ||
    !(userAvatar instanceof HTMLElement) ||
    !(userName instanceof HTMLElement) ||
    !(userEmail instanceof HTMLElement) ||
    !(userStatus instanceof HTMLElement) ||
    !(userPill instanceof HTMLElement) ||
    !(userLogoutButton instanceof HTMLButtonElement) ||
    !(newThreadButton instanceof HTMLButtonElement) ||
    !(memoryList instanceof HTMLDivElement)
  ) {
    return;
  }

  const initialMessagesMarkup = messages.innerHTML;
  let loadingBubble = null;
  let loadingStageTimers = [];
  let chatHistory = [];
  let currentSessionId = window.localStorage.getItem(CHAT_SESSION_KEY) || "";
  let currentConversationTitle = "";
  let answerMode = window.localStorage.getItem(ANSWER_MODE_KEY) || "balanced";
  let entryMode = window.localStorage.getItem(CHAT_ENTRY_MODE_KEY) || "";
  let userToken = window.localStorage.getItem(CHAT_USER_TOKEN_KEY) || "";
  let currentUser = readStoredUserProfile();
  let googleAuthConfig = null;
  let remoteConversationSummaries = [];

  function persistEntryMode(mode) {
    entryMode = String(mode || "").trim();
    if (entryMode) {
      window.localStorage.setItem(CHAT_ENTRY_MODE_KEY, entryMode);
      return;
    }
    window.localStorage.removeItem(CHAT_ENTRY_MODE_KEY);
  }

  function defaultEntryHelpText() {
    return googleAuthConfig?.enabled
      ? "Sign in with Google to keep chats across devices, or continue as a guest for browser-only access."
      : "Google sign-in is not configured right now. You can still continue as a guest.";
  }

  function setEntryGateVisible(visible) {
    entryGate.hidden = !visible;
    appShell.hidden = visible;
  }

  function setChatReadyState() {
    setText("chatRuntimeStatus", "Local runtime");
    setText("chatRuntimeHint", "Stable browser client connected to FastAPI.");
    setText("chatKnowledgeStatus", "RAG connected");
    setText("chatModeStatus", "Standby");
    setText("chatCitationCount", "0");
    setText("chatStatusText", "Browser ready. API route: POST /chat");
    setText(
      "chatPanelNote",
      "Ask about business plans, internal notes, SOPs, client workflows, or anything you have stored in the knowledge base."
    );
    setStatusPill("chatFlowPill", "Ready", "ready");
    setStatusPill("chatResponsePill", "Connected", "ready");
  }

  function setAnswerModeSelection(nextMode) {
    answerMode = nextMode;
    window.localStorage.setItem(ANSWER_MODE_KEY, answerMode);
    answerModeButtons.forEach((button) => {
      if (button instanceof HTMLButtonElement) {
        const active = button.dataset.answerMode === answerMode;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      }
    });
  }

  function userInitials(profile) {
    const base = String(profile?.name || profile?.email || "H").trim();
    const parts = base.split(/\s+/).filter(Boolean);
    if (!parts.length) {
      return "H";
    }
    return parts
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() || "")
      .join("");
  }

  function renderUserState() {
    const signedIn = Boolean(userToken && currentUser);
    userCard.hidden = false;
    setStatusPill("chatUserPill", signedIn ? "Google connected" : "Guest session", signedIn ? "ready" : "idle");
    if (signedIn && currentUser) {
      userAvatar.textContent = userInitials(currentUser);
      userName.textContent = currentUser.name || currentUser.email || "Signed in user";
      userEmail.textContent = currentUser.email || "";
      userStatus.textContent = "Your chat history is now tied to this Google account and can follow you across devices.";
      userLogoutButton.textContent = "Sign out";
    } else {
      userAvatar.textContent = "H";
      userName.textContent = "Guest session";
      userEmail.textContent = "This guest session stays in this browser.";
      userStatus.textContent = "You entered as a guest. Use the button below to return to the welcome screen.";
      userLogoutButton.textContent = "Back to welcome";
    }
  }

  async function loadChatSessionsFromAccount() {
    if (!userToken) {
      remoteConversationSummaries = [];
      return;
    }
    const items = await api("/chat/sessions", { token: userToken });
    remoteConversationSummaries = Array.isArray(items)
      ? items.map((item) => ({
          id: String(item.id || ""),
          title: String(item.title || "New conversation"),
          updatedAt: item.updated_at || item.updatedAt || new Date().toISOString()
        }))
      : [];
  }

  async function fetchUserProfile() {
    if (!userToken) {
      currentUser = null;
      writeStoredUserProfile(null);
      remoteConversationSummaries = [];
      renderUserState();
      return null;
    }
    try {
      const profile = await api("/user-auth/me", { token: userToken });
      currentUser = profile;
      writeStoredUserProfile(profile);
      await loadChatSessionsFromAccount();
      renderUserState();
      return profile;
    } catch {
      userToken = "";
      currentUser = null;
      remoteConversationSummaries = [];
      window.localStorage.removeItem(CHAT_USER_TOKEN_KEY);
      writeStoredUserProfile(null);
      renderUserState();
      return null;
    }
  }

  function applySignedOutState() {
    userToken = "";
    currentUser = null;
    remoteConversationSummaries = [];
    window.localStorage.removeItem(CHAT_USER_TOKEN_KEY);
    writeStoredUserProfile(null);
    renderUserState();
    renderConversationMemoryList();
  }

  function rememberConversationSummary(summary) {
    const nextSummary = {
      id: String(summary.id || ""),
      title: String(summary.title || "New conversation"),
      updatedAt: summary.updatedAt || new Date().toISOString()
    };
    if (!nextSummary.id) {
      return;
    }

    if (currentUser) {
      remoteConversationSummaries = [
        nextSummary,
        ...remoteConversationSummaries.filter((item) => item.id !== nextSummary.id)
      ].slice(0, 20);
    }

    const nextItems = [
      nextSummary,
      ...readStoredConversationSummaries().filter((item) => item.id !== nextSummary.id)
    ];
    writeStoredConversationSummaries(nextItems);
  }

  function removeConversationSummary(sessionId) {
    if (currentUser) {
      remoteConversationSummaries = remoteConversationSummaries.filter((item) => item.id !== sessionId);
    }
    writeStoredConversationSummaries(readStoredConversationSummaries().filter((item) => item.id !== sessionId));
  }

  function renderConversationMemoryList() {
    const items = currentUser ? remoteConversationSummaries : readStoredConversationSummaries();
    if (!items.length) {
      memoryList.innerHTML = `
        <p class="sidebar-note">${
          currentUser
            ? "Signed-in conversations will appear here once you start a chat."
            : "Recent conversations in this browser will appear here after your first chat."
        }</p>
      `;
      return;
    }

    memoryList.innerHTML = items
      .map(
        (item) => `
          <button class="thread-item ${item.id === currentSessionId ? "is-active" : ""}" data-chat-session-id="${escapeHtml(item.id)}" type="button">
            <strong>${escapeHtml(item.title || "New conversation")}</strong>
            <small>${escapeHtml(formatTimestamp(item.updatedAt))}</small>
          </button>
        `
      )
      .join("");

    memoryList.querySelectorAll("[data-chat-session-id]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      button.addEventListener("click", () => {
        void loadConversation(button.dataset.chatSessionId || "");
      });
    });
  }

  function scrollConversationIntoView() {
    chatCard.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => {
      const latest = messages.lastElementChild;
      if (latest instanceof HTMLElement) {
        latest.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }, 220);
  }

  function clearLoadingState() {
    loadingStageTimers.forEach((timerId) => window.clearTimeout(timerId));
    loadingStageTimers = [];
    removeLoadingMessage(loadingBubble);
    loadingBubble = null;
  }

  function applyLoadingStage(stage) {
    if (!stage) {
      return;
    }

    setText("chatRuntimeStatus", stage.runtimeStatus);
    setText("chatRuntimeHint", stage.runtimeHint);
    setText("chatKnowledgeStatus", stage.knowledgeStatus);
    setText("chatModeStatus", stage.modeStatus);
    setText("chatCitationCount", "0");
    setText("chatPanelNote", stage.panelNote);
    setText("chatStatusText", stage.statusText);
    setStatusPill("chatFlowPill", "Thinking", "loading");
    setStatusPill("chatResponsePill", "Thinking", "loading");
    updateLoadingMessage(loadingBubble, stage.helperText);
  }

  function startLoadingExperience() {
    clearLoadingState();
    loadingBubble = appendLoadingMessage();
    CHAT_LOADING_STAGES.forEach((stage) => {
      const timerId = window.setTimeout(() => {
        applyLoadingStage(stage);
      }, stage.delay);
      loadingStageTimers.push(timerId);
    });
  }

  function resetConversation() {
    clearLoadingState();
    messages.innerHTML = initialMessagesMarkup;
    input.value = "";
    chatHistory = [];
    currentSessionId = "";
    currentConversationTitle = "";
    window.localStorage.removeItem(CHAT_SESSION_KEY);
    showError("chatErrorText", "");
    setChatReadyState();
    bindCopyButtons();
    renderConversationMemoryList();
  }

  function renderGoogleButton() {
    if (!googleAuthConfig?.enabled || !googleAuthConfig?.client_id) {
      entryGoogleButtonHost.innerHTML = `
        <button class="secondary-button entry-google-fallback" type="button" disabled>
          Sign in with Google
        </button>
      `;
      entryGoogleButtonHost.hidden = false;
      entryHelp.textContent = defaultEntryHelpText();
      return;
    }
    if (!(window.google && window.google.accounts && window.google.accounts.id)) {
      entryGoogleButtonHost.innerHTML = `
        <button class="secondary-button entry-google-fallback" type="button" disabled>
          Sign in with Google
        </button>
      `;
      entryGoogleButtonHost.hidden = false;
      entryHelp.textContent = "Google sign-in is still loading. You can continue as a guest if you prefer.";
      return;
    }

    entryGoogleButtonHost.innerHTML = "";
    entryGoogleButtonHost.hidden = false;
    window.google.accounts.id.initialize({
      client_id: googleAuthConfig.client_id,
      callback: async (payload) => {
        const credential = String(payload?.credential || "").trim();
        if (!credential) {
          return;
        }
        showError("chatErrorText", "");
        setText("chatStatusText", "Signing in with Google...");
        try {
          const response = await api("/user-auth/google", {
            method: "POST",
            body: {
              credential,
              session_id: currentSessionId || null
            }
          });
          userToken = response.token;
          currentUser = response.user;
          window.localStorage.setItem(CHAT_USER_TOKEN_KEY, userToken);
          writeStoredUserProfile(currentUser);
          persistEntryMode("google");
          if (response.claimed_session_id) {
            currentSessionId = response.claimed_session_id;
            window.localStorage.setItem(CHAT_SESSION_KEY, currentSessionId);
          }
          await loadChatSessionsFromAccount();
          renderUserState();
          renderConversationMemoryList();
          setEntryGateVisible(false);
          setText("chatStatusText", `${currentUser.name || currentUser.email} is signed in. Chats can now follow this account.`);
        } catch (error) {
          showError("chatErrorText", error instanceof Error ? error.message : "Google sign-in failed.");
          setText("chatStatusText", "Google sign-in failed.");
        }
      }
    });
    window.google.accounts.id.renderButton(entryGoogleButtonHost, {
      type: "standard",
      theme: "outline",
      size: "large",
      shape: "pill",
      text: "continue_with",
      width: 280
    });
    entryHelp.textContent = defaultEntryHelpText();
  }

  async function loadGoogleIdentityScript() {
    if (window.google && window.google.accounts && window.google.accounts.id) {
      return;
    }
    await new Promise((resolve, reject) => {
      const existing = document.querySelector("script[data-google-identity='true']");
      if (existing instanceof HTMLScriptElement) {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => reject(new Error("Google Identity script failed to load.")), { once: true });
        return;
      }
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.dataset.googleIdentity = "true";
      script.addEventListener("load", () => resolve(), { once: true });
      script.addEventListener("error", () => reject(new Error("Google Identity script failed to load.")), { once: true });
      document.head.appendChild(script);
    });
  }

  async function initializeUserAuth() {
    renderUserState();
    try {
      googleAuthConfig = await api("/user-auth/config");
    } catch {
      googleAuthConfig = { enabled: false };
    }

    await fetchUserProfile();
    renderConversationMemoryList();

    if (googleAuthConfig?.enabled) {
      try {
        await loadGoogleIdentityScript();
      } catch {
        entryHelp.textContent = "Google sign-in could not be loaded right now. You can continue as a guest.";
      }
    }
    renderGoogleButton();

    const shouldEnterWithGoogle = Boolean(userToken && currentUser);

    if (shouldEnterWithGoogle) {
      persistEntryMode("google");
      setEntryGateVisible(false);
    } else {
      persistEntryMode("");
      setEntryGateVisible(true);
      entryHelp.textContent = defaultEntryHelpText();
    }

    if (!entryGate.hidden && !appShell.hidden) {
      setEntryGateVisible(true);
    }

    if (!appShell.hidden && currentSessionId) {
      await loadConversation(currentSessionId);
    }
  }

  setChatReadyState();
  bindCopyButtons();
  setAnswerModeSelection(answerMode);
  renderUserState();
  renderConversationMemoryList();

  function createStreamingAssistantShell(mode) {
    const article = appendMessage("assistant", "", [], mode || "conversation", null);
    if (!(article instanceof HTMLElement)) {
      return null;
    }

    const copy = article.querySelector(".message-copy");
    const notice = article.querySelector(".message-notice");
    const citations = article.querySelector(".citation-list");
    const copyButton = article.querySelector("[data-copy-message]");
    if (copy instanceof HTMLElement) {
      copy.textContent = "";
    }
    if (notice instanceof HTMLElement) {
      notice.hidden = true;
    }
    if (citations instanceof HTMLElement) {
      citations.hidden = true;
    }
    if (copyButton instanceof HTMLElement) {
      copyButton.hidden = true;
    }
    return article;
  }

  function finalizeAssistantMessage(article, response) {
    if (!(article instanceof HTMLElement)) {
      return;
    }
    const modeNode = article.querySelector(".message-head small");
    if (modeNode instanceof HTMLElement) {
      modeNode.textContent = humanizeMode(response.mode);
    }

    const copy = article.querySelector(".message-copy");
    const existingCopyButton = article.querySelector("[data-copy-message]");
    if (copy instanceof HTMLElement) {
      copy.innerHTML = formatMessageHtml(response.answer || "");
    }

    article.querySelectorAll(".message-notice, .citation-list").forEach((element) => element.remove());

    const noticeMarkup = response.notice
      ? `<div class="message-notice" role="note" aria-label="response mode note">
          <span class="message-notice-label">Response mode</span>
          <span>${escapeHtml(response.notice)}</span>
        </div>`
      : "";
    const citationsMarkup = Array.isArray(response.citations) && response.citations.length
      ? `<div class="citation-list">
          ${response.citations
            .map(
              (citation) => `
                <div class="citation-card">
                  <div class="citation-head-row">
                    <strong>${
                      citation.url
                        ? `<a href="${escapeHtml(citation.url)}" target="_blank" rel="noreferrer">${escapeHtml(citation.title)}</a>`
                        : escapeHtml(citation.title)
                    }</strong>
                    <span class="citation-kind">${escapeHtml(
                      citation.kind === "knowledge"
                        ? citation.group_name || "knowledge"
                        : citation.kind === "web"
                          ? "web"
                          : citation.kind || "source"
                    )}</span>
                  </div>
                  <span>${escapeHtml(citation.excerpt)}</span>
                  ${
                    citation.url
                      ? `<div class="citation-actions">
                          <a
                            class="secondary-button secondary-button--inline"
                            href="${escapeHtml(citation.url)}"
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open source
                          </a>
                        </div>`
                      : ""
                  }
                </div>
              `
            )
            .join("")}
        </div>`
      : "";
    article.insertAdjacentHTML("beforeend", `${noticeMarkup}${citationsMarkup}`);
    if (existingCopyButton instanceof HTMLElement) {
      existingCopyButton.hidden = false;
    }
    bindCopyButtons();
  }

  function applyResponseState(response) {
    const citationCount = Array.isArray(response.citations) ? response.citations.length : 0;
    const modeLabel = humanizeMode(response.mode).replace(/\b\w/g, (character) => character.toUpperCase());
    setText(
      "chatRuntimeStatus",
      response.mode === "web" || response.mode === "knowledge_web"
        ? "Hybrid runtime"
        : response.mode === "ollama" || response.mode === "anthropic"
          ? "Live reasoning"
          : response.mode === "conversation"
            ? "Conversational runtime"
            : "Knowledge runtime"
    );
    setText(
      "chatRuntimeHint",
      response.mode === "web" || response.mode === "knowledge_web"
        ? "Saved knowledge first, then live web context where the library is thin."
        : response.mode === "ollama" || response.mode === "anthropic"
          ? "A live model shaped the reply after grounding it in saved context."
          : response.mode === "conversation"
            ? "Natural conversation stays warm and human before touching web lookup."
            : "Saved knowledge base with synthesized local guidance."
    );
    setText("chatKnowledgeStatus", citationCount ? `${citationCount} source${citationCount === 1 ? "" : "s"} used` : "Guidance mode");
    setText("chatModeStatus", modeLabel);
    setText("chatCitationCount", String(citationCount));
    setText("chatStatusText", currentConversationTitle ? `Current thread: ${currentConversationTitle}` : "Browser ready. API route: POST /chat");
    setText(
      "chatPanelNote",
      response.mode === "knowledge_web"
        ? "This answer blended your own material with broader live web context."
        : response.mode === "web"
          ? "No strong local match was found, so the assistant used broader live web context."
          : response.mode === "conversation"
            ? "Casual conversation stays human while deeper questions still use your saved knowledge."
            : citationCount
              ? "This answer was grounded in your saved knowledge and then summarized into a cleaner response."
              : "This answer leaned on local guidance because no strong citation was available."
    );
    setStatusPill("chatFlowPill", "Ready", "ready");
    setStatusPill(
      "chatResponsePill",
      response.mode === "knowledge_web"
        ? "Hybrid"
        : response.mode === "conversation"
          ? "Conversing"
          : citationCount
            ? "Grounded"
            : "Responded",
      "ready"
    );
  }

  function parseEventStreamChunk(buffer, onEvent) {
    let remaining = buffer;
    let boundaryIndex = remaining.indexOf("\n\n");
    while (boundaryIndex !== -1) {
      const rawEvent = remaining.slice(0, boundaryIndex);
      remaining = remaining.slice(boundaryIndex + 2);
      const lines = rawEvent.split("\n");
      let eventName = "message";
      const dataLines = [];
      lines.forEach((line) => {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      });
      if (dataLines.length) {
        try {
          onEvent(eventName, JSON.parse(dataLines.join("\n")));
        } catch {
          // Ignore malformed event payloads and continue the stream.
        }
      }
      boundaryIndex = remaining.indexOf("\n\n");
    }
    return remaining;
  }

  async function streamChatResponse(payload, shouldScrollConversation) {
    const response = await fetchWithTimeout(
      "/chat/stream",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(userToken ? { Authorization: `Bearer ${userToken}` } : {})
        },
        body: JSON.stringify(payload)
      },
      LONG_REQUEST_TIMEOUT_MS
    );

    if (!response.ok) {
      let detail = response.statusText || "Chat failed.";
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch {
        detail = response.statusText || "Chat failed.";
      }
      throw new Error(detail);
    }

    if (!response.body) {
      return api("/chat", { method: "POST", body: payload });
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamedText = "";
    let finalPayload = null;
    let assistantArticle = null;

    const handleStreamEvent = (eventName, eventPayload) => {
      if (eventName === "stage") {
        setText("chatStatusText", eventPayload.message || "Thinking...");
        return;
      }

      if (eventName === "session") {
        currentSessionId = eventPayload.session_id || currentSessionId;
        currentConversationTitle = eventPayload.conversation_title || currentConversationTitle;
        if (currentSessionId) {
          window.localStorage.setItem(CHAT_SESSION_KEY, currentSessionId);
          rememberConversationSummary({
            id: currentSessionId,
            title: currentConversationTitle || "New conversation",
            updatedAt: new Date().toISOString()
          });
          renderConversationMemoryList();
        }
        return;
      }

      if (eventName === "delta") {
        if (!assistantArticle) {
          clearLoadingState();
          assistantArticle = createStreamingAssistantShell("conversation");
        }
        if (!(assistantArticle instanceof HTMLElement)) {
          return;
        }
        streamedText += eventPayload.text || "";
        const copy = assistantArticle.querySelector(".message-copy");
        if (copy instanceof HTMLElement) {
          copy.textContent = streamedText;
        }
        if (shouldScrollConversation) {
          scrollConversationIntoView();
        }
        return;
      }

      if (eventName === "complete") {
        finalPayload = eventPayload;
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      buffer = parseEventStreamChunk(buffer, handleStreamEvent);
      if (done) {
        break;
      }
    }

    if (!finalPayload) {
      throw new Error("Streaming ended before a final answer arrived.");
    }

    clearLoadingState();
    if (!assistantArticle) {
      assistantArticle = createStreamingAssistantShell(finalPayload.mode);
    }
    finalizeAssistantMessage(assistantArticle, finalPayload);
    return finalPayload;
  }

  function renderConversationMessages(messagesPayload) {
    messages.innerHTML = "";
    if (!Array.isArray(messagesPayload) || !messagesPayload.length) {
      messages.innerHTML = initialMessagesMarkup;
      bindCopyButtons();
      return;
    }

    messagesPayload.forEach((message) => {
      appendMessage(message.role, message.content, message.citations || [], message.mode, message.notice);
    });
    bindCopyButtons();
  }

  async function loadConversation(sessionId) {
    const nextSessionId = String(sessionId || "").trim();
    if (!nextSessionId) {
      resetConversation();
      return;
    }

    try {
      const payload = await api(`/chat/session/${encodeURIComponent(nextSessionId)}`, {
        token: userToken || undefined
      });
      currentSessionId = payload.session.id;
      currentConversationTitle = payload.session.title || "";
      window.localStorage.setItem(CHAT_SESSION_KEY, currentSessionId);
      setAnswerModeSelection(payload.session.answer_mode || answerMode);
      renderConversationMessages(payload.messages || []);
      chatHistory = (payload.messages || []).map((item) => ({ role: item.role, content: item.content }));
      rememberConversationSummary({
            id: payload.session.id,
            title: payload.session.title || "New conversation",
            updatedAt: payload.session.updated_at || new Date().toISOString()
      });
      renderConversationMemoryList();
      if (payload.messages && payload.messages.length) {
        const lastAssistant = [...payload.messages].reverse().find((item) => item.role === "assistant");
        if (lastAssistant) {
          applyResponseState(lastAssistant);
        } else {
          setChatReadyState();
        }
      } else {
        setChatReadyState();
      }
    } catch (error) {
      removeConversationSummary(nextSessionId);
      if (currentSessionId === nextSessionId) {
        window.localStorage.removeItem(CHAT_SESSION_KEY);
        currentSessionId = "";
      }
      renderConversationMemoryList();
      resetConversation();
      showError("chatErrorText", error instanceof Error ? error.message : "Conversation could not be restored.");
    }
  }

  async function submitMessage(message, options = {}) {
    const nextMessage = (message || input.value).trim();
    if (!nextMessage) {
      return;
    }

    const shouldScrollConversation = Boolean(options.scrollToConversation);
    const requestHistory = chatHistory.slice(-8);

    showError("chatErrorText", "");
    appendMessage("user", nextMessage);
    chatHistory.push({ role: "user", content: nextMessage });
    startLoadingExperience();
    if (shouldScrollConversation) {
      scrollConversationIntoView();
    }
    input.value = "";
    sendButton.disabled = true;
    clearButton.disabled = true;

    try {
      const response = await streamChatResponse(
        { message: nextMessage, history: requestHistory, session_id: currentSessionId || null, answer_mode: answerMode },
        shouldScrollConversation
      );
      chatHistory.push({ role: "assistant", content: response.answer });
      currentSessionId = response.session_id || currentSessionId;
      currentConversationTitle = response.conversation_title || currentConversationTitle;
      if (currentSessionId) {
        window.localStorage.setItem(CHAT_SESSION_KEY, currentSessionId);
        rememberConversationSummary({
            id: currentSessionId,
            title: currentConversationTitle || nextMessage,
            updatedAt: new Date().toISOString()
        });
        renderConversationMemoryList();
      }
      if (shouldScrollConversation) {
        scrollConversationIntoView();
      }
      applyResponseState(response);
    } catch (error) {
      clearLoadingState();
      if (chatHistory.length && chatHistory[chatHistory.length - 1]?.role === "user") {
        chatHistory.pop();
      }
      showError("chatErrorText", error instanceof Error ? error.message : "Chat failed.");
      setText("chatRuntimeStatus", "Knowledge runtime");
      setText("chatRuntimeHint", "The app is still reachable, but this request needs a retry.");
      setText("chatKnowledgeStatus", "Retry needed");
      setText("chatModeStatus", "Retry needed");
      setText("chatCitationCount", "0");
      setText("chatStatusText", "Browser ready. API route: POST /chat");
      setText("chatPanelNote", "The request hit an error. You can retry or change the prompt.");
      setStatusPill("chatFlowPill", "Retry", "warning");
      setStatusPill("chatResponsePill", "Failed", "warning");
    } finally {
      sendButton.disabled = false;
      clearButton.disabled = false;
    }
  }

  sendButton.addEventListener("click", () => {
    void submitMessage();
  });

  input.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void submitMessage();
    }
  });

  clearButton.addEventListener("click", () => {
    resetConversation();
  });

  newThreadButton.addEventListener("click", () => {
    resetConversation();
  });

  userLogoutButton.addEventListener("click", () => {
    const activeToken = userToken;
    void (async () => {
      if (activeToken) {
        try {
          await api("/user-auth/logout", {
            method: "POST",
            token: activeToken
          });
        } catch {
          // Local sign-out still wins even if the remote logout call fails.
        }
      }
      applySignedOutState();
      resetConversation();
      persistEntryMode("");
      setEntryGateVisible(true);
      entryHelp.textContent = defaultEntryHelpText();
    })();
  });

  entryGuestButton.addEventListener("click", () => {
    persistEntryMode("guest");
    setEntryGateVisible(false);
    renderUserState();
    renderConversationMemoryList();
    setText("chatStatusText", "Guest mode is active. Your chats stay in this browser.");
    if (currentSessionId) {
      void loadConversation(currentSessionId);
      return;
    }
    setChatReadyState();
  });

  document.querySelectorAll("[data-prompt]").forEach((button) => {
    if (button instanceof HTMLButtonElement) {
      button.addEventListener("click", () => {
        void submitMessage(button.dataset.prompt || "", { scrollToConversation: true });
      });
    }
  });

  answerModeButtons.forEach((button) => {
    if (button instanceof HTMLButtonElement) {
      button.addEventListener("click", () => {
        setAnswerModeSelection(button.dataset.answerMode || "balanced");
      });
    }
  });

  void initializeUserAuth();
}

function setAdminGatedVisible(visible) {
  const adminShell = document.querySelector("[data-admin-page='true']");
  if (adminShell instanceof HTMLElement) {
    adminShell.classList.toggle("admin-locked", !visible);
    adminShell.classList.toggle("admin-authenticated", visible);
  }
  document.querySelectorAll("[data-admin-gated='true']").forEach((element) => {
    if (element instanceof HTMLElement) {
      element.hidden = !visible;
    }
  });
}

function setRuntimePulseAlert(message, status = "offline") {
  const alert = document.getElementById("adminRuntimeAlert");
  const title = document.getElementById("adminRuntimeAlertTitle");
  const text = document.getElementById("adminRuntimeAlertText");
  if (!(alert instanceof HTMLElement) || !(title instanceof HTMLElement) || !(text instanceof HTMLElement)) {
    return;
  }
  const visible = Boolean(message && status !== "live");
  alert.hidden = !visible;
  if (visible) {
    title.textContent = status === "degraded" ? "Provider degraded" : "Provider issue detected";
    text.textContent = message;
  }
}

function renderLockedState() {
  setAdminGatedVisible(false);
  setText("adminWorkspaceAccount", "Protected");
  setText("adminDocumentsCount", "0");
  setText("adminChunksCount", "0");
  setText("adminGroupsCount", "0");
  setText("adminSourcesCount", "0");
  setText("adminAiProvider", "Locked");
  setText("adminCheckStatus", "Waiting");
  setText("adminProviderReady", "Login required");
  setText("adminOllamaReady", "Login required");
  setText("adminLibrarySummary", "No data yet");
  setText("adminOpsScore", "Locked");
  setText("adminRequestsToday", "0");
  setText("adminGroundingRate", "Waiting for analytics.");
  setText("adminRuntimeSummary", "Checking provider reachability from this server now.");
  setText("adminSideProvider", "Checking…");
  setText("adminSideReady", "Checking…");
  setText("adminUptime", "Checking…");
  setText("adminLastChecked", "Waiting");
  setText("adminAlertCount", "Restricted");
  setText("adminCpuLoad", "Restricted");
  setText("adminMemoryUsage", "Restricted");
  setText("adminDiskUsage", "Restricted");
  setText("adminRailCpu", "0.00");
  setText("adminRailMemory", "0%");
  setText("adminRailDisk", "0%");
  setMeter("adminCpuMeter", 0);
  setMeter("adminMemoryMeter", 0);
  setMeter("adminDiskMeter", 0);
  setText("adminCurrentUserEmail", "Login required");
  setText("adminUsersCount", "0");
  setText("adminDirectorySummary", "0 accounts");
  setText("adminProfileNameLabel", "Workspace operator");
  setText("adminProfileEmail", "Login required");
  setText("adminProfileAvatarPreview", "SK");
  setText("adminProfileStatus", "Profile locked.");
  setText("adminPasswordStatus", "Waiting");
  setText("adminCreateUserStatus", "Waiting");
  setText("adminBackupStatus", "No backup created in this session.");
  setText("adminSourceHealthCount", "0 sources");
  setText("adminAlertsSummary", "0 alerts");
  setText("adminHealthChecksSummary", "0 checks");
  setText("adminLogsSummary", "0 events");
  setText("adminLogTailSummary", "0 lines");
  setText("adminAnalyticsSummary", "0 requests");
  setText("adminSecretAuditSummary", "Waiting");
  setText("adminMetricHistorySummary", "0 snapshots");
  setText("adminMaintenanceSummary", "Standby");
  setStatusPill("adminAccessPill", "Locked", "idle");
  setStatusPill("adminRuntimePulsePill", "Checking", "idle");
  setRuntimePulseAlert("", "offline");
  renderDebugCards("adminSourceHealthList", []);
  renderDebugCards("adminAlertsList", []);
  renderDebugCards("adminHealthChecksList", []);
  renderDebugCards("adminLogsList", []);
  renderDebugCards("adminLogTailList", []);
  renderDebugCards("adminBackupsList", []);
  renderDebugCards("adminAnalyticsList", []);
  renderDebugCards("adminSecretAuditList", []);
  renderDebugCards("adminMetricHistoryList", []);
  renderDebugCards("adminMaintenanceList", []);
  renderAdminUsers([], "");
  renderAdminProfile(null);
  renderDocuments([]);
}

function renderStats(stats) {
  const providerName = stats.ai_provider || "unknown";
  const providerLabels = {
    hybrid: "Knowledge + web",
    offline: "Knowledge only",
    auto: "Auto",
    ollama: stats.web_search_enabled ? "Ollama + web" : "Ollama + knowledge",
    anthropic: stats.web_search_enabled ? "Live AI + web" : "Live AI + knowledge"
  };
  const providerLabel = providerLabels[providerName] || providerName.charAt(0).toUpperCase() + providerName.slice(1);
  const readiness = stats.provider_ready
    ? stats.web_search_enabled && providerName === "hybrid"
      ? "Smart fallback ready"
      : stats.web_search_enabled && (providerName === "ollama" || providerName === "anthropic")
        ? "Online reasoning ready"
      : "Ready"
    : "Fallback only";
  const ollamaState = stats.ollama_configured ? "Reachable" : "Unavailable";

  setText("adminDocumentsCount", String(stats.documents));
  setText("adminChunksCount", String(stats.chunks));
  setText("adminGroupsCount", String(stats.groups || 0));
  setText("adminSourcesCount", `${stats.active_sources || 0}/${stats.sources || 0}`);
  setText("adminAiProvider", providerLabel);
  setText("adminCheckStatus", stats.provider_ready ? "Healthy" : "Watch");
  setText("adminProviderReady", readiness);
  setText("adminOllamaReady", ollamaState);
  setText("adminLibrarySummary", `${stats.documents} docs / ${stats.chunks} chunks / ${stats.active_sources || 0} active sources`);
  setText(
    "adminRuntimeSummary",
    stats.provider_ready
      ? providerName === "hybrid"
        ? `Knowledge-first mode is live and will reach the open web when your library does not fully cover the question.`
        : stats.web_search_enabled && providerName === "ollama"
          ? `${providerLabel} is live, can reason over your saved knowledge, and can pull broader web context for generic questions.`
        : `${providerLabel} is live and grounded by ${stats.documents} documents in your retrieval library.`
      : `${providerLabel} is available in limited mode. Your retrieval library still has ${stats.documents} documents ready to cite.`
  );
  setText("adminSideProvider", providerLabel);
  setText("adminSideReady", readiness);
}

function renderDebugCards(id, items, formatter) {
  const container = document.getElementById(id);
  if (!container) {
    return;
  }

  const normalizedItems = Array.isArray(items) ? items : [];
  if (!normalizedItems.length) {
    container.innerHTML = `<div class="empty-state compact">No diagnostics yet.</div>`;
    return;
  }

  container.innerHTML = normalizedItems
    .map((item) => formatter(item))
    .join("");
}

function renderDebugSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    return;
  }

  const sourceHealth = Array.isArray(snapshot.source_health) ? snapshot.source_health : [];
  const alerts = Array.isArray(snapshot.recent_alerts) ? snapshot.recent_alerts : [];
  const checks = Array.isArray(snapshot.recent_health_checks) ? snapshot.recent_health_checks : [];
  const logs = Array.isArray(snapshot.recent_logs) ? snapshot.recent_logs : [];
  const logTail = Array.isArray(snapshot.log_tail) ? snapshot.log_tail : [];
  const backups = Array.isArray(snapshot.backups) ? snapshot.backups : [];
  const metricHistory = Array.isArray(snapshot.metric_history) ? snapshot.metric_history : [];
  const analytics = snapshot.analytics && typeof snapshot.analytics === "object" ? snapshot.analytics : {};
  const secretAudit = snapshot.secret_audit && typeof snapshot.secret_audit === "object" ? snapshot.secret_audit : {};
  const metrics = snapshot.resource_metrics && typeof snapshot.resource_metrics === "object" ? snapshot.resource_metrics : {};

  setText("adminUptime", formatDuration(snapshot.uptime_seconds || 0));
  setText("adminLastChecked", formatTimestamp(snapshot.last_checked_at));
  setText("adminAlertCount", String(alerts.length));
  setText("adminCpuLoad", Number(metrics.cpu_load_1 || 0).toFixed(2));
  setText("adminMemoryUsage", `${Number(metrics.memory_percent || 0).toFixed(1)}%`);
  setText("adminDiskUsage", `${Number(metrics.disk_percent || 0).toFixed(1)}%`);
  setText("adminRailCpu", Number(metrics.cpu_load_1 || 0).toFixed(2));
  setText("adminRailMemory", `${Number(metrics.memory_percent || 0).toFixed(1)}%`);
  setText("adminRailDisk", `${Number(metrics.disk_percent || 0).toFixed(1)}%`);
  setMeter("adminCpuMeter", Math.min(100, Number(metrics.cpu_load_1 || 0) * 18));
  setMeter("adminMemoryMeter", Number(metrics.memory_percent || 0));
  setMeter("adminDiskMeter", Number(metrics.disk_percent || 0));
  setText("adminSourceHealthCount", `${sourceHealth.length} source${sourceHealth.length === 1 ? "" : "s"}`);
  setText("adminAlertsSummary", `${alerts.length} alert${alerts.length === 1 ? "" : "s"}`);
  setText("adminHealthChecksSummary", `${checks.length} check${checks.length === 1 ? "" : "s"}`);
  setText("adminLogsSummary", `${logs.length} event${logs.length === 1 ? "" : "s"}`);
  setText("adminLogTailSummary", `${logTail.length} line${logTail.length === 1 ? "" : "s"}`);
  setText("adminAnalyticsSummary", `${analytics.total_requests || 0} requests / ${analytics.window_days || 0}d`);
  setText("adminSecretAuditSummary", secretAudit.status || "Waiting");
  setText("adminMetricHistorySummary", `${metricHistory.length} snapshot${metricHistory.length === 1 ? "" : "s"}`);
  const dailyRequests = analytics.daily_requests || [];
  const todaysRequests = dailyRequests.length ? dailyRequests[dailyRequests.length - 1].count || 0 : 0;
  const warningSignals =
    alerts.filter((item) => item.level === "error" || item.level === "warning").length +
    checks.filter((item) => item.status !== "ok").length +
    (secretAudit.status && secretAudit.status !== "healthy" ? 1 : 0);
  const opsScore = Math.max(72, 100 - warningSignals * 8 - Math.round(Number(metrics.disk_percent || 0) / 12));
  setText("adminOpsScore", warningSignals ? `${opsScore} watch` : `${opsScore} healthy`);
  setText("adminRequestsToday", String(todaysRequests));
  setText(
    "adminGroundingRate",
    `${Number(analytics.average_citations || 0).toFixed(1)} avg citations · ${analytics.total_requests || 0} requests/${analytics.window_days || 0}d`
  );

  renderDebugCards("adminSourceHealthList", sourceHealth, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.source_label || item.group_name || "Ungrouped")}</strong>
        <span class="document-source-pill">${escapeHtml(item.source)}</span>
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <div class="document-meta-row">
        <span>${item.documents} docs · ${item.enabled ? "enabled" : "disabled"}</span>
        <span>${escapeHtml(formatTimestamp(item.last_updated))}</span>
      </div>
      <div class="document-meta-row">
        <span>${escapeHtml(item.source_url || item.group_name || "Ready for retrieval")}</span>
        <span class="status-pill ${item.health === "healthy" ? "ready" : item.health === "disabled" ? "idle" : "warning"}">${escapeHtml(item.health)}</span>
      </div>
      <div class="document-actions">
        ${
          item.enabled
            ? `<button class="secondary-button" data-source-disable="${encodeURIComponent(item.source_key)}" type="button">Disable</button>`
            : `<button class="secondary-button" data-source-enable="${encodeURIComponent(item.source_key)}" type="button">Enable</button>`
        }
        <button class="secondary-button" data-source-reindex="${encodeURIComponent(item.source_key)}" type="button">Reindex</button>
        ${
          item.syncable
            ? `<button class="secondary-button" data-source-sync="${encodeURIComponent(item.source_key)}" type="button">Sync</button>`
            : ""
        }
      </div>
    </article>
  `);

  renderDebugCards("adminAlertsList", alerts, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.title)}</strong>
        <span class="status-pill ${item.level === "error" ? "warning" : "idle"}">${escapeHtml(item.level)}</span>
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <div class="document-meta-row">
        <span>${escapeHtml(item.source)}</span>
        <span>${escapeHtml(formatTimestamp(item.created_at))}</span>
      </div>
    </article>
  `);

  renderDebugCards("adminHealthChecksList", checks, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.name)}</strong>
        <span class="status-pill ${item.status === "ok" ? "ready" : "warning"}">${escapeHtml(item.status)}</span>
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <div class="document-meta-row">
        <span>${escapeHtml(formatTimestamp(item.created_at))}</span>
      </div>
    </article>
  `);

  renderDebugCards("adminLogsList", logs, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.method)} ${escapeHtml(item.path)}</strong>
        <span>${item.status_code} · ${item.duration_ms.toFixed(0)}ms</span>
      </div>
      <p>${escapeHtml(item.error_message || "No error recorded.")}</p>
      <div class="document-meta-row">
        <span>${escapeHtml(formatTimestamp(item.created_at))}</span>
      </div>
    </article>
  `);

  renderDebugCards("adminLogTailList", logTail, (line) => `
    <article class="debug-card log-tail-card">
      <p>${escapeHtml(String(line || ""))}</p>
    </article>
  `);

  renderDebugCards("adminBackupsList", backups, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.archive_name)}</strong>
        <span>${escapeHtml(formatBytes(item.size_bytes))}</span>
      </div>
      <p>${escapeHtml(item.note || "Backup archive ready.")}</p>
      <div class="document-meta-row">
        <span>${escapeHtml(formatTimestamp(item.created_at))}</span>
        <span class="status-pill ${item.download_ready ? "ready" : "warning"}">${item.download_ready ? "download ready" : "missing"}</span>
      </div>
      ${
        item.download_ready
          ? `<div class="document-actions">
              <button class="secondary-button" data-backup-download="${item.id}" type="button">Download</button>
            </div>`
          : ""
      }
    </article>
  `);

  renderDebugCards("adminAnalyticsList", analytics.daily_requests || [], (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.day)}</strong>
        <span>${item.count} requests</span>
      </div>
      <p>Avg prompt ${Number(analytics.average_prompt_length || 0).toFixed(1)} chars · Avg answer ${Number(analytics.average_answer_length || 0).toFixed(1)} chars · Avg citations ${Number(analytics.average_citations || 0).toFixed(1)}</p>
      <div class="document-meta-row">
        <span>${escapeHtml(JSON.stringify(analytics.by_mode || {}))}</span>
      </div>
    </article>
  `);

  renderDebugCards("adminSecretAuditList", secretAudit.checks || [], (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.name)}</strong>
        <span class="status-pill ${item.ok ? "ready" : "warning"}">${item.ok ? "ok" : "needs work"}</span>
      </div>
      <p>${escapeHtml(item.detail)}</p>
    </article>
  `);

  renderDebugCards("adminMetricHistoryList", metricHistory, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(formatTimestamp(item.created_at))}</strong>
        <span>${item.ollama_reachable ? "Ollama ok" : "Ollama watch"}</span>
      </div>
      <p>CPU ${Number(item.cpu_load_1 || 0).toFixed(2)} / ${Number(item.cpu_load_5 || 0).toFixed(2)} · Memory ${formatBytes(item.memory_used_bytes)} of ${formatBytes(item.memory_total_bytes)} · Disk ${formatBytes(item.disk_used_bytes)} of ${formatBytes(item.disk_total_bytes)}</p>
      <div class="document-meta-row">
        <span>${escapeHtml(item.notes || "No note")}</span>
      </div>
    </article>
  `);
}

function renderAdminUsers(users, currentEmail) {
  const container = document.getElementById("adminUsersList");
  const entries = Array.isArray(users) ? users : [];
  const activeEmail = String(currentEmail || "").trim().toLowerCase();

  setText("adminUsersCount", String(entries.length));
  setText("adminDirectorySummary", `${entries.length} account${entries.length === 1 ? "" : "s"}`);
  setText("adminCurrentUserEmail", currentEmail || "Login required");
  setText("adminWorkspaceAccount", currentEmail || "Protected");

  if (!container) {
    return;
  }

  if (!entries.length) {
    container.innerHTML = `<div class="empty-state compact">No admin accounts available yet.</div>`;
    return;
  }

  container.innerHTML = entries
    .map((entry) => {
      const email = String(entry.email || "");
      const isCurrent = Boolean(entry.is_current) || email.toLowerCase() === activeEmail;
      const displayName = String(entry.display_name || email);
      const roleTitle = String(entry.role_title || "Workspace operator");
      return `
        <article class="admin-user-card">
          <div class="document-meta-row">
            <strong>${escapeHtml(displayName)}</strong>
            <span class="status-pill ${isCurrent ? "ready" : "idle"}">${isCurrent ? "Current session" : "Admin"}</span>
          </div>
          <p>${escapeHtml(roleTitle)} · ${escapeHtml(email)}</p>
          <div class="document-meta-row">
            <span>Created ${escapeHtml(formatTimestamp(entry.created_at))}</span>
            <span>Updated ${escapeHtml(formatTimestamp(entry.updated_at))}</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function adminInitials(profile) {
  const base = String(profile?.display_name || profile?.email || "SK").trim();
  const parts = base.split(/\s+/).filter(Boolean);
  if (!parts.length) {
    return "SK";
  }
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function renderAdminProfile(profile) {
  const currentProfile = profile && typeof profile === "object" ? profile : {};
  const displayNameInput = document.getElementById("adminProfileDisplayNameInput");
  const roleInput = document.getElementById("adminProfileRoleInput");
  const timezoneInput = document.getElementById("adminProfileTimezoneInput");
  const bioInput = document.getElementById("adminProfileBioInput");
  const notificationsInput = document.getElementById("adminProfileNotificationsInput");
  const avatarButton = document.getElementById("adminProfileAvatarButton");
  const avatarPreview = document.getElementById("adminProfileAvatarPreview");

  const displayName = String(currentProfile.display_name || currentProfile.email || "Workspace operator");
  const roleTitle = String(currentProfile.role_title || "Workspace operator");
  const avatarUrl = String(currentProfile.avatar_url || "").trim();

  setText("adminProfileNameLabel", displayName);
  setText("adminProfileEmail", currentProfile.email || "Login required");
  setText("adminProfileStatus", currentProfile.email ? "Profile synced." : "Profile locked.");

  if (displayNameInput instanceof HTMLInputElement) {
    displayNameInput.value = currentProfile.display_name || "";
  }
  if (roleInput instanceof HTMLInputElement) {
    roleInput.value = roleTitle;
  }
  if (timezoneInput instanceof HTMLInputElement) {
    timezoneInput.value = currentProfile.timezone || "";
  }
  if (bioInput instanceof HTMLTextAreaElement) {
    bioInput.value = currentProfile.bio || "";
  }
  if (notificationsInput instanceof HTMLInputElement) {
    notificationsInput.checked = Boolean(currentProfile.notifications_enabled);
  }
  if (avatarPreview instanceof HTMLElement) {
    avatarPreview.textContent = adminInitials(currentProfile);
  }
  if (avatarButton instanceof HTMLElement) {
    avatarButton.classList.toggle("has-image", Boolean(avatarUrl));
    avatarButton.style.backgroundImage = avatarUrl ? `url("${avatarUrl}")` : "";
  }
}

function renderDocuments(documents) {
  const grid = document.getElementById("adminDocumentsGrid");
  if (!grid) {
    return;
  }

  const emptyState = document.getElementById("adminEmptyState");
  const searchInput = document.getElementById("adminSearchInput");
  const items = Array.isArray(documents) ? documents : [];
  const query =
    searchInput instanceof HTMLInputElement ? searchInput.value.trim().toLowerCase() : "";
  const filteredItems = !query
    ? items
    : items.filter((entry) => {
        const haystack = [
          entry.title,
          entry.content,
          entry.source,
          entry.group_name,
          entry.source_url,
          ...(Array.isArray(entry.tags) ? entry.tags : [])
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      });

  setText(
    "adminDocumentItemsCount",
    query
      ? `${filteredItems.length} of ${items.length} item${items.length === 1 ? "" : "s"}`
      : `${items.length} item${items.length === 1 ? "" : "s"}`
  );

  if (!filteredItems.length) {
    grid.innerHTML = "";
    grid.hidden = true;
    if (emptyState) {
      emptyState.textContent = items.length
        ? "No documents match the current search. Try a broader keyword or clear the filter."
        : "No knowledge added yet. Unlock the workspace and add your first document to seed the assistant.";
      emptyState.hidden = false;
    }
    return;
  }

  if (emptyState) {
    emptyState.hidden = true;
  }
  grid.hidden = false;
  const groups = filteredItems.reduce((accumulator, entry) => {
    const groupName = entry.group_name || "Ungrouped";
    if (!accumulator[groupName]) {
      accumulator[groupName] = [];
    }
    accumulator[groupName].push(entry);
    return accumulator;
  }, {});

  grid.innerHTML = Object.entries(groups)
    .map(
      ([groupName, entries]) => `
        <section class="document-group">
          <div class="document-group-head">
            <h3>${escapeHtml(groupName)}</h3>
            <span>${entries.length} item${entries.length === 1 ? "" : "s"}</span>
          </div>
          <div class="document-group-grid">
            ${entries
              .map((entry) => {
                const tags = Array.isArray(entry.tags) ? entry.tags : [];
                return `
                  <article class="document-card">
                    <div class="document-head">
                      <h3>${escapeHtml(entry.title)}</h3>
                      <span class="document-source-pill">${escapeHtml(entry.source || "manual")}</span>
                    </div>
                    ${
                      entry.core_persona
                        ? `<div class="document-badge-row">
                            <span class="persona-badge">Core persona</span>
                          </div>`
                        : ""
                    }
                    <p>${escapeHtml(entry.content)}</p>
                    ${
                      tags.length
                        ? `<div class="tag-row">
                            ${tags.map((tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`).join("")}
                          </div>`
                        : ""
                    }
                    <div class="document-meta-row">
                      <span class="helper-text">${escapeHtml(entry.source_url || "Ready for retrieval")}</span>
                      <span class="document-timestamp">${escapeHtml(formatTimestamp(entry.updated_at))}</span>
                    </div>
                    <div class="document-actions">
                      <button class="secondary-button" data-toggle-core-persona="${entry.id}" type="button">${
                        entry.core_persona ? "Remove core persona" : "Mark core persona"
                      }</button>
                      <button class="secondary-button" data-edit-document="${entry.id}" type="button">Edit</button>
                      <button class="danger-button" data-delete-document="${entry.id}" type="button">Delete</button>
                    </div>
                  </article>
                `;
              })
              .join("")}
          </div>
        </section>
      `
    )
    .join("");
}

function titleFromFilename(name) {
  return String(name || "Imported document")
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function parseCsvLine(line) {
  const values = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && inQuotes && next === '"') {
      current += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === "," && !inQuotes) {
      values.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }

  values.push(current.trim());
  return values;
}

function parseCsvDocuments(text, fileName) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) {
    return [];
  }

  const headers = parseCsvLine(lines[0]).map((value) => value.toLowerCase());
  return lines.slice(1).flatMap((line, index) => {
    const values = parseCsvLine(line);
    const record = Object.fromEntries(headers.map((header, headerIndex) => [header, values[headerIndex] || ""]));
    const content = (record.content || record.body || record.text || "").trim();
    if (!content) {
      return [];
    }
    const rawTags = record.tags || record.tag || "";
    return [
      {
        title: (record.title || record.name || `${titleFromFilename(fileName)} ${index + 1}`).trim(),
        content,
        tags: rawTags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        source: (record.source || "upload").trim() || "upload"
      }
    ];
  });
}

function normalizeImportDocument(item, fallbackTitle) {
  if (!item || typeof item !== "object") {
    return null;
  }

  const content = String(item.content || item.body || item.text || "").trim();
  if (!content) {
    return null;
  }

  const rawTags = Array.isArray(item.tags) ? item.tags : String(item.tags || "").split(",");
  return {
    title: String(item.title || item.name || fallbackTitle || "Imported document").trim(),
    content,
    tags: rawTags.map((tag) => String(tag).trim()).filter(Boolean),
    source: String(item.source || "upload").trim() || "upload"
  };
}

function parseJsonDocuments(text, fileName) {
  const parsed = JSON.parse(text);
  if (Array.isArray(parsed)) {
    return parsed
      .map((entry, index) => normalizeImportDocument(entry, `${titleFromFilename(fileName)} ${index + 1}`))
      .filter(Boolean);
  }
  if (Array.isArray(parsed.documents)) {
    return parsed.documents
      .map((entry, index) => normalizeImportDocument(entry, `${titleFromFilename(fileName)} ${index + 1}`))
      .filter(Boolean);
  }
  const single = normalizeImportDocument(parsed, titleFromFilename(fileName));
  return single ? [single] : [];
}

async function parseImportFiles(files) {
  const imported = [];
  for (const file of files) {
    const text = await file.text();
    const extension = String(file.name.split(".").pop() || "").toLowerCase();
    if (!text.trim()) {
      continue;
    }
    if (extension === "json") {
      imported.push(...parseJsonDocuments(text, file.name));
      continue;
    }
    if (extension === "csv") {
      imported.push(...parseCsvDocuments(text, file.name));
      continue;
    }
    imported.push({
      title: titleFromFilename(file.name) || "Imported document",
      content: text.trim(),
      tags: [],
      source: "upload"
    });
  }
  return imported;
}

function initAdminPage() {
  if (!document.querySelector("[data-admin-page='true']")) {
    return;
  }

  initAdminThemeControls();

  const emailInput = document.getElementById("adminEmailInput");
  const passwordInput = document.getElementById("adminPasswordInput");
  const titleInput = document.getElementById("adminTitleInput");
  const groupInput = document.getElementById("adminGroupInput");
  const tagsInput = document.getElementById("adminTagsInput");
  const sourceUrlInput = document.getElementById("adminSourceUrlInput");
  const corePersonaInput = document.getElementById("adminCorePersonaInput");
  const contentInput = document.getElementById("adminContentInput");
  const importInput = document.getElementById("adminImportInput");
  const importGroupInput = document.getElementById("adminImportGroupInput");
  const importTagsInput = document.getElementById("adminImportTagsInput");
  const importButton = document.getElementById("adminImportButton");
  const urlInput = document.getElementById("adminUrlInput");
  const urlGroupInput = document.getElementById("adminUrlGroupInput");
  const urlTagsInput = document.getElementById("adminUrlTagsInput");
  const urlImportButton = document.getElementById("adminUrlImportButton");
  const searchInput = document.getElementById("adminSearchInput");
  const loginButton = document.getElementById("adminLoginButton");
  const logoutButton = document.getElementById("adminLogoutButton");
  const cancelEditButton = document.getElementById("adminCancelEditButton");
  const saveButton = document.getElementById("adminSaveButton");
  const currentPasswordInput = document.getElementById("adminCurrentPasswordInput");
  const newPasswordInput = document.getElementById("adminNewPasswordInput");
  const confirmPasswordInput = document.getElementById("adminConfirmPasswordInput");
  const changePasswordButton = document.getElementById("adminChangePasswordButton");
  const newUserEmailInput = document.getElementById("adminNewUserEmailInput");
  const newUserPasswordInput = document.getElementById("adminNewUserPasswordInput");
  const confirmUserPasswordInput = document.getElementById("adminConfirmUserPasswordInput");
  const createUserButton = document.getElementById("adminCreateUserButton");
  const createBackupButton = document.getElementById("adminCreateBackupButton");
  const cleanupBackupsButton = document.getElementById("adminCleanupBackupsButton");
  const maintenanceButton = document.getElementById("adminMaintenanceButton");
  const runtimeRetryButton = document.getElementById("adminRuntimeRetryButton");
  const profileAvatarButton = document.getElementById("adminProfileAvatarButton");
  const profileAvatarInput = document.getElementById("adminProfileAvatarInput");
  const profileDisplayNameInput = document.getElementById("adminProfileDisplayNameInput");
  const profileRoleInput = document.getElementById("adminProfileRoleInput");
  const profileTimezoneInput = document.getElementById("adminProfileTimezoneInput");
  const profileBioInput = document.getElementById("adminProfileBioInput");
  const profileNotificationsInput = document.getElementById("adminProfileNotificationsInput");
  const profileSaveButton = document.getElementById("adminProfileSaveButton");

  if (
    !(emailInput instanceof HTMLInputElement) ||
    !(passwordInput instanceof HTMLInputElement) ||
    !(titleInput instanceof HTMLInputElement) ||
    !(groupInput instanceof HTMLInputElement) ||
    !(tagsInput instanceof HTMLInputElement) ||
    !(sourceUrlInput instanceof HTMLInputElement) ||
    !(corePersonaInput instanceof HTMLInputElement) ||
    !(contentInput instanceof HTMLTextAreaElement) ||
    !(importInput instanceof HTMLInputElement) ||
    !(importGroupInput instanceof HTMLInputElement) ||
    !(importTagsInput instanceof HTMLInputElement) ||
    !(importButton instanceof HTMLButtonElement) ||
    !(urlInput instanceof HTMLInputElement) ||
    !(urlGroupInput instanceof HTMLInputElement) ||
    !(urlTagsInput instanceof HTMLInputElement) ||
    !(urlImportButton instanceof HTMLButtonElement) ||
    !(searchInput instanceof HTMLInputElement) ||
    !(loginButton instanceof HTMLButtonElement) ||
    !(logoutButton instanceof HTMLButtonElement) ||
    !(cancelEditButton instanceof HTMLButtonElement) ||
    !(saveButton instanceof HTMLButtonElement) ||
    !(currentPasswordInput instanceof HTMLInputElement) ||
    !(newPasswordInput instanceof HTMLInputElement) ||
    !(confirmPasswordInput instanceof HTMLInputElement) ||
    !(changePasswordButton instanceof HTMLButtonElement) ||
    !(newUserEmailInput instanceof HTMLInputElement) ||
    !(newUserPasswordInput instanceof HTMLInputElement) ||
    !(confirmUserPasswordInput instanceof HTMLInputElement) ||
    !(createUserButton instanceof HTMLButtonElement) ||
    !(createBackupButton instanceof HTMLButtonElement) ||
    !(cleanupBackupsButton instanceof HTMLButtonElement) ||
    !(maintenanceButton instanceof HTMLButtonElement) ||
    !(runtimeRetryButton instanceof HTMLButtonElement) ||
    !(profileAvatarButton instanceof HTMLButtonElement) ||
    !(profileAvatarInput instanceof HTMLInputElement) ||
    !(profileDisplayNameInput instanceof HTMLInputElement) ||
    !(profileRoleInput instanceof HTMLInputElement) ||
    !(profileTimezoneInput instanceof HTMLInputElement) ||
    !(profileBioInput instanceof HTMLTextAreaElement) ||
    !(profileNotificationsInput instanceof HTMLInputElement) ||
    !(profileSaveButton instanceof HTMLButtonElement)
  ) {
    return;
  }

  setText("adminBrowserStatus", "Browser ready");
  let token = window.localStorage.getItem(TOKEN_KEY) || "";
  let documentsCache = [];
  let editingDocumentId = null;
  let currentAdminEmail = "";
  let currentAdminProfile = null;
  let runtimePulseTimer = 0;
  let telemetryTimer = 0;
  let runtimePulseInFlight = false;

  function setAdminSessionState({ label, hint, status, pill, tone, composerLabel, composerTone }) {
    setText("adminSessionLabel", label);
    setText("adminSessionHint", hint);
    setText("adminLoginStatus", status);
    setStatusPill("adminSessionPill", pill, tone);
    setStatusPill("adminComposerState", composerLabel, composerTone);
    setStatusPill("adminAccessPill", token ? "Unlocked" : "Locked", token ? "ready" : "idle");
    logoutButton.disabled = !token;
    saveButton.disabled = !token;
    importButton.disabled = !token;
    urlImportButton.disabled = !token;
    changePasswordButton.disabled = !token;
    createUserButton.disabled = !token;
    createBackupButton.disabled = !token;
    cleanupBackupsButton.disabled = !token;
    maintenanceButton.disabled = !token;
    profileSaveButton.disabled = !token;
    profileAvatarButton.disabled = !token;
  }

  function setComposerMode({ heading, buttonLabel, stateLabel, stateTone, editing }) {
    setText("adminComposerHeading", heading);
    saveButton.textContent = buttonLabel;
    setStatusPill("adminComposerState", stateLabel, stateTone);
    setHidden("adminCancelEditButton", !editing);
  }

  function toneForRuntimePulse(status) {
    if (status === "live") {
      return "ready";
    }
    if (status === "degraded") {
      return "degraded";
    }
    if (status === "offline") {
      return "danger";
    }
    return "idle";
  }

  function renderRuntimePulse(pulse) {
    const status = String(pulse?.status || "offline");
    const statusLabel = String(pulse?.status_label || "Offline");
    const reason = String(pulse?.reason || "");
    setStatusPill("adminRuntimePulsePill", statusLabel, toneForRuntimePulse(status));
    setText("adminRuntimeSummary", reason || "Runtime pulse updated.");
    setText("adminSideProvider", String(pulse?.provider_label || "Unknown"));
    setText("adminSideReady", statusLabel);
    setText(
      "adminUptime",
      Number.isFinite(Number(pulse?.uptime_seconds)) ? formatDuration(Number(pulse.uptime_seconds)) : "Waiting"
    );
    setText("adminLastChecked", pulse?.checked_at ? formatTimestamp(pulse.checked_at) : "Waiting");
    setRuntimePulseAlert(status === "live" ? "" : reason, status);
  }

  function renderRuntimePulseFailure(error) {
    const detail = error instanceof Error ? error.message : "Runtime pulse check failed.";
    renderRuntimePulse({
      provider_label: "Unavailable",
      status: "offline",
      status_label: "Offline",
      reason: detail,
      checked_at: new Date().toISOString(),
      uptime_seconds: 0,
    });
  }

  async function loadRuntimePulse({ quiet = false } = {}) {
    if (runtimePulseInFlight) {
      return;
    }
    if (!token) {
      renderRuntimePulse({
        provider_label: "Protected",
        status: "offline",
        status_label: "Locked",
        reason: "Unlock the admin workspace to view runtime provider health.",
        checked_at: new Date().toISOString(),
        uptime_seconds: 0,
      });
      return;
    }
    runtimePulseInFlight = true;
    if (!quiet) {
      setStatusPill("adminRuntimePulsePill", "Checking", "idle");
      setText("adminSideReady", "Checking…");
      setText("adminRuntimeSummary", "Checking provider reachability from this server now.");
    }
    runtimeRetryButton.disabled = true;
    try {
      const pulse = await api("/admin/runtime-pulse", { token });
      renderRuntimePulse(pulse);
    } catch (error) {
      renderRuntimePulseFailure(error);
    } finally {
      runtimeRetryButton.disabled = false;
      runtimePulseInFlight = false;
    }
  }

  function startRuntimePulseLoop() {
    if (runtimePulseTimer) {
      window.clearInterval(runtimePulseTimer);
    }
    runtimePulseTimer = window.setInterval(() => {
      void loadRuntimePulse({ quiet: true });
    }, 30000);
  }

  function resetComposer() {
    editingDocumentId = null;
    titleInput.value = "";
    groupInput.value = "";
    tagsInput.value = "";
    sourceUrlInput.value = "";
    corePersonaInput.checked = false;
    contentInput.value = "";
    setComposerMode({
      heading: "Add knowledge",
      buttonLabel: "Save document",
      stateLabel: token ? "Ready to draft" : "Login required",
      stateTone: token ? "ready" : "idle",
      editing: false
    });
  }

  function startEditing(documentId) {
    const entry = documentsCache.find((item) => item.id === documentId);
    if (!entry) {
      return;
    }

    editingDocumentId = documentId;
    titleInput.value = entry.title || "";
    groupInput.value = entry.group_name || "";
    tagsInput.value = Array.isArray(entry.tags) ? entry.tags.join(", ") : "";
    sourceUrlInput.value = entry.source_url || "";
    corePersonaInput.checked = Boolean(entry.core_persona);
    contentInput.value = entry.content || "";
    setComposerMode({
      heading: "Edit knowledge",
      buttonLabel: "Update document",
      stateLabel: "Editing document",
      stateTone: "warning",
      editing: true
    });
    titleInput.focus();
    titleInput.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function bindDocumentActions() {
    document.querySelectorAll("[data-edit-document]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement) || button.dataset.boundEdit === "true") {
        return;
      }

      button.dataset.boundEdit = "true";
      button.addEventListener("click", () => {
        const documentId = Number(button.dataset.editDocument);
        if (Number.isFinite(documentId)) {
          startEditing(documentId);
        }
      });
    });

    document.querySelectorAll("[data-delete-document]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement) || button.dataset.boundDelete === "true") {
        return;
      }

      button.dataset.boundDelete = "true";
      button.addEventListener("click", async () => {
        if (!token) {
          showError("adminErrorText", "Login first to manage the knowledge base.");
          return;
        }

        const documentId = Number(button.dataset.deleteDocument);
        const entry = documentsCache.find((item) => item.id === documentId);
        if (!Number.isFinite(documentId) || !entry) {
          return;
        }

        const confirmed = window.confirm(`Delete "${entry.title}" from the knowledge base?`);
        if (!confirmed) {
          return;
        }

        button.disabled = true;
        setText("adminLoginStatus", "Deleting document...");
        try {
          await api(`/admin/documents/${documentId}`, {
            method: "DELETE",
            token
          });
          if (editingDocumentId === documentId) {
            resetComposer();
          }
          await refresh();
          setText("adminLoginStatus", "Document deleted.");
        } catch (error) {
          showError("adminErrorText", error instanceof Error ? error.message : "Delete failed.");
          setText("adminLoginStatus", "Delete failed.");
        } finally {
          button.disabled = false;
        }
      });
    });

    document.querySelectorAll("[data-toggle-core-persona]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement) || button.dataset.boundCorePersona === "true") {
        return;
      }

      button.dataset.boundCorePersona = "true";
      button.addEventListener("click", async () => {
        if (!token) {
          showError("adminErrorText", "Login first to manage core persona documents.");
          return;
        }

        const documentId = Number(button.dataset.toggleCorePersona);
        const entry = documentsCache.find((item) => item.id === documentId);
        if (!Number.isFinite(documentId) || !entry) {
          return;
        }

        button.disabled = true;
        setText("adminLoginStatus", entry.core_persona ? "Removing core persona priority..." : "Marking core persona priority...");
        try {
          await api(`/admin/documents/${documentId}/core-persona`, {
            method: "POST",
            token,
            body: {
              core_persona: !entry.core_persona
            }
          });
          await refresh();
          setText("adminLoginStatus", !entry.core_persona ? "Document marked as a core persona source." : "Core persona priority removed.");
        } catch (error) {
          showError("adminErrorText", error instanceof Error ? error.message : "Could not update core persona priority.");
          setText("adminLoginStatus", "Core persona update failed.");
        } finally {
          button.disabled = false;
        }
      });
    });
  }

  function bindSourceActions() {
    const actionConfigs = [
      { selector: "[data-source-enable]", path: "enable", message: "Source enabled." },
      { selector: "[data-source-disable]", path: "disable", message: "Source disabled." },
      { selector: "[data-source-reindex]", path: "reindex", message: "Source reindexed." },
      { selector: "[data-source-sync]", path: "sync", message: "Source synced." }
    ];

    actionConfigs.forEach(({ selector, path, message }) => {
      document.querySelectorAll(selector).forEach((button) => {
        if (!(button instanceof HTMLButtonElement) || button.dataset.boundSourceAction === "true") {
          return;
        }
        button.dataset.boundSourceAction = "true";
        button.addEventListener("click", async () => {
          if (!token) {
            showError("adminErrorText", "Login first to manage sources.");
            return;
          }
          const encodedSourceKey =
            button.dataset.sourceEnable ||
            button.dataset.sourceDisable ||
            button.dataset.sourceReindex ||
            button.dataset.sourceSync;
          if (!encodedSourceKey) {
            return;
          }
          button.disabled = true;
          setText("adminMaintenanceSummary", `Running ${path}...`);
          try {
            await api(`/admin/sources/${encodedSourceKey}/${path}`, {
              method: "POST",
              token
            });
            await refresh();
            setText("adminMaintenanceSummary", message);
            setText("adminLoginStatus", message);
          } catch (error) {
            showError("adminErrorText", error instanceof Error ? error.message : `Source ${path} failed.`);
            setText("adminMaintenanceSummary", `${path} failed`);
          } finally {
            button.disabled = false;
          }
        });
      });
    });
  }

  function bindBackupActions() {
    document.querySelectorAll("[data-backup-download]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement) || button.dataset.boundBackupDownload === "true") {
        return;
      }
      button.dataset.boundBackupDownload = "true";
      button.addEventListener("click", async () => {
        if (!token) {
          showError("adminErrorText", "Login first to download backups.");
          return;
        }
        const backupId = button.dataset.backupDownload;
        if (!backupId) {
          return;
        }
        button.disabled = true;
        try {
          await downloadFile(`/admin/backups/${backupId}/download`, token, `hajihaz-backup-${backupId}.zip`);
          setText("adminBackupStatus", "Backup download started.");
        } catch (error) {
          showError("adminErrorText", error instanceof Error ? error.message : "Backup download failed.");
        } finally {
          button.disabled = false;
        }
      });
    });
  }

  function renderLibrary() {
    renderDocuments(documentsCache);
    bindDocumentActions();
  }

  function clearSession(message) {
    token = "";
    currentAdminEmail = "";
    window.localStorage.removeItem(TOKEN_KEY);
    passwordInput.value = "";
    searchInput.value = "";
    importInput.value = "";
    importGroupInput.value = "";
    importTagsInput.value = "";
    urlInput.value = "";
    urlGroupInput.value = "";
    urlTagsInput.value = "";
    currentPasswordInput.value = "";
    newPasswordInput.value = "";
    confirmPasswordInput.value = "";
    newUserEmailInput.value = "";
    newUserPasswordInput.value = "";
    confirmUserPasswordInput.value = "";
    profileAvatarInput.value = "";
    profileDisplayNameInput.value = "";
    profileRoleInput.value = "";
    profileTimezoneInput.value = "";
    profileBioInput.value = "";
    profileNotificationsInput.checked = false;
    currentAdminProfile = null;
    setText("adminImportStatus", "No files selected.");
    setText("adminUrlImportStatus", "No page imported yet.");
    documentsCache = [];
    renderLockedState();
    resetComposer();
    setAdminSessionState({
      label: "Guest mode",
      hint: "Login to manage the library.",
      status: message,
      pill: "Offline",
      tone: "idle",
      composerLabel: "Login required",
      composerTone: "idle"
    });
    showError("adminErrorText", "");
    void loadRuntimePulse({ quiet: false });
  }

  async function refresh() {
    if (!token) {
      currentAdminEmail = "";
      documentsCache = [];
      renderLockedState();
      void loadRuntimePulse({ quiet: false });
      return { me: null, users: [] };
    }

    const [documents, stats, debug, me, users] = await Promise.all([
      api("/admin/documents", { token }),
      api("/admin/stats", { token }),
      api("/admin/debug", { token }),
      api("/auth/me", { token }),
      api("/admin/admin-users", { token })
    ]);
    documentsCache = Array.isArray(documents) ? documents : [];
    currentAdminEmail = me?.email || "";
    currentAdminProfile = me || null;
    renderAdminProfile(currentAdminProfile);
    renderLibrary();
    renderStats(stats);
    renderDebugSnapshot(debug);
    renderAdminUsers(users, currentAdminEmail);
    bindSourceActions();
    bindBackupActions();
    setAdminGatedVisible(true);
    void loadRuntimePulse({ quiet: true });
    return { me, users };
  }

  async function refreshTelemetry() {
    if (!token) {
      return;
    }
    try {
      const [stats, debug] = await Promise.all([
        api("/admin/stats", { token }),
        api("/admin/debug", { token })
      ]);
      renderStats(stats);
      renderDebugSnapshot(debug);
      bindSourceActions();
      bindBackupActions();
    } catch {
      setText("adminAnalyticsSummary", "Refresh paused");
    }
  }

  function startTelemetryLoop() {
    if (telemetryTimer) {
      window.clearInterval(telemetryTimer);
    }
    telemetryTimer = window.setInterval(() => {
      void refreshTelemetry();
    }, 45000);
  }

  renderLockedState();
  resetComposer();
  setAdminSessionState({
    label: "Guest mode",
    hint: "Login to manage the library.",
    status: "Not authenticated",
    pill: "Offline",
    tone: "idle",
    composerLabel: "Login required",
    composerTone: "idle"
  });
  runtimeRetryButton.addEventListener("click", () => {
    void loadRuntimePulse({ quiet: false });
  });
  profileAvatarButton.addEventListener("click", () => {
    if (!token) {
      showError("adminErrorText", "Login first to update your profile avatar.");
      return;
    }
    profileAvatarInput.click();
  });
  profileAvatarInput.addEventListener("change", async () => {
    const file = profileAvatarInput.files && profileAvatarInput.files[0];
    if (!file) {
      return;
    }
    if (!token) {
      showError("adminErrorText", "Login first to update your profile avatar.");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    profileAvatarButton.disabled = true;
    setText("adminProfileStatus", "Uploading avatar...");
    showError("adminErrorText", "");
    try {
      const profile = await api("/auth/avatar", {
        method: "POST",
        token,
        formData,
        timeoutMs: LONG_REQUEST_TIMEOUT_MS
      });
      currentAdminProfile = profile;
      renderAdminProfile(profile);
      setText("adminLoginStatus", "Profile avatar updated.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Avatar upload failed.");
      setText("adminProfileStatus", "Avatar upload failed.");
    } finally {
      profileAvatarInput.value = "";
      profileAvatarButton.disabled = !token;
    }
  });
  profileSaveButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to update your profile.");
      return;
    }
    profileSaveButton.disabled = true;
    showError("adminErrorText", "");
    setText("adminProfileStatus", "Saving profile...");
    try {
      const profile = await api("/auth/profile", {
        method: "PATCH",
        token,
        body: {
          display_name: profileDisplayNameInput.value.trim(),
          role_title: profileRoleInput.value.trim(),
          timezone: profileTimezoneInput.value.trim(),
          bio: profileBioInput.value.trim(),
          notifications_enabled: profileNotificationsInput.checked
        }
      });
      currentAdminProfile = profile;
      renderAdminProfile(profile);
      renderAdminUsers(await api("/admin/admin-users", { token }), profile.email);
      setText("adminLoginStatus", "Admin profile updated.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Profile update failed.");
      setText("adminProfileStatus", "Profile update failed.");
    } finally {
      profileSaveButton.disabled = !token;
    }
  });
  void loadRuntimePulse({ quiet: false });
  startRuntimePulseLoop();
  startTelemetryLoop();

  loginButton.addEventListener("click", async () => {
    showError("adminErrorText", "");
    loginButton.disabled = true;
    setAdminSessionState({
      label: "Signing in",
      hint: "Checking local admin credentials.",
      status: "Signing in...",
      pill: "Authorizing",
      tone: "warning",
      composerLabel: "Waiting for access",
      composerTone: "idle"
    });

    try {
      const response = await api("/auth/login", {
        method: "POST",
        body: {
          email: emailInput.value,
          password: passwordInput.value
        }
      });
      token = response.token;
      window.localStorage.setItem(TOKEN_KEY, token);
      passwordInput.value = "";
      const { me } = await refresh();
      setAdminSessionState({
        label: "Workspace unlocked",
        hint: me?.email || response.email,
        status: `Authenticated as ${me?.email || response.email}`,
        pill: "Unlocked",
        tone: "ready",
        composerLabel: "Ready to save",
        composerTone: "ready"
      });
      resetComposer();
    } catch (error) {
      clearSession(error instanceof Error ? error.message : "Login failed.");
      setStatusPill("adminSessionPill", "Access denied", "warning");
      setText("adminSessionLabel", "Login failed");
      setText("adminSessionHint", "Check the admin password and try again.");
      setStatusPill("adminComposerState", "Blocked", "warning");
    } finally {
      loginButton.disabled = false;
    }
  });

  logoutButton.addEventListener("click", () => {
    const activeToken = token;
    void (async () => {
      if (activeToken) {
        try {
          await api("/auth/logout", {
            method: "POST",
            token: activeToken
          });
        } catch {
          // Even if remote logout fails, local session should still be cleared.
        }
      }
      clearSession("Session cleared.");
    })();
  });

  cancelEditButton.addEventListener("click", () => {
    resetComposer();
    setText("adminLoginStatus", token ? "Edit cancelled." : "Not authenticated");
    showError("adminErrorText", "");
  });

  searchInput.addEventListener("input", () => {
    renderLibrary();
  });

  importInput.addEventListener("change", () => {
    const count = importInput.files ? importInput.files.length : 0;
    setText("adminImportStatus", count ? `${count} file${count === 1 ? "" : "s"} selected.` : "No files selected.");
  });

  changePasswordButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to change your password.");
      return;
    }
    if (!currentPasswordInput.value || !newPasswordInput.value || !confirmPasswordInput.value) {
      showError("adminErrorText", "Fill in all password fields first.");
      return;
    }
    if (newPasswordInput.value !== confirmPasswordInput.value) {
      showError("adminErrorText", "New password confirmation does not match.");
      return;
    }
    if (newPasswordInput.value.length < 8) {
      showError("adminErrorText", "Use at least 8 characters for the new password.");
      return;
    }

    showError("adminErrorText", "");
    changePasswordButton.disabled = true;
    setText("adminPasswordStatus", "Updating...");
    setText("adminLoginStatus", "Updating password...");

    try {
      const response = await api("/auth/change-password", {
        method: "POST",
        token,
        body: {
          current_password: currentPasswordInput.value,
          new_password: newPasswordInput.value
        }
      });
      currentPasswordInput.value = "";
      newPasswordInput.value = "";
      confirmPasswordInput.value = "";
      setText("adminPasswordStatus", "Password updated");
      setText("adminLoginStatus", `Password updated for ${response.email}.`);
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Password update failed.");
      setText("adminPasswordStatus", "Update failed");
      setText("adminLoginStatus", "Password update failed.");
    } finally {
      changePasswordButton.disabled = !token;
    }
  });

  createUserButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to add another admin.");
      return;
    }
    if (!newUserEmailInput.value.trim() || !newUserPasswordInput.value || !confirmUserPasswordInput.value) {
      showError("adminErrorText", "Fill in the new admin email and password.");
      return;
    }
    if (newUserPasswordInput.value !== confirmUserPasswordInput.value) {
      showError("adminErrorText", "New admin password confirmation does not match.");
      return;
    }
    if (newUserPasswordInput.value.length < 8) {
      showError("adminErrorText", "Use at least 8 characters for the new admin password.");
      return;
    }

    showError("adminErrorText", "");
    createUserButton.disabled = true;
    setText("adminCreateUserStatus", "Creating...");
    setText("adminLoginStatus", "Adding another admin...");

    try {
      const response = await api("/admin/admin-users", {
        method: "POST",
        token,
        body: {
          email: newUserEmailInput.value.trim(),
          password: newUserPasswordInput.value
        }
      });
      newUserEmailInput.value = "";
      newUserPasswordInput.value = "";
      confirmUserPasswordInput.value = "";
      await refresh();
      setText("adminCreateUserStatus", "Admin added");
      setText("adminLoginStatus", `${response.email} can now log in as an admin.`);
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Could not add the new admin.");
      setText("adminCreateUserStatus", "Add failed");
      setText("adminLoginStatus", "Admin creation failed.");
    } finally {
      createUserButton.disabled = !token;
    }
  });

  createBackupButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to create a backup.");
      return;
    }

    showError("adminErrorText", "");
    createBackupButton.disabled = true;
    setText("adminBackupStatus", "Creating backup archive...");
    try {
      const response = await api("/admin/backups/create", {
        method: "POST",
        token,
        body: {
          note: "Manual backup from admin workspace"
        }
      });
      await refresh();
      setText("adminBackupStatus", `Backup ready: ${response.archive_name}`);
      setText("adminLoginStatus", "Backup created.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Backup creation failed.");
      setText("adminBackupStatus", "Backup creation failed.");
    } finally {
      createBackupButton.disabled = !token;
    }
  });

  cleanupBackupsButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to clean old backups.");
      return;
    }

    showError("adminErrorText", "");
    cleanupBackupsButton.disabled = true;
    setText("adminBackupStatus", "Cleaning old backups...");
    try {
      const response = await api("/admin/backups/cleanup", {
        method: "POST",
        token
      });
      await refresh();
      setText("adminBackupStatus", response.removed.length ? `Removed ${response.removed.length} old backup(s).` : "No old backups needed cleanup.");
      setText("adminLoginStatus", "Backup cleanup finished.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Backup cleanup failed.");
      setText("adminBackupStatus", "Backup cleanup failed.");
    } finally {
      cleanupBackupsButton.disabled = !token;
    }
  });

  maintenanceButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to run maintenance.");
      return;
    }

    showError("adminErrorText", "");
    maintenanceButton.disabled = true;
    setText("adminMaintenanceSummary", "Running maintenance...");
    try {
      const response = await api("/admin/maintenance", {
        method: "POST",
        token
      });
      renderDebugCards("adminMaintenanceList", [response], (item) => `
        <article class="debug-card">
          <div class="document-meta-row">
            <strong>Maintenance completed</strong>
            <span>${escapeHtml(formatTimestamp(new Date().toISOString()))}</span>
          </div>
          <p>Pruned: ${escapeHtml(JSON.stringify(item.pruned || {}))}</p>
          <div class="document-meta-row">
            <span>Removed backups: ${Array.isArray(item.removed_backups) ? item.removed_backups.length : 0}</span>
            <span>Disk ${Number(item.metrics?.disk_percent || 0).toFixed(1)}%</span>
          </div>
        </article>
      `);
      await refresh();
      setText("adminMaintenanceSummary", "Maintenance completed");
      setText("adminLoginStatus", "Maintenance run completed.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Maintenance failed.");
      setText("adminMaintenanceSummary", "Maintenance failed");
    } finally {
      maintenanceButton.disabled = !token;
    }
  });

  importButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to import documents.");
      return;
    }

    const files = Array.from(importInput.files || []);
    if (!files.length) {
      showError("adminErrorText", "Choose one or more files to import.");
      return;
    }

    showError("adminErrorText", "");
    importButton.disabled = true;
    urlImportButton.disabled = true;
    setText("adminLoginStatus", "Importing files...");
    setText("adminImportStatus", "Parsing selected files...");
    setStatusPill("adminComposerState", "Importing", "warning");

    try {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      formData.append("group_name", importGroupInput.value.trim());
      formData.append("tags_csv", importTagsInput.value.trim());
      formData.append("skip_duplicates", "true");

      const response = await api("/admin/documents/import/files", {
        method: "POST",
        token,
        formData,
        timeoutMs: LONG_REQUEST_TIMEOUT_MS
      });
      importInput.value = "";
      importGroupInput.value = "";
      importTagsInput.value = "";
      setText(
        "adminImportStatus",
        `Imported ${response.imported} document${response.imported === 1 ? "" : "s"} with ${response.skipped} duplicate skip${response.skipped === 1 ? "" : "s"}.`
      );
      await refresh();
      setStatusPill("adminComposerState", "Imported", "ready");
      setText("adminLoginStatus", "Bulk import finished.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Bulk import failed.");
      setText("adminImportStatus", "Import failed. Check the selected files and try again.");
      setStatusPill("adminComposerState", "Import failed", "warning");
      setText("adminLoginStatus", "Bulk import failed.");
    } finally {
      importButton.disabled = !token;
      urlImportButton.disabled = !token;
    }
  });

  urlImportButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to import a page.");
      return;
    }

    if (!urlInput.value.trim()) {
      showError("adminErrorText", "Enter a website or page URL to import.");
      return;
    }

    showError("adminErrorText", "");
    urlImportButton.disabled = true;
    importButton.disabled = true;
    setText("adminUrlImportStatus", "Fetching page content...");
    setText("adminLoginStatus", "Importing page...");
    setStatusPill("adminComposerState", "Fetching page", "warning");

    try {
      const response = await api("/admin/documents/import/url", {
        method: "POST",
        token,
        timeoutMs: LONG_REQUEST_TIMEOUT_MS,
        body: {
          url: urlInput.value.trim(),
          group_name: urlGroupInput.value.trim(),
          tags: urlTagsInput.value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean)
        }
      });
      urlInput.value = "";
      urlGroupInput.value = "";
      urlTagsInput.value = "";
      setText(
        "adminUrlImportStatus",
        response.imported
          ? response.imported === 1
            ? `Imported ${response.documents[0]?.title || "page"} into the library.`
            : `Imported ${response.imported} documents from that source.`
          : "This page was already in the library, so it was skipped."
      );
      await refresh();
      setStatusPill("adminComposerState", "Page imported", "ready");
      setText("adminLoginStatus", "Website import finished.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Website import failed.");
      setText("adminUrlImportStatus", "Website import failed. Check the URL and try again.");
      setStatusPill("adminComposerState", "Import failed", "warning");
      setText("adminLoginStatus", "Website import failed.");
    } finally {
      urlImportButton.disabled = !token;
      importButton.disabled = !token;
    }
  });

  saveButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to manage the knowledge base.");
      setStatusPill("adminComposerState", "Login required", "warning");
      return;
    }

    showError("adminErrorText", "");
    saveButton.disabled = true;
    setStatusPill("adminComposerState", editingDocumentId ? "Updating now" : "Saving now", "warning");
    setText("adminLoginStatus", editingDocumentId ? "Updating document..." : "Saving document...");

    try {
      const wasEditing = editingDocumentId !== null;
      const sourceForUpdate =
        wasEditing
          ? documentsCache.find((item) => item.id === editingDocumentId)?.source || "admin"
          : "admin";
      await api(wasEditing ? `/admin/documents/${editingDocumentId}` : "/admin/documents", {
        method: wasEditing ? "PUT" : "POST",
        token,
        body: {
          title: titleInput.value,
          content: contentInput.value,
          tags: tagsInput.value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
          source: sourceForUpdate,
          group_name: groupInput.value.trim(),
          core_persona: corePersonaInput.checked,
          source_url: sourceUrlInput.value.trim() || null
        }
      });
      await refresh();
      resetComposer();
      setStatusPill("adminComposerState", wasEditing ? "Updated" : "Saved", "ready");
      setText("adminLoginStatus", wasEditing ? "Document updated." : "Knowledge base updated.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Document request failed.");
      setStatusPill("adminComposerState", editingDocumentId !== null ? "Update failed" : "Save failed", "warning");
      setText("adminLoginStatus", editingDocumentId !== null ? "Update failed." : "Save failed.");
    } finally {
      saveButton.disabled = !token;
    }
  });

  if (token) {
    setAdminSessionState({
      label: "Restoring session",
      hint: "Loading your admin workspace.",
      status: "Existing session found. Loading workspace...",
      pill: "Restoring",
      tone: "warning",
      composerLabel: "Loading",
      composerTone: "idle"
    });
    void refresh()
      .then(({ me }) => {
        setAdminSessionState({
          label: "Workspace unlocked",
          hint: me?.email || "Session restored from this browser.",
          status: me?.email ? `Authenticated as ${me.email}` : "Authenticated from local session.",
          pill: "Unlocked",
          tone: "ready",
          composerLabel: "Ready to save",
          composerTone: "ready"
        });
        resetComposer();
      })
      .catch(() => {
        clearSession("Stored session expired. Login again.");
      });
  }

  document.querySelectorAll("[data-export-format]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }

    button.addEventListener("click", async () => {
      if (!token) {
        showError("adminErrorText", "Login first to export the library.");
        return;
      }

      const format = button.dataset.exportFormat || "json";
      button.disabled = true;
      try {
        await downloadFile(
          `/admin/documents/export?export_format=${encodeURIComponent(format)}`,
          token,
          `hajihaz-library.${format === "markdown" ? "md" : format}`
        );
        setText("adminLoginStatus", `Library exported as ${format.toUpperCase()}.`);
      } catch (error) {
        showError("adminErrorText", error instanceof Error ? error.message : "Export failed.");
      } finally {
        button.disabled = false;
      }
    });
  });
}

window.addEventListener("load", () => {
  initChatPage();
  initAdminPage();
});
