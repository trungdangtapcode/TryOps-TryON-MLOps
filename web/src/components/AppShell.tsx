import { ExternalLink, LogIn, LogOut, RefreshCw, Settings2, ShieldCheck, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { navItems } from "../data";
import type { AuthConfig, AuthSession, ViewKey } from "../types";
import { StatusBanner } from "./StatusBanner";

interface AppShellProps {
  activeView: ViewKey;
  apiKey: string;
  authConfig?: AuthConfig;
  authenticated: boolean;
  allowedViews: ViewKey[];
  children: ReactNode;
  devApiKeyEnabled: boolean;
  health: "checking" | "ready" | "degraded";
  lastError?: string;
  onApiKeyChange: (value: string) => void;
  onDevApiKeyEnabledChange: (value: boolean) => void;
  onLogin: () => void;
  onLogout: () => void;
  onRefresh: () => void;
  onSignup: () => void;
  onViewChange: (value: ViewKey) => void;
  session?: AuthSession;
}

export function AppShell({
  activeView,
  apiKey,
  authConfig,
  authenticated,
  allowedViews,
  children,
  devApiKeyEnabled,
  health,
  lastError,
  onApiKeyChange,
  onDevApiKeyEnabledChange,
  onLogin,
  onLogout,
  onRefresh,
  onSignup,
  onViewChange,
  session
}: AppShellProps) {
  const visibleNavItems = navItems.filter((item) => allowedViews.includes(item.key));
  const studioNavItems = visibleNavItems.filter((item) => !item.requiredScope);
  const adminNavItems = visibleNavItems.filter((item) => item.requiredScope);
  const activeLabel = navItems.find((item) => item.key === activeView)?.label ?? "TryOps";
  const activeSurface = activeView === "dashboard" || adminNavItems.some((item) => item.key === activeView)
    ? "admin"
    : "studio";
  const surfaceEyebrow = activeSurface === "admin" ? "Admin dashboard" : "End-user app";
  const identityLabel = session?.principal.display_name
    || session?.principal.email
    || session?.principal.username
    || (devApiKeyEnabled && apiKey.trim() ? "Local dev key" : "Guest");
  const roleLabel = session?.membership?.role ?? session?.principal.role ?? "signed out";

  return (
    <div className="app-frame">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand-block">
          <div className="brand-mark">T</div>
          <div>
            <strong>TryOps</strong>
            <span>Studio and operations</span>
          </div>
        </div>
        <nav className="nav-stack">
          {studioNavItems.length ? (
            <NavSection
              activeView={activeView}
              items={studioNavItems}
              label="Studio"
              onViewChange={onViewChange}
            />
          ) : null}
          {adminNavItems.length ? (
            <NavSection
              activeView={activeView}
              items={adminNavItems}
              label="Admin"
              onViewChange={onViewChange}
            />
          ) : null}
        </nav>
        <div className="sidebar-footer">
          <ShieldCheck aria-hidden="true" size={18} />
          <span>Native edge: Rust · Go · C++</span>
        </div>
      </aside>

      <main className="main-surface">
        <header className="topbar">
          <div>
            <p className="eyebrow">{surfaceEyebrow}</p>
            <h1>{activeLabel}</h1>
          </div>
          <div className="topbar-actions">
            <div className="session-pill" title={session ? session.principal.scopes.join(" ") : "No active RBAC session"}>
              <UserRound aria-hidden="true" size={16} />
              <span>{identityLabel}</span>
            </div>
            {authenticated ? (
              <button className="text-button" onClick={onLogout} type="button">
                <LogOut aria-hidden="true" size={16} />
                Sign out
              </button>
            ) : (
              <>
                <button className="text-button" disabled={!authConfig} onClick={onLogin} type="button">
                  <LogIn aria-hidden="true" size={16} />
                  Log in
                </button>
                <button className="text-button" disabled={!authConfig} onClick={onSignup} type="button">
                  Sign up
                </button>
              </>
            )}
            <details className="consumer-settings admin-auth-menu">
              <summary title="Auth settings">
                <Settings2 aria-hidden="true" size={16} />
                <span>Auth</span>
              </summary>
              <div className="consumer-settings-panel">
                <div className="profile-card">
                  <span>Profile</span>
                  <strong>{identityLabel}</strong>
                  <small>{session?.account?.name ?? "No workspace session"} · {roleLabel}</small>
                </div>
                {authConfig?.account_console_endpoint && session ? (
                  <a className="settings-link" href={authConfig.account_console_endpoint} rel="noreferrer" target="_blank">
                    <UserRound aria-hidden="true" size={16} />
                    Profile, password, MFA
                    <ExternalLink aria-hidden="true" size={14} />
                  </a>
                ) : null}
                <label className="dev-toggle">
                  <input
                    checked={devApiKeyEnabled}
                    onChange={(event) => onDevApiKeyEnabledChange(event.target.checked)}
                    type="checkbox"
                  />
                  <span>Enable local dev API key fallback</span>
                </label>
                <label className="api-key-field">
                  <span>Local dev API key</span>
                  <input
                    autoComplete="off"
                    disabled={!devApiKeyEnabled}
                    onChange={(event) => onApiKeyChange(event.target.value)}
                    placeholder="tryops-viewer-demo-key"
                    type="password"
                    value={apiKey}
                  />
                </label>
                <p className="settings-note">Normal users sign in through Keycloak. The key is only for local debugging.</p>
              </div>
            </details>
            <button className="icon-button" onClick={onRefresh} title="Refresh console data" type="button">
              <RefreshCw aria-hidden="true" size={18} />
            </button>
          </div>
        </header>
        <StatusBanner health={health} message={lastError} />
        {children}
      </main>
    </div>
  );
}

interface NavSectionProps {
  activeView: ViewKey;
  items: typeof navItems;
  label: string;
  onViewChange: (value: ViewKey) => void;
}

function NavSection({ activeView, items, label, onViewChange }: NavSectionProps) {
  return (
    <div className="nav-section">
      <span className="nav-section-label">{label}</span>
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button
            className={item.key === activeView ? "nav-item active" : "nav-item"}
            key={item.key}
            onClick={() => onViewChange(item.key)}
            title={item.label}
            type="button"
          >
            <Icon aria-hidden="true" size={18} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
