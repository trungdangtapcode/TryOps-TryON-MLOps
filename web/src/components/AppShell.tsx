import { RefreshCw, ShieldCheck, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { navItems } from "../data";
import type { AuthSession, ViewKey } from "../types";
import { StatusBanner } from "./StatusBanner";

interface AppShellProps {
  activeView: ViewKey;
  apiKey: string;
  allowedViews: ViewKey[];
  children: ReactNode;
  health: "checking" | "ready" | "degraded";
  lastError?: string;
  onApiKeyChange: (value: string) => void;
  onRefresh: () => void;
  onViewChange: (value: ViewKey) => void;
  session?: AuthSession;
}

export function AppShell({
  activeView,
  apiKey,
  allowedViews,
  children,
  health,
  lastError,
  onApiKeyChange,
  onRefresh,
  onViewChange,
  session
}: AppShellProps) {
  const visibleNavItems = navItems.filter((item) => allowedViews.includes(item.key));
  const activeLabel = navItems.find((item) => item.key === activeView)?.label ?? "TryOps";

  return (
    <div className="app-frame">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand-block">
          <div className="brand-mark">T</div>
          <div>
            <strong>TryOps Console</strong>
            <span>Enterprise AI operations</span>
          </div>
        </div>
        <nav className="nav-stack">
          {visibleNavItems.map((item) => {
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
        </nav>
        <div className="sidebar-footer">
          <ShieldCheck aria-hidden="true" size={18} />
          <span>Native edge: Rust · Go · C++</span>
        </div>
      </aside>

      <main className="main-surface">
        <header className="topbar">
          <div>
            <p className="eyebrow">Production control plane</p>
            <h1>{activeLabel}</h1>
          </div>
          <div className="topbar-actions">
            <div className="session-pill" title={session ? session.principal.scopes.join(" ") : "No active RBAC session"}>
              <UserRound aria-hidden="true" size={16} />
              <span>{session?.principal.role ?? "No session"}</span>
            </div>
            <label className="api-key-field">
              <span>API key</span>
              <input
                autoComplete="off"
                onChange={(event) => onApiKeyChange(event.target.value)}
                placeholder="tryops-viewer-demo-key"
                type="password"
                value={apiKey}
              />
            </label>
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
