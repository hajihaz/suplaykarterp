(() => {
  "use strict";

  const STORAGE_KEY = "hajihaz-ui-state-v2";
  const LEGACY_STORAGE_KEY = "hajihaz-ui-state-v1";
  const AUTH_TOKEN_KEY = "hajihaz-user-token";
  const PROFILE_STORAGE_KEY = "hajihaz-profile-settings-v1";
  const MAX_HISTORY_TURNS = 12;
  const REQUEST_TIMEOUT_MS = 90000;
  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

  const els = {
    form: document.getElementById("chatForm"),
    input: document.getElementById("chatInput"),
    send: document.getElementById("sendButton"),
    clear: document.getElementById("clearThreadButton"),
    mode: document.getElementById("answerMode"),
    messages: document.getElementById("messageList"),
    welcome: document.getElementById("welcomePanel"),
    starters: document.getElementById("starterPrompts"),
    list: document.getElementById("conversationList"),
    search: document.getElementById("conversationSearch"),
    newChat: document.getElementById("newChatButton"),
    title: document.getElementById("conversationTitle"),
    subtitle: document.getElementById("conversationSubtitle"),
    status: document.getElementById("connectionStatus"),
    error: document.getElementById("chatError"),
    sidebar: document.getElementById("appSidebar"),
    sidebarToggle: document.getElementById("sidebarToggleButton"),
    sidebarClose: document.getElementById("closeSidebarButton"),
    sidebarBackdrop: document.getElementById("sidebarBackdrop"),
    settingsButton: document.getElementById("settingsButton"),
    settingsPanel: document.getElementById("settingsPanel"),
    themeToggle: document.getElementById("themeToggleButton"),
    themeLabel: document.getElementById("themeLabel"),
    themeSwitch: document.getElementById("themeSwitch"),
    memoryToggle: document.getElementById("memoryToggle"),
    aiMode: document.getElementById("aiMode"),
    exportChat: document.getElementById("exportChatButton"),
    settingsClear: document.getElementById("settingsClearButton"),
    sidebarName: document.getElementById("sidebarName"),
    sidebarPlan: document.getElementById("sidebarPlan"),
    sidebarAvatar: document.getElementById("sidebarAvatar"),
    profileName: document.getElementById("profileName"),
    profileUsername: document.getElementById("profileUsername"),
    profileBio: document.getElementById("profileBio"),
    profileAiNickname: document.getElementById("profileAiNickname"),
    profilePersonality: document.getElementById("profilePersonality"),
    profileAvatarButton: document.getElementById("profileAvatarButton"),
    profileAvatarPreview: document.getElementById("profileAvatarPreview"),
    profileAvatarUpload: document.getElementById("profileAvatarUpload"),
    profileSyncStatus: document.getElementById("profileSyncStatus"),
  };

  const nowIso = () => new Date().toISOString();

  function makeId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  function defaultState() {
    const first = {
      id: makeId(),
      title: "New conversation",
      sessionId: null,
      createdAt: nowIso(),
      updatedAt: nowIso(),
      messages: [],
    };
    return {
      answerMode: "balanced",
      aiMode: "auto",
      memoryEnabled: true,
      theme: "dark",
      profile: defaultProfile(),
      activeId: first.id,
      conversations: [first],
    };
  }

  function defaultProfile() {
    return {
      name: "Haji H.",
      username: "",
      bio: "",
      picture_url: "",
      ai_nickname: "HajiHaz AI",
      personality: "balanced",
      authenticated: false,
    };
  }

  function safeParse(raw) {
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function normalizeMode(mode) {
    return ["balanced", "concise", "detailed", "strategic", "founder"].includes(mode) ? mode : "balanced";
  }

  function normalizeAiMode(mode) {
    return ["auto", "general", "memory", "reasoning", "coding", "creative"].includes(mode) ? mode : "auto";
  }

  function normalizeTheme(theme) {
    return ["dark", "light", "system"].includes(theme) ? theme : "dark";
  }

  function normalizePersonality(personality) {
    return ["balanced", "direct", "warm", "strategic", "creative"].includes(personality) ? personality : "balanced";
  }

  function cleanProfileText(value, fallback = "") {
    return String(value || fallback).replace(/\s+/g, " ").trim();
  }

  function normalizeProfile(profile) {
    const base = { ...defaultProfile(), ...(profile || {}) };
    return {
      ...base,
      name: cleanProfileText(base.name, "Haji H.").slice(0, 80),
      username: String(base.username || "").toLowerCase().replace(/[^a-z0-9._-]+/g, "").slice(0, 40),
      bio: cleanProfileText(base.bio).slice(0, 500),
      picture_url: String(base.picture_url || ""),
      ai_nickname: cleanProfileText(base.ai_nickname, "HajiHaz AI").slice(0, 80),
      personality: normalizePersonality(base.personality),
      authenticated: Boolean(base.authenticated),
    };
  }

  function normalizeState(parsed) {
    if (!parsed || !Array.isArray(parsed.conversations) || !parsed.conversations.length) {
      return defaultState();
    }
    parsed.conversations = parsed.conversations.map((conversation) => ({
      id: String(conversation.id || makeId()),
      title: String(conversation.title || "New conversation"),
      sessionId: conversation.sessionId || null,
      createdAt: conversation.createdAt || nowIso(),
      updatedAt: conversation.updatedAt || nowIso(),
      messages: Array.isArray(conversation.messages) ? conversation.messages : [],
    }));
    if (!parsed.activeId || !parsed.conversations.some((item) => item.id === parsed.activeId)) {
      parsed.activeId = parsed.conversations[0].id;
    }
    parsed.answerMode = normalizeMode(parsed.answerMode);
    parsed.aiMode = normalizeAiMode(parsed.aiMode);
    parsed.memoryEnabled = parsed.memoryEnabled !== false;
    parsed.theme = normalizeTheme(parsed.theme);
    parsed.profile = normalizeProfile(parsed.profile || safeParse(window.localStorage.getItem(PROFILE_STORAGE_KEY) || ""));
    return parsed;
  }

  function loadState() {
    return normalizeState(
      safeParse(window.localStorage.getItem(STORAGE_KEY) || "") ||
        safeParse(window.localStorage.getItem(LEGACY_STORAGE_KEY) || "")
    );
  }

  let state = loadState();

  function applyTheme() {
    const preferred = normalizeTheme(state.theme);
    const theme =
      preferred === "system" && window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : preferred === "system"
          ? "dark"
          : preferred;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.themePreference = preferred;
    document.documentElement.style.colorScheme = theme;
    const meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) meta.setAttribute("content", theme === "light" ? "light dark" : "dark light");
  }

  function saveState() {
    const trimmed = {
      ...state,
      profile: normalizeProfile(state.profile),
      conversations: state.conversations.slice(0, 40).map((conversation) => ({
        ...conversation,
        messages: conversation.messages.slice(-90),
      })),
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(trimmed.profile));
  }

  function activeConversation() {
    let conversation = state.conversations.find((item) => item.id === state.activeId);
    if (!conversation) {
      conversation = defaultState().conversations[0];
      state.conversations.unshift(conversation);
      state.activeId = conversation.id;
    }
    return conversation;
  }

  function createEl(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function createIcon(name) {
    const paths = {
      copy: ["M8 8h10v10H8z", "M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"],
      source: ["M7 17 17 7", "M9 7h8v8"],
      chat: ["M7 8h10M7 12h6", "M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-8l-5 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"],
    };
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    for (const d of paths[name] || paths.chat) {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  }

  function setStatus(label, stateName = "ready") {
    els.status.textContent = label;
    els.status.dataset.state = stateName;
  }

  function setError(message = "") {
    els.error.textContent = message;
    els.error.hidden = !message;
  }

  function formatTime(iso) {
    try {
      return new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
      }).format(new Date(iso));
    } catch {
      return "";
    }
  }

  function dayKey(iso) {
    const date = new Date(iso);
    const today = new Date();
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diffDays = Math.round((start - target) / 86400000);
    if (diffDays <= 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return "Last 7 days";
    return "Older";
  }

  function titleFromMessage(message) {
    const compact = message.replace(/\s+/g, " ").trim();
    if (!compact) return "New conversation";
    return compact.length > 56 ? `${compact.slice(0, 53)}...` : compact;
  }

  function openSidebar() {
    document.body.classList.add("is-sidebar-open");
  }

  function closeSidebar() {
    document.body.classList.remove("is-sidebar-open");
    closeSettings();
  }

  function openSettings() {
    els.settingsPanel.hidden = false;
    els.settingsButton.setAttribute("aria-expanded", "true");
    document.body.classList.add("is-settings-open");
  }

  function closeSettings() {
    els.settingsPanel.hidden = true;
    els.settingsButton.setAttribute("aria-expanded", "false");
    document.body.classList.remove("is-settings-open");
  }

  function toggleSettings() {
    if (els.settingsPanel.hidden) {
      openSettings();
    } else {
      closeSettings();
    }
  }

  function renderConversationList() {
    const query = (els.search.value || "").trim().toLowerCase();
    const conversations = state.conversations
      .filter((conversation) => conversation.title.toLowerCase().includes(query))
      .sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));

    els.list.replaceChildren();
    if (!conversations.length) {
      els.list.append(createEl("p", "hh-empty-list", "No matching conversations yet."));
      return;
    }

    let currentGroup = "";
    for (const conversation of conversations) {
      const group = dayKey(conversation.updatedAt || conversation.createdAt);
      if (group !== currentGroup) {
        currentGroup = group;
        els.list.append(createEl("div", "hh-conversation-group", group));
      }

      const button = createEl("button", "hh-conversation");
      button.type = "button";
      button.classList.toggle("is-active", conversation.id === state.activeId);
      button.dataset.id = conversation.id;
      button.append(createEl("strong", "", conversation.title));
      button.append(createEl("small", "", formatTime(conversation.updatedAt)));
      button.addEventListener("click", () => {
        state.activeId = conversation.id;
        saveState();
        render();
        closeSidebar();
      });
      els.list.append(button);
    }
  }

  function renderCitations(parent, citations) {
    if (!Array.isArray(citations) || !citations.length) return;
    const wrap = createEl("div", "hh-citations");
    for (const citation of citations.slice(0, 4)) {
      const card = createEl("article", "hh-citation");
      const head = createEl("div", "hh-citation-head");
      head.append(createEl("strong", "", citation.title || "Source"));
      head.append(createEl("span", "hh-source-kind", citation.kind || citation.source || "source"));
      card.append(head);
      if (citation.excerpt) {
        card.append(createEl("p", "", citation.excerpt));
      }
      if (citation.url) {
        const link = createEl("a", "hh-source-link");
        link.href = citation.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.append(createIcon("source"), createEl("span", "", "Open source"));
        card.append(link);
      }
      wrap.append(card);
    }
    parent.append(wrap);
  }

  function displayMode(message) {
    if (message.role === "user") return formatTime(message.createdAt);
    const strategy = message.sourceStrategy || "";
    if (strategy === "web") return "web";
    if (strategy === "reasoning") return "reasoning";
    if (strategy === "memory" || strategy === "hybrid") return "knowledge";
    if (strategy === "general") return "answer";
    return message.mode || "answer";
  }

  function renderMessage(message) {
    const article = createEl("article", `hh-message is-${message.role}`);
    const bubble = createEl("div", "hh-bubble");
    const meta = createEl("div", "hh-message-meta");
    meta.append(createEl("strong", "", message.role === "user" ? "You" : "HajiHaz AI"));
    meta.append(createEl("span", "", displayMode(message)));

    const copy = createEl("div", "hh-answer");
    copy.textContent = message.content || "";
    bubble.append(meta, copy);

    if (message.notice) {
      bubble.append(createEl("div", "hh-notice", message.notice));
    }
    renderCitations(bubble, message.citations);

    if (message.role === "assistant" && message.content && !message.pending) {
      const actions = createEl("div", "hh-actions");
      const copyButton = createEl("button", "hh-copy");
      copyButton.type = "button";
      copyButton.append(createIcon("copy"), createEl("span", "", "Copy"));
      copyButton.addEventListener("click", async () => {
        try {
          await window.navigator.clipboard.writeText(message.content);
          copyButton.querySelector("span").textContent = "Copied";
          window.setTimeout(() => {
            copyButton.querySelector("span").textContent = "Copy";
          }, 1200);
        } catch {
          copyButton.querySelector("span").textContent = "Copy failed";
        }
      });
      actions.append(copyButton);
      bubble.append(actions);
    }

    article.append(bubble);
    return article;
  }

  function renderMessages() {
    const conversation = activeConversation();
    const hasMessages = conversation.messages.length > 0;
    els.messages.replaceChildren();
    els.welcome.classList.toggle("is-hidden", hasMessages);
    els.messages.hidden = !hasMessages;
    for (const message of conversation.messages) {
      els.messages.append(renderMessage(message));
    }
  }

  function renderHeader() {
    const conversation = activeConversation();
    const count = conversation.messages.filter((message) => !message.pending).length;
    els.title.textContent = conversation.title || "New conversation";
    const memoryLabel = state.memoryEnabled ? "Memory guarded" : "Memory off";
    const modeLabel = state.aiMode === "auto" ? "Auto routing" : `${state.aiMode[0].toUpperCase()}${state.aiMode.slice(1)} mode`;
    els.subtitle.textContent = count > 0 ? `${count} messages · ${modeLabel}` : `${modeLabel} · ${memoryLabel}`;
    els.mode.value = state.answerMode;
  }

  function renderSettings() {
    const themeLabel = state.theme === "system" ? "System" : state.theme === "light" ? "Light" : "Dark";
    els.themeLabel.textContent = themeLabel;
    els.themeSwitch.classList.toggle("is-on", state.theme === "light");
    els.themeToggle.setAttribute("aria-pressed", String(state.theme === "light"));
    els.memoryToggle.checked = state.memoryEnabled;
    els.aiMode.value = state.aiMode;
  }

  function initialsFromName(name) {
    const parts = cleanProfileText(name, "HH").split(" ").filter(Boolean);
    return (parts[0]?.[0] || "H") + (parts[1]?.[0] || parts[0]?.[1] || "H");
  }

  function paintAvatar(element, imageUrl, initials) {
    if (!element) return;
    const label = element.querySelector ? element.querySelector("span") : null;
    (label || element).textContent = initials.toUpperCase().slice(0, 2);
    if (imageUrl) {
      element.style.backgroundImage = `url("${imageUrl.replace(/"/g, "%22")}")`;
      element.classList.add("has-image");
    } else {
      element.style.backgroundImage = "";
      element.classList.remove("has-image");
    }
  }

  function setFieldValue(element, value) {
    if (element && document.activeElement !== element) {
      element.value = value || "";
    }
  }

  function renderProfile() {
    state.profile = normalizeProfile(state.profile);
    const initials = initialsFromName(state.profile.name);
    els.sidebarName.textContent = state.profile.name || "Haji H.";
    els.sidebarPlan.innerHTML = `<i aria-hidden="true"></i>${state.profile.authenticated ? "Signed in" : "Guest"} · Pro`;
    paintAvatar(els.sidebarAvatar, state.profile.picture_url, initials);
    paintAvatar(els.profileAvatarButton, state.profile.picture_url, initials);
    setFieldValue(els.profileName, state.profile.name);
    setFieldValue(els.profileUsername, state.profile.username);
    setFieldValue(els.profileBio, state.profile.bio);
    setFieldValue(els.profileAiNickname, state.profile.ai_nickname);
    if (els.profilePersonality && document.activeElement !== els.profilePersonality) {
      els.profilePersonality.value = state.profile.personality;
    }
    els.profileSyncStatus.textContent = state.profile.authenticated ? "Synced to your account" : "Saved on this device";
  }

  function render() {
    applyTheme();
    renderHeader();
    renderSettings();
    renderProfile();
    renderConversationList();
    renderMessages();
    resizeInput();
  }

  function getApiHistory(conversation) {
    return conversation.messages
      .filter((message) => !message.pending && (message.role === "user" || message.role === "assistant") && message.content)
      .slice(-MAX_HISTORY_TURNS)
      .map((message) => ({
        role: message.role,
        content: message.content.slice(0, 4000),
      }));
  }

  function authHeaders() {
    const token = window.localStorage.getItem(AUTH_TOKEN_KEY);
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function apiJson(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: "same-origin",
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...authHeaders(),
        ...(options.headers || {}),
      },
    });
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    if (!response.ok) {
      throw new Error((data && (data.detail || data.message)) || `Request failed with HTTP ${response.status}`);
    }
    return data || {};
  }

  function applyRemoteProfile(profile) {
    state.profile = normalizeProfile({ ...state.profile, ...profile, authenticated: true });
    if (profile.theme) state.theme = normalizeTheme(profile.theme);
    if (typeof profile.memory_enabled === "boolean") state.memoryEnabled = profile.memory_enabled;
    if (profile.ai_mode) state.aiMode = normalizeAiMode(profile.ai_mode);
    if (profile.answer_mode) state.answerMode = normalizeMode(profile.answer_mode);
    saveState();
    render();
  }

  async function loadRemoteProfile() {
    if (!window.localStorage.getItem(AUTH_TOKEN_KEY)) return;
    try {
      const profile = await apiJson("/user-auth/me");
      applyRemoteProfile(profile);
    } catch {
      state.profile.authenticated = false;
      saveState();
      renderProfile();
    }
  }

  let profileSyncTimer = null;
  function queueProfileSync() {
    saveState();
    renderProfile();
    if (!window.localStorage.getItem(AUTH_TOKEN_KEY)) return;
    window.clearTimeout(profileSyncTimer);
    profileSyncTimer = window.setTimeout(async () => {
      els.profileSyncStatus.textContent = "Syncing...";
      try {
        const profile = await apiJson("/user-auth/me", {
          method: "PATCH",
          body: JSON.stringify({
            name: state.profile.name,
            username: state.profile.username,
            bio: state.profile.bio,
            picture_url: state.profile.picture_url && !state.profile.picture_url.startsWith("data:") ? state.profile.picture_url : undefined,
            ai_nickname: state.profile.ai_nickname,
            personality: state.profile.personality,
            theme: state.theme,
            memory_enabled: state.memoryEnabled,
            ai_mode: state.aiMode,
            answer_mode: state.answerMode,
          }),
        });
        applyRemoteProfile(profile);
      } catch (error) {
        els.profileSyncStatus.textContent = "Saved locally";
      }
    }, 550);
  }

  async function sendToBackend(payload) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let response;
    try {
      response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new Error("Chat request timed out. Please try again.");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }

    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (!response.ok) {
      const detail = data && (data.detail || data.message);
      throw new Error(detail || `Chat request failed with HTTP ${response.status}`);
    }
    return data || {};
  }

  function scrollMessagesToBottom() {
    window.requestAnimationFrame(() => {
      els.messages.scrollTop = els.messages.scrollHeight;
    });
  }

  async function submitMessage(rawMessage) {
    const messageText = rawMessage.trim();
    if (!messageText) return;

    const conversation = activeConversation();
    const history = getApiHistory(conversation);
    const createdAt = nowIso();
    const assistantId = makeId();

    conversation.messages.push({
      id: makeId(),
      role: "user",
      content: messageText,
      createdAt,
    });
    conversation.messages.push({
      id: assistantId,
      role: "assistant",
      content: "Thinking through your question...",
      mode: "working",
      pending: true,
      createdAt: nowIso(),
    });
    if (conversation.title === "New conversation") {
      conversation.title = titleFromMessage(messageText);
    }
    conversation.updatedAt = nowIso();
    saveState();
    render();
    scrollMessagesToBottom();

    els.input.value = "";
    resizeInput();
    els.input.focus();
    els.send.disabled = true;
    setError();
    setStatus("Thinking", "busy");

    try {
      const data = await sendToBackend({
        message: messageText,
        history,
        session_id: conversation.sessionId,
        answer_mode: state.answerMode,
        memory_enabled: state.memoryEnabled,
        ai_mode: state.aiMode,
      });
      const assistant = conversation.messages.find((item) => item.id === assistantId);
      if (assistant) {
        assistant.content = String(data.answer || "I could not produce an answer from the chat backend.");
        assistant.mode = String(data.mode || "chat");
        assistant.intent = data.intent || null;
        assistant.sourceStrategy = data.source_strategy || null;
        assistant.memoryConfidence = Number(data.memory_confidence || 0);
        assistant.notice = data.notice || null;
        assistant.citations = Array.isArray(data.citations) ? data.citations : [];
        assistant.pending = false;
      }
      conversation.sessionId = data.session_id || conversation.sessionId;
      if (data.conversation_title) {
        conversation.title = String(data.conversation_title);
      }
      conversation.updatedAt = nowIso();
      setStatus("Ready", "ready");
    } catch (error) {
      const assistant = conversation.messages.find((item) => item.id === assistantId);
      if (assistant) {
        assistant.content = "I could not reach the chat backend right now. Please retry once the service is available.";
        assistant.mode = "offline";
        assistant.notice = error instanceof Error ? error.message : "Unknown chat error";
        assistant.pending = false;
      }
      setError(error instanceof Error ? error.message : "Chat request failed");
      setStatus("Offline", "error");
    } finally {
      conversation.updatedAt = nowIso();
      saveState();
      render();
      els.send.disabled = false;
      scrollMessagesToBottom();
    }
  }

  function createConversation() {
    const conversation = {
      id: makeId(),
      title: "New conversation",
      sessionId: null,
      createdAt: nowIso(),
      updatedAt: nowIso(),
      messages: [],
    };
    state.conversations.unshift(conversation);
    state.activeId = conversation.id;
    saveState();
    render();
    closeSidebar();
    els.input.focus();
  }

  function clearActiveConversation() {
    const conversation = activeConversation();
    conversation.messages = [];
    conversation.sessionId = null;
    conversation.title = "New conversation";
    conversation.updatedAt = nowIso();
    saveState();
    render();
    setError();
    setStatus("Ready", "ready");
    els.input.focus();
  }

  function exportActiveConversation() {
    const conversation = activeConversation();
    const payload = {
      exported_at: nowIso(),
      title: conversation.title,
      session_id: conversation.sessionId,
      answer_mode: state.answerMode,
      ai_mode: state.aiMode,
      memory_enabled: state.memoryEnabled,
      messages: conversation.messages
        .filter((message) => !message.pending)
        .map((message) => ({
          role: message.role,
          content: message.content,
          created_at: message.createdAt,
          mode: message.mode || "",
        })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const filename = `${conversation.title || "hajihaz-chat"}`.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "hajihaz-chat";
    link.href = url;
    link.download = `${filename}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function resizeInput() {
    els.input.style.height = "auto";
    els.input.style.height = `${Math.min(190, Math.max(42, els.input.scrollHeight))}px`;
  }

  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitMessage(els.input.value);
  });

  els.input.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      submitMessage(els.input.value);
    }
  });

  els.input.addEventListener("input", resizeInput);

  els.mode.addEventListener("change", () => {
    state.answerMode = normalizeMode(els.mode.value);
    queueProfileSync();
  });

  els.search.addEventListener("input", renderConversationList);
  els.newChat.addEventListener("click", createConversation);
  els.clear.addEventListener("click", clearActiveConversation);
  els.sidebarToggle.addEventListener("click", openSidebar);
  els.sidebarClose.addEventListener("click", closeSidebar);
  els.sidebarBackdrop.addEventListener("click", closeSidebar);
  els.settingsButton.addEventListener("click", toggleSettings);
  els.themeToggle.addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : state.theme === "light" ? "system" : "dark";
    applyTheme();
    queueProfileSync();
    renderSettings();
  });
  els.memoryToggle.addEventListener("change", () => {
    state.memoryEnabled = Boolean(els.memoryToggle.checked);
    queueProfileSync();
    renderHeader();
  });
  els.aiMode.addEventListener("change", () => {
    state.aiMode = normalizeAiMode(els.aiMode.value);
    queueProfileSync();
    renderHeader();
  });
  [els.profileName, els.profileUsername, els.profileBio, els.profileAiNickname].forEach((field) => {
    field.addEventListener("input", () => {
      state.profile.name = els.profileName.value;
      state.profile.username = els.profileUsername.value;
      state.profile.bio = els.profileBio.value;
      state.profile.ai_nickname = els.profileAiNickname.value;
      state.profile = normalizeProfile(state.profile);
      queueProfileSync();
    });
  });
  els.profilePersonality.addEventListener("change", () => {
    state.profile.personality = normalizePersonality(els.profilePersonality.value);
    queueProfileSync();
  });
  els.profileAvatarButton.addEventListener("click", () => els.profileAvatarUpload.click());
  els.profileAvatarUpload.addEventListener("change", async () => {
    const file = els.profileAvatarUpload.files && els.profileAvatarUpload.files[0];
    if (!file) return;
    if (window.localStorage.getItem(AUTH_TOKEN_KEY)) {
      const formData = new FormData();
      formData.append("file", file);
      els.profileSyncStatus.textContent = "Uploading avatar...";
      try {
        const profile = await apiJson("/user-auth/avatar", { method: "POST", body: formData });
        applyRemoteProfile(profile);
        return;
      } catch {
        els.profileSyncStatus.textContent = "Saved locally";
      }
    }
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      state.profile.picture_url = String(reader.result || "");
      queueProfileSync();
    });
    reader.readAsDataURL(file);
  });
  els.exportChat.addEventListener("click", exportActiveConversation);
  els.settingsClear.addEventListener("click", () => {
    clearActiveConversation();
    closeSettings();
  });

  els.starters.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-prompt]");
    if (!button) return;
    els.input.value = button.dataset.prompt || "";
    resizeInput();
    submitMessage(els.input.value);
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSettings();
      closeSidebar();
    }
  });

  applyTheme();
  render();
  loadRemoteProfile();
})();
