const TOKEN_KEY = "hajihaz-admin-token";
const ADMIN_THEME_KEY = "hajihaz-admin-theme";
const LONG_REQUEST_TIMEOUT_MS = 120000;
const ADMIN_THEME_CHOICES = new Set(["system", "dark", "light"]);

async function api(path, options = {}) {
  const headers = {
    ...(options.token ? { Authorization: `Bearer ${options.token}` } : {})
  };
  if (!options.formData) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.formData || (options.body ? JSON.stringify(options.body) : undefined),
    cache: "no-store"
  });

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
  element.textContent = message;
  element.hidden = !message;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTimestamp(value) {
  if (!value) {
    return "Just now";
  }
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return String(value);
  }
  return timestamp.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
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
  return `${size.toFixed(size >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function buildCitationMarkup(citations) {
  if (!citations || citations.length === 0) {
    return "";
  }

  return `
    <div class="citation-list">
      ${citations
        .map(
          (citation) => `
            <div class="citation-card">
              <strong>${escapeHtml(citation.title)}</strong>
              <span>${escapeHtml(citation.excerpt)}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function appendMessage(role, content, citations, mode) {
  const messages = document.getElementById("chatMessages");
  if (!messages) {
    return;
  }

  const article = document.createElement("article");
  article.className = `message-bubble ${role}`;
  article.innerHTML = `
    <div class="message-head">
      <span>${role === "assistant" ? "HajiHaz AI" : "You"}</span>
      ${mode ? `<small>${escapeHtml(mode)}</small>` : ""}
    </div>
    <p>${escapeHtml(content)}</p>
    ${buildCitationMarkup(citations)}
    ${role === "assistant" ? '<button class="ghost-button" data-copy-message type="button">Copy response</button>' : ""}
  `;

  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

function bindCopyButtons() {
  document.querySelectorAll("[data-copy-message]").forEach((button) => {
    if (button.dataset.boundCopy === "true") {
      return;
    }

    button.dataset.boundCopy = "true";
    button.addEventListener("click", async () => {
      const text = button.parentElement?.querySelector("p")?.textContent || "";
      try {
        await navigator.clipboard.writeText(text);
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

  const input = document.getElementById("chatInput");
  const sendButton = document.getElementById("chatSendButton");

  if (!(input instanceof HTMLTextAreaElement) || !(sendButton instanceof HTMLButtonElement)) {
    return;
  }

  bindCopyButtons();

  async function submitMessage(message) {
    const nextMessage = (message || input.value).trim();
    if (!nextMessage) {
      return;
    }

    showError("chatErrorText", "");
    setText("chatStatusText", "Generating response...");
    setText("chatRuntimeStatus", "Thinking...");
    input.value = "";
    sendButton.disabled = true;
    appendMessage("user", nextMessage);

    try {
      const response = await api("/api/chat", {
        method: "POST",
        body: { message: nextMessage }
      });
      appendMessage("assistant", response.answer, response.citations, response.mode);
      setText("chatStatusText", "Browser ready. App API route: POST /api/chat");
      setText("chatRuntimeStatus", "Browser ready");
      bindCopyButtons();
    } catch (error) {
      showError("chatErrorText", error instanceof Error ? error.message : "Something went wrong.");
      setText("chatStatusText", "Browser ready. App API route: POST /api/chat");
      setText("chatRuntimeStatus", "Browser ready");
    } finally {
      sendButton.disabled = false;
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

  document.querySelectorAll("[data-prompt]").forEach((button) => {
    if (button instanceof HTMLButtonElement) {
      button.addEventListener("click", () => {
        void submitMessage(button.dataset.prompt || "");
      });
    }
  });
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
  const avatarButton = document.getElementById("adminProfileAvatarButton");
  const avatarPreview = document.getElementById("adminProfileAvatarPreview");
  const displayNameInput = document.getElementById("adminProfileDisplayNameInput");
  const roleInput = document.getElementById("adminProfileRoleInput");
  const timezoneInput = document.getElementById("adminProfileTimezoneInput");
  const bioInput = document.getElementById("adminProfileBioInput");
  const notificationsInput = document.getElementById("adminProfileNotificationsInput");
  const displayName = String(currentProfile.display_name || currentProfile.email || "Workspace operator");
  const avatarUrl = String(currentProfile.avatar_url || "").trim();

  setText("adminProfileNameLabel", displayName);
  setText("adminProfileEmail", currentProfile.email || "Login required");
  setText("adminProfileStatus", currentProfile.email ? "Profile synced." : "Profile locked.");
  if (avatarPreview instanceof HTMLElement) {
    avatarPreview.textContent = adminInitials(currentProfile);
  }
  if (avatarButton instanceof HTMLElement) {
    avatarButton.classList.toggle("has-image", Boolean(avatarUrl));
    avatarButton.style.backgroundImage = avatarUrl ? `url("${avatarUrl}")` : "";
  }
  if (displayNameInput instanceof HTMLInputElement) {
    displayNameInput.value = currentProfile.display_name || "";
  }
  if (roleInput instanceof HTMLInputElement) {
    roleInput.value = currentProfile.role_title || "Workspace operator";
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
}

function renderStats(stats) {
  const providerName = stats.ai_provider || "unknown";
  const providerLabel =
    providerName === "ollama"
      ? stats.web_search_enabled
        ? "Ollama + web"
        : "Ollama + knowledge"
      : providerName === "anthropic"
        ? "Live AI + knowledge"
        : providerName.charAt(0).toUpperCase() + providerName.slice(1);

  setText("adminDocumentsCount", String(stats.documents || 0));
  setText("adminChunksCount", String(stats.chunks || 0));
  setText("adminGroupsCount", String(stats.groups || 0));
  setText("adminSourcesCount", `${stats.active_sources || 0}/${stats.sources || 0}`);
  setText("adminAiProvider", providerLabel);
  setText("adminProviderReady", stats.provider_ready ? "Ready" : "Fallback only");
  setText("adminOllamaReady", stats.ollama_configured ? "Reachable" : "Unavailable");
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
  container.innerHTML = normalizedItems.map((item) => formatter(item)).join("");
}

function renderDebugSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    return;
  }
  const sourceHealth = Array.isArray(snapshot.source_health) ? snapshot.source_health : [];
  const alerts = Array.isArray(snapshot.recent_alerts) ? snapshot.recent_alerts : [];
  const checks = Array.isArray(snapshot.recent_health_checks) ? snapshot.recent_health_checks : [];
  const analytics = snapshot.analytics && typeof snapshot.analytics === "object" ? snapshot.analytics : {};
  const secretAudit = snapshot.secret_audit && typeof snapshot.secret_audit === "object" ? snapshot.secret_audit : {};
  const metrics = snapshot.resource_metrics && typeof snapshot.resource_metrics === "object" ? snapshot.resource_metrics : {};
  const dailyRequests = analytics.daily_requests || [];
  const todaysRequests = dailyRequests.length ? dailyRequests[dailyRequests.length - 1].count || 0 : 0;
  const warningSignals =
    alerts.filter((item) => item.level === "error" || item.level === "warning").length +
    checks.filter((item) => item.status !== "ok").length +
    (secretAudit.status && secretAudit.status !== "healthy" ? 1 : 0);
  const opsScore = Math.max(72, 100 - warningSignals * 8 - Math.round(Number(metrics.disk_percent || 0) / 12));

  setText("adminOpsScore", warningSignals ? `${opsScore} watch` : `${opsScore} healthy`);
  setText("adminRequestsToday", String(todaysRequests));
  setText("adminGroundingRate", `${Number(analytics.average_citations || 0).toFixed(1)} avg citations`);
  setText("adminRailCpu", Number(metrics.cpu_load_1 || 0).toFixed(2));
  setText("adminRailMemory", `${Number(metrics.memory_percent || 0).toFixed(1)}%`);
  setText("adminRailDisk", `${Number(metrics.disk_percent || 0).toFixed(1)}%`);
  setMeter("adminCpuMeter", Math.min(100, Number(metrics.cpu_load_1 || 0) * 18));
  setMeter("adminMemoryMeter", Number(metrics.memory_percent || 0));
  setMeter("adminDiskMeter", Number(metrics.disk_percent || 0));
  setText("adminSourceHealthCount", `${sourceHealth.length} source${sourceHealth.length === 1 ? "" : "s"}`);
  setText("adminAlertsSummary", `${alerts.length} alert${alerts.length === 1 ? "" : "s"}`);
  setText("adminHealthChecksSummary", `${checks.length} check${checks.length === 1 ? "" : "s"}`);
  setText("adminSecretAuditSummary", secretAudit.status || "Waiting");

  renderDebugCards("adminAnalyticsList", analytics.daily_requests || [], (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.day)}</strong>
        <span>${item.count} requests</span>
      </div>
      <p>Avg prompt ${Number(analytics.average_prompt_length || 0).toFixed(1)} chars · Avg answer ${Number(analytics.average_answer_length || 0).toFixed(1)} chars · Avg citations ${Number(analytics.average_citations || 0).toFixed(1)}</p>
    </article>
  `);
  renderDebugCards("adminAlertsList", alerts, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.title)}</strong>
        <span class="status-pill ${item.level === "error" ? "warning" : "idle"}">${escapeHtml(item.level)}</span>
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <span>${escapeHtml(formatTimestamp(item.created_at))}</span>
    </article>
  `);
  renderDebugCards("adminHealthChecksList", checks, (item) => `
    <article class="debug-card">
      <div class="document-meta-row">
        <strong>${escapeHtml(item.name)}</strong>
        <span class="status-pill ${item.status === "ok" ? "ready" : "warning"}">${escapeHtml(item.status)}</span>
      </div>
      <p>${escapeHtml(item.detail)}</p>
    </article>
  `);
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
}

function renderDocuments(documents) {
  const grid = document.getElementById("adminDocumentsGrid");
  const emptyState = document.getElementById("adminEmptyState");
  const searchInput = document.getElementById("adminSearchInput");
  if (!grid) {
    return;
  }
  const items = Array.isArray(documents) ? documents : [];
  const query = searchInput instanceof HTMLInputElement ? searchInput.value.trim().toLowerCase() : "";
  const filteredItems = !query
    ? items
    : items.filter((entry) =>
        [entry.title, entry.content, entry.source, entry.group_name, entry.source_url, ...(Array.isArray(entry.tags) ? entry.tags : [])]
          .join(" ")
          .toLowerCase()
          .includes(query)
      );

  setText(
    "adminDocumentItemsCount",
    query ? `${filteredItems.length} of ${items.length} items` : `${items.length} item${items.length === 1 ? "" : "s"}`
  );

  if (!filteredItems.length) {
    grid.innerHTML = "";
    grid.hidden = true;
    if (emptyState) {
      emptyState.textContent = items.length
        ? "No documents match the current search."
        : "No knowledge loaded yet. Unlock the workspace and add your first document.";
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
                    ${entry.core_persona ? `<div class="document-badge-row"><span class="persona-badge">Core persona</span></div>` : ""}
                    <p>${escapeHtml(entry.content)}</p>
                    ${
                      tags.length
                        ? `<div class="tag-row">${tags.map((tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`).join("")}</div>`
                        : ""
                    }
                    <div class="document-meta-row">
                      <span class="helper-text">${escapeHtml(entry.source_url || "Ready for retrieval")}</span>
                      <span class="document-timestamp">${escapeHtml(formatTimestamp(entry.updated_at))}</span>
                    </div>
                    <div class="document-actions">
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

function initAdminPage() {
  if (!document.querySelector("[data-admin-page='true']")) {
    return;
  }

  initAdminThemeControls();

  const adminShell = document.querySelector("[data-admin-page='true']");
  const emailInput = document.getElementById("adminEmailInput");
  const passwordInput = document.getElementById("adminPasswordInput");
  const titleInput = document.getElementById("adminTitleInput");
  const groupInput = document.getElementById("adminGroupInput");
  const tagsInput = document.getElementById("adminTagsInput");
  const sourceUrlInput = document.getElementById("adminSourceUrlInput");
  const corePersonaInput = document.getElementById("adminCorePersonaInput");
  const contentInput = document.getElementById("adminContentInput");
  const searchInput = document.getElementById("adminSearchInput");
  const loginButton = document.getElementById("adminLoginButton");
  const logoutButton = document.getElementById("adminLogoutButton");
  const saveButton = document.getElementById("adminSaveButton");
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
    !(searchInput instanceof HTMLInputElement) ||
    !(loginButton instanceof HTMLButtonElement) ||
    !(logoutButton instanceof HTMLButtonElement) ||
    !(saveButton instanceof HTMLButtonElement) ||
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

  let token = window.localStorage.getItem(TOKEN_KEY) || "";
  let documentsCache = [];
  let editingDocumentId = null;

  function setAuthenticated(authenticated) {
    if (adminShell instanceof HTMLElement) {
      adminShell.classList.toggle("admin-locked", !authenticated);
      adminShell.classList.toggle("admin-authenticated", authenticated);
    }
    logoutButton.disabled = !authenticated;
    saveButton.disabled = !authenticated;
    profileSaveButton.disabled = !authenticated;
    profileAvatarButton.disabled = !authenticated;
    setStatusPill("adminSessionPill", authenticated ? "Unlocked" : "Locked", authenticated ? "ready" : "idle");
  }

  function resetComposer() {
    editingDocumentId = null;
    titleInput.value = "";
    groupInput.value = "";
    tagsInput.value = "";
    sourceUrlInput.value = "";
    corePersonaInput.checked = false;
    contentInput.value = "";
    saveButton.textContent = "Save document";
  }

  function bindDocumentActions() {
    document.querySelectorAll("[data-edit-document]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement) || button.dataset.boundEdit === "true") {
        return;
      }
      button.dataset.boundEdit = "true";
      button.addEventListener("click", () => {
        const documentId = Number(button.dataset.editDocument);
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
        saveButton.textContent = "Update document";
        setStatusPill("adminComposerState", "Editing", "warning");
        titleInput.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });

    document.querySelectorAll("[data-delete-document]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement) || button.dataset.boundDelete === "true") {
        return;
      }
      button.dataset.boundDelete = "true";
      button.addEventListener("click", async () => {
        const documentId = Number(button.dataset.deleteDocument);
        const entry = documentsCache.find((item) => item.id === documentId);
        if (!token || !entry || !window.confirm(`Delete "${entry.title}" from the knowledge base?`)) {
          return;
        }
        button.disabled = true;
        try {
          await api(`/api/admin/documents/${documentId}`, { method: "DELETE", token });
          await refresh();
          setText("adminLoginStatus", "Document deleted.");
        } catch (error) {
          showError("adminErrorText", error instanceof Error ? error.message : "Delete failed.");
        } finally {
          button.disabled = false;
        }
      });
    });
  }

  async function refreshTelemetry() {
    if (!token) {
      return;
    }
    const [statsResult, debugResult] = await Promise.allSettled([
      api("/api/admin/stats", { token }),
      api("/api/admin/debug", { token })
    ]);
    if (statsResult.status === "fulfilled") {
      renderStats(statsResult.value);
    }
    if (debugResult.status === "fulfilled") {
      renderDebugSnapshot(debugResult.value);
    }
  }

  async function refresh() {
    if (!token) {
      documentsCache = [];
      renderDocuments([]);
      renderAdminProfile(null);
      setAuthenticated(false);
      return;
    }
    const [documents, me] = await Promise.all([
      api("/api/admin/documents", { token }),
      api("/api/auth/me", { token })
    ]);
    documentsCache = Array.isArray(documents) ? documents : [];
    renderDocuments(documentsCache);
    renderAdminProfile(me);
    bindDocumentActions();
    await refreshTelemetry();
    setAuthenticated(true);
  }

  setAuthenticated(Boolean(token));
  setText("adminBrowserStatus", "Browser ready");
  renderDocuments([]);

  loginButton.addEventListener("click", async () => {
    showError("adminErrorText", "");
    loginButton.disabled = true;
    setText("adminLoginStatus", "Signing in...");
    try {
      const response = await api("/api/auth/login", {
        method: "POST",
        body: {
          email: emailInput.value,
          password: passwordInput.value
        }
      });
      token = response.token;
      window.localStorage.setItem(TOKEN_KEY, token);
      passwordInput.value = "";
      await refresh();
      setText("adminLoginStatus", `Authenticated as ${response.email}`);
      setStatusPill("adminComposerState", "Ready", "ready");
    } catch (error) {
      token = "";
      window.localStorage.removeItem(TOKEN_KEY);
      setAuthenticated(false);
      setText("adminLoginStatus", error instanceof Error ? error.message : "Login failed.");
    } finally {
      loginButton.disabled = false;
    }
  });

  logoutButton.addEventListener("click", () => {
    const activeToken = token;
    void (async () => {
      if (activeToken) {
        try {
          await api("/api/auth/logout", { method: "POST", token: activeToken });
        } catch {
          // Local session clearing still wins.
        }
      }
      token = "";
      window.localStorage.removeItem(TOKEN_KEY);
      resetComposer();
      setAuthenticated(false);
      setText("adminLoginStatus", "Session cleared.");
      setStatusPill("adminComposerState", "Login required", "idle");
    })();
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
    if (!file || !token) {
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    profileAvatarButton.disabled = true;
    setText("adminProfileStatus", "Uploading avatar...");
    try {
      const profile = await api("/api/auth/avatar", {
        method: "POST",
        token,
        formData,
        timeoutMs: LONG_REQUEST_TIMEOUT_MS
      });
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
    setText("adminProfileStatus", "Saving profile...");
    try {
      const profile = await api("/api/auth/profile", {
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
      renderAdminProfile(profile);
      setText("adminLoginStatus", "Admin profile updated.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Profile update failed.");
      setText("adminProfileStatus", "Profile update failed.");
    } finally {
      profileSaveButton.disabled = !token;
    }
  });

  saveButton.addEventListener("click", async () => {
    if (!token) {
      showError("adminErrorText", "Login first to manage the knowledge base.");
      setStatusPill("adminComposerState", "Login required", "warning");
      return;
    }
    saveButton.disabled = true;
    showError("adminErrorText", "");
    setStatusPill("adminComposerState", editingDocumentId ? "Updating" : "Saving", "warning");
    try {
      const wasEditing = editingDocumentId !== null;
      const sourceForUpdate = wasEditing ? documentsCache.find((item) => item.id === editingDocumentId)?.source || "admin" : "admin";
      await api(wasEditing ? `/api/admin/documents/${editingDocumentId}` : "/api/admin/documents", {
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
      resetComposer();
      await refresh();
      setStatusPill("adminComposerState", wasEditing ? "Updated" : "Saved", "ready");
      setText("adminLoginStatus", wasEditing ? "Document updated." : "Knowledge base updated.");
    } catch (error) {
      showError("adminErrorText", error instanceof Error ? error.message : "Document request failed.");
      setStatusPill("adminComposerState", "Needs attention", "warning");
    } finally {
      saveButton.disabled = !token;
    }
  });

  searchInput.addEventListener("input", () => {
    renderDocuments(documentsCache);
    bindDocumentActions();
  });

  if (token) {
    setText("adminLoginStatus", "Existing session found. Loading workspace...");
    void refresh().catch(() => {
      token = "";
      window.localStorage.removeItem(TOKEN_KEY);
      setAuthenticated(false);
      setText("adminLoginStatus", "Stored session expired. Login again.");
    });
  }

  window.setInterval(() => {
    void refreshTelemetry();
  }, 45000);
}

window.addEventListener("load", () => {
  initChatPage();
  initAdminPage();
});
