import { ExternalLink, LogIn, LogOut, RefreshCw, Settings2, ShieldCheck, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import type { AuthConfig, AuthSession, ViewKey } from "../types";

interface EndUserShellProps {
  activeView: ViewKey;
  allowedViews: ViewKey[];
  apiKey: string;
  authConfig?: AuthConfig;
  authenticated: boolean;
  children: ReactNode;
  devApiKeyEnabled: boolean;
  health: "checking" | "ready" | "degraded";
  lastError?: string;
  onAccountChange: (value: string) => void;
  onApiKeyChange: (value: string) => void;
  onDevApiKeyEnabledChange: (value: boolean) => void;
  onLogin: () => void;
  onLogout: () => void;
  onRefresh: () => void;
  onSignup: () => void;
  onViewChange: (value: ViewKey) => void;
  selectedAccountId: string;
  session?: AuthSession;
}

export function EndUserShell({
  activeView,
  allowedViews,
  apiKey,
  authConfig,
  authenticated,
  children,
  devApiKeyEnabled,
  health,
  lastError,
  onAccountChange,
  onApiKeyChange,
  onDevApiKeyEnabledChange,
  onLogin,
  onLogout,
  onRefresh,
  onSignup,
  onViewChange,
  selectedAccountId,
  session
}: EndUserShellProps) {
  const canOpenAdmin = allowedViews.includes("dashboard") && session?.principal.role !== "viewer";
  const canOpenAccount = allowedViews.includes("account");
  const identityLabel = normalizeIdentity(
    session?.principal.display_name
    || session?.principal.email
    || session?.principal.username
    || (devApiKeyEnabled && apiKey.trim() ? "Local API key" : "Guest"),
    session?.principal.email,
    session?.principal.username
  );
  const roleLabel = session?.membership?.role ?? session?.principal.role ?? "signed out";
  const accounts = session?.accounts ?? [];
  const activeAccountId = session?.account?.id ?? selectedAccountId;
  const accountAvatarUrl = session?.account?.avatar_url ?? session?.membership?.avatar_url;
  const identityAvatarUrl = session?.membership?.avatar_url ?? accountAvatarUrl;
  const localApiKeysEnabled = Boolean(authConfig?.demo_api_key_fallback)
    || import.meta.env.VITE_TRYOPS_ENABLE_DEV_AUTH_FALLBACK === "1";

  return (
    <div className="consumer-app">
      <header className="consumer-topbar">
        <button className="consumer-brand" onClick={() => onViewChange("vton")} type="button">
          <span className="consumer-mark">T</span>
          <span>
            <strong>TryOps Fit</strong>
            <small>Virtual try-on</small>
          </span>
        </button>
        <nav className="consumer-nav" aria-label="Product navigation">
          <button className={activeView === "vton" ? "active" : ""} onClick={() => onViewChange("vton")} type="button">Studio</button>
          {canOpenAccount ? (
            <button className={activeView === "account" ? "active" : ""} onClick={() => onViewChange("account")} type="button">
              Account
            </button>
          ) : null}
          {canOpenAdmin ? (
            <button onClick={() => onViewChange("dashboard")} type="button">
              <ShieldCheck aria-hidden="true" size={16} />
              Admin
            </button>
          ) : null}
        </nav>
        <div className="consumer-actions">
          <span className={`consumer-health ${health}`} title={`API ${health}`} />
          {accounts.length > 0 ? (
            <label className="workspace-switcher">
              <span>Workspace</span>
              {accountAvatarUrl ? (
                <img alt="" className="account-avatar small" src={accountAvatarUrl} />
              ) : null}
              <select
                onChange={(event) => onAccountChange(event.target.value)}
                value={activeAccountId}
              >
                {accounts.map((item) => (
                  <option key={item.account.id} value={item.account.id}>
                    {item.account.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {authenticated ? (
            <button className="consumer-auth-button" onClick={onLogout} type="button">
              <LogOut aria-hidden="true" size={16} />
              Sign out
            </button>
          ) : (
            <>
              <button className="consumer-auth-button ghost" disabled={!authConfig} onClick={onLogin} type="button">
                <LogIn aria-hidden="true" size={16} />
                Log in
              </button>
              <button className="consumer-auth-button" disabled={!authConfig} onClick={onSignup} type="button">
                Sign up
              </button>
            </>
          )}
          <details className="consumer-settings">
            <summary title="Settings">
              {identityAvatarUrl ? (
                <img alt="" className="account-avatar small" src={identityAvatarUrl} />
              ) : (
                <UserRound aria-hidden="true" size={17} />
              )}
              <span className="consumer-identity">
                <strong>{identityLabel}</strong>
                <small>{session?.account?.name ?? roleLabel}</small>
              </span>
              <Settings2 aria-hidden="true" size={16} />
            </summary>
            <div className="consumer-settings-panel">
              <div className="profile-card">
                {identityAvatarUrl ? <img alt="" className="account-avatar" src={identityAvatarUrl} /> : null}
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
              {localApiKeysEnabled ? (
                <>
                  <label className="dev-toggle">
                    <input
                      checked={devApiKeyEnabled}
                      onChange={(event) => onDevApiKeyEnabledChange(event.target.checked)}
                      type="checkbox"
                    />
                    <span>Enable local API key</span>
                  </label>
                  <label className="api-key-field">
                    <span>Local API key</span>
                    <input
                      autoComplete="off"
                      disabled={!devApiKeyEnabled}
                      onChange={(event) => onApiKeyChange(event.target.value)}
                      placeholder="local API key"
                      type="password"
                      value={apiKey}
                    />
                  </label>
                </>
              ) : null}
              <p className="settings-note">
                Normal users sign in with username/password through Keycloak.
              </p>
              <button className="text-button full-width" onClick={onRefresh} type="button">
                <RefreshCw aria-hidden="true" size={16} />
                Refresh
              </button>
              {lastError ? <div className="asset-error">{lastError}</div> : null}
            </div>
          </details>
        </div>
      </header>
      <main className="consumer-main">
        {children}
      </main>
    </div>
  );
}

function normalizeIdentity(value: string, email?: string, username?: string): string {
  const trimmed = value.trim().replace(/\s+/g, " ");
  const parts = trimmed.split(" ");
  if (parts.length > 1 && parts.every((part) => part.toLowerCase() === parts[0].toLowerCase())) {
    return parts[0];
  }
  if (email && trimmed.toLowerCase() === `${email} ${email}`.toLowerCase()) {
    return email;
  }
  if (email && trimmed.toLowerCase().startsWith(`${email} ${email}`.toLowerCase())) {
    return email;
  }
  if (username && trimmed.toLowerCase() === `${username} ${username}`.toLowerCase()) {
    return username;
  }
  return trimmed;
}
