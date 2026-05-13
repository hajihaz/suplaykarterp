import Link from "next/link";
import type { CSSProperties } from "react";

type MeterStyle = CSSProperties & Record<"--meter", string>;

const emptyMeterStyle: MeterStyle = { "--meter": "0%" };

const railLinks = [
  ["Profile", "#adminProfilePanel"],
  ["Dashboard", "#adminDashboardPanel"],
  ["Knowledge", "#adminComposerPanel"],
  ["Library", "#adminLibraryPanel"],
  ["Monitoring", "#adminMonitorPanel"]
];

export function AdminShell() {
  return (
    <main className="page-shell admin-os-shell admin-locked" data-admin-page="true">
      <section className="hero-card compact admin-hero">
        <div className="hero-copy">
          <span className="eyebrow">Enterprise workforce OS</span>
          <h1>Suplaykart ERP command center</h1>
          <p>
            Operate knowledge, workforce readiness, runtime health, source quality, and executive reporting from one
            protected admin cockpit.
          </p>
          <div className="action-row">
            <Link className="secondary-button link-button" href="/">
              Open assistant
            </Link>
          </div>
        </div>
        <div className="hero-meta">
          <div className="meta-tile">
            <span>Session</span>
            <strong id="adminLoginStatus">Not authenticated</strong>
            <small id="adminBrowserStatus">Browser ready</small>
          </div>
          <div className="meta-tile">
            <span>Ops score</span>
            <strong id="adminOpsScore">Locked</strong>
            <small id="adminGroundingRate">Waiting for analytics.</small>
          </div>
          <div className="meta-tile">
            <span>Request window</span>
            <strong id="adminRequestsToday">0</strong>
            <small>Realtime admin telemetry</small>
          </div>
        </div>
      </section>

      <aside className="admin-command-rail" aria-label="Admin command center">
        <div className="admin-rail-brand">
          <span className="admin-rail-mark" aria-hidden="true">
            SK
          </span>
          <div>
            <strong>Suplaykart ERP</strong>
            <small>Workforce operating system</small>
          </div>
        </div>

        <nav className="admin-rail-nav" aria-label="Admin sections">
          {railLinks.map(([label, href]) => (
            <a href={href} key={href}>
              {label}
            </a>
          ))}
        </nav>

        <section className="admin-appearance-card" aria-label="Appearance">
          <div className="admin-appearance-head">
            <strong>Appearance</strong>
            <small id="adminThemeStatus">System</small>
          </div>
          <div className="admin-theme-options" role="group" aria-label="Admin color theme">
            <button className="admin-theme-option" data-admin-theme-option="system" type="button">
              System
            </button>
            <button className="admin-theme-option" data-admin-theme-option="dark" type="button">
              Dark
            </button>
            <button className="admin-theme-option" data-admin-theme-option="light" type="button">
              Light
            </button>
          </div>
        </section>

        <section className="admin-profile-card" id="adminProfilePanel">
          <div className="admin-profile-head">
            <button className="admin-profile-avatar" id="adminProfileAvatarButton" type="button">
              <span id="adminProfileAvatarPreview">SK</span>
            </button>
            <div>
              <strong id="adminProfileNameLabel">Workspace operator</strong>
              <span id="adminProfileEmail">Login required</span>
            </div>
            <input id="adminProfileAvatarInput" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden />
          </div>

          <div className="admin-profile-fields">
            <label className="field-group" htmlFor="adminProfileDisplayNameInput">
              <span className="field-label">Display name</span>
              <input id="adminProfileDisplayNameInput" maxLength={80} placeholder="Operations lead" />
            </label>
            <label className="field-group" htmlFor="adminProfileRoleInput">
              <span className="field-label">Role title</span>
              <input id="adminProfileRoleInput" maxLength={80} placeholder="ERP command lead" />
            </label>
            <label className="field-group" htmlFor="adminProfileTimezoneInput">
              <span className="field-label">Timezone</span>
              <input id="adminProfileTimezoneInput" maxLength={80} placeholder="Asia/Kolkata" />
            </label>
            <label className="field-group" htmlFor="adminProfileBioInput">
              <span className="field-label">Operator note</span>
              <textarea id="adminProfileBioInput" maxLength={500} rows={3} />
            </label>
            <label className="toggle-card compact-toggle" htmlFor="adminProfileNotificationsInput">
              <span className="toggle-copy">
                <strong>Notify on system changes</strong>
                <small>Prepared for alert delivery.</small>
              </span>
              <input id="adminProfileNotificationsInput" type="checkbox" />
            </label>
          </div>

          <div className="action-row rail-actions">
            <button className="secondary-button secondary-button--inline" id="adminProfileSaveButton" type="button">
              Save profile
            </button>
            <span className="helper-text" id="adminProfileStatus">
              Profile locked.
            </span>
          </div>
        </section>

        <section className="admin-rail-metrics" id="adminDashboardPanel">
          <div className="admin-meter-row">
            <span>CPU</span>
            <strong id="adminRailCpu">0.00</strong>
            <i className="admin-meter" id="adminCpuMeter" style={emptyMeterStyle} />
          </div>
          <div className="admin-meter-row">
            <span>Memory</span>
            <strong id="adminRailMemory">0%</strong>
            <i className="admin-meter" id="adminMemoryMeter" style={emptyMeterStyle} />
          </div>
          <div className="admin-meter-row">
            <span>Disk</span>
            <strong id="adminRailDisk">0%</strong>
            <i className="admin-meter" id="adminDiskMeter" style={emptyMeterStyle} />
          </div>
        </section>
      </aside>

      <section className="admin-grid admin-workspace">
        <div className="admin-main-stack">
          <section className="panel-card admin-access-panel">
            <div className="panel-intro">
              <div>
                <span className="eyebrow">Authentication</span>
                <h2>Admin access</h2>
              </div>
              <span className="status-pill idle" id="adminSessionPill">
                Locked
              </span>
            </div>
            <div className="field-grid two-col">
              <label className="field-group" htmlFor="adminEmailInput">
                <span className="field-label">Admin email</span>
                <input defaultValue="admin@hajihaz.local" id="adminEmailInput" placeholder="Admin email" />
              </label>
              <label className="field-group" htmlFor="adminPasswordInput">
                <span className="field-label">Password</span>
                <input id="adminPasswordInput" placeholder="Password" type="password" />
              </label>
            </div>
            <div className="action-row">
              <button className="primary-button" id="adminLoginButton" type="button">
                Unlock workspace
              </button>
              <button className="secondary-button" id="adminLogoutButton" type="button">
                Clear session
              </button>
            </div>
          </section>

          <section className="panel-card">
            <div className="stats-grid admin-stats-grid">
              <div className="stat-card">
                <span>Documents</span>
                <strong id="adminDocumentsCount">0</strong>
              </div>
              <div className="stat-card">
                <span>Chunks</span>
                <strong id="adminChunksCount">0</strong>
              </div>
              <div className="stat-card">
                <span>Groups</span>
                <strong id="adminGroupsCount">0</strong>
              </div>
              <div className="stat-card">
                <span>Sources</span>
                <strong id="adminSourcesCount">0</strong>
              </div>
              <div className="stat-card">
                <span>AI runtime</span>
                <strong id="adminAiProvider">Locked</strong>
              </div>
              <div className="stat-card">
                <span>Provider</span>
                <strong id="adminProviderReady">Login required</strong>
              </div>
              <div className="stat-card">
                <span>Ollama</span>
                <strong id="adminOllamaReady">Login required</strong>
              </div>
            </div>
          </section>

          <section className="panel-card" id="adminComposerPanel">
            <div className="panel-intro">
              <div>
                <span className="eyebrow">Knowledge operations</span>
                <h2>Add workforce knowledge</h2>
              </div>
              <span className="status-pill idle" id="adminComposerState">
                Login required
              </span>
            </div>
            <div className="form-stack">
              <div className="field-grid two-col">
                <input id="adminTitleInput" placeholder="Document title" />
                <input id="adminGroupInput" placeholder="Group, team, or department" />
              </div>
              <div className="field-grid two-col">
                <input id="adminTagsInput" placeholder="Tags, separated by commas" />
                <input id="adminSourceUrlInput" placeholder="Optional source URL" />
              </div>
              <label className="toggle-card" htmlFor="adminCorePersonaInput">
                <span className="toggle-copy">
                  <strong>Core persona source</strong>
                  <small>Prioritize this material for identity and owner-profile answers.</small>
                </span>
                <input id="adminCorePersonaInput" type="checkbox" />
              </label>
              <textarea
                className="admin-textarea"
                id="adminContentInput"
                placeholder="Paste SOPs, policies, service notes, team workflows, or operational context..."
                rows={10}
              />
              <button className="primary-button" id="adminSaveButton" type="button">
                Save document
              </button>
            </div>
            <p className="error-text" hidden id="adminErrorText" />
          </section>
        </div>

        <aside className="admin-side-stack">
          <section className="panel-card accent-panel">
            <div className="panel-intro">
              <div>
                <span className="eyebrow">Realtime analytics</span>
                <h2>Dashboard pulse</h2>
              </div>
            </div>
            <div className="debug-list" id="adminAnalyticsList" />
          </section>
          <section className="panel-card">
            <div className="section-head">
              <h2>Recent alerts</h2>
              <span id="adminAlertsSummary">0 alerts</span>
            </div>
            <div className="debug-list" id="adminAlertsList" />
          </section>
          <section className="panel-card">
            <div className="section-head">
              <h2>Health checks</h2>
              <span id="adminHealthChecksSummary">0 checks</span>
            </div>
            <div className="debug-list" id="adminHealthChecksList" />
          </section>
        </aside>
      </section>

      <section className="panel-card document-list" id="adminLibraryPanel">
        <div className="section-head">
          <h2>Current knowledge base</h2>
          <span id="adminDocumentItemsCount">0 items</span>
        </div>
        <label className="field-group" htmlFor="adminSearchInput">
          <span className="field-label">Search library</span>
          <input id="adminSearchInput" placeholder="Find by title, group, tags, source, or content" />
        </label>
        <div className="empty-state" id="adminEmptyState">
          Unlock the workspace to load the live Suplaykart knowledge base.
        </div>
        <div className="document-grid" hidden id="adminDocumentsGrid" />
      </section>

      <section className="admin-grid monitor-grid" id="adminMonitorPanel">
        <section className="panel-card">
          <div className="section-head">
            <h2>Source health</h2>
            <span id="adminSourceHealthCount">0 sources</span>
          </div>
          <div className="debug-list" id="adminSourceHealthList" />
        </section>
        <section className="panel-card">
          <div className="section-head">
            <h2>Deploy audit</h2>
            <span id="adminSecretAuditSummary">Waiting</span>
          </div>
          <div className="debug-list" id="adminSecretAuditList" />
        </section>
      </section>
    </main>
  );
}
