import { useEffect, useMemo, useState } from "react";
import { TryOpsClient } from "./api";
import {
  beginOidcLogin,
  beginOidcLogout,
  clearStoredOidcToken,
  completeOidcRedirect,
  loadStoredOidcToken,
  refreshOidcToken,
  type OidcTokenState
} from "./auth";
import { AccountDashboardView } from "./components/AccountDashboardView";
import { AppShell } from "./components/AppShell";
import { DashboardView } from "./components/DashboardView";
import { EndUserShell } from "./components/EndUserShell";
import { EvaluationView } from "./components/EvaluationView";
import { ExperimentView } from "./components/ExperimentView";
import { GovernanceView } from "./components/GovernanceView";
import { HistoryView } from "./components/HistoryView";
import { IncidentView } from "./components/IncidentView";
import { LlmPlayground } from "./components/LlmPlayground";
import { PipelineRunsView } from "./components/PipelineRunsView";
import { ProfessorDemoView } from "./components/ProfessorDemoView";
import { RegistryView } from "./components/RegistryView";
import { VtonStudio } from "./components/VtonStudio";
import type {
  AccountDashboard,
  AccountInvitation,
  AccountMember,
  AccountQuota,
  AccountSummary,
  AuthConfig,
  AuthSession,
  DashboardSummary,
  EvaluationIndex,
  ExperimentConsole,
  ModelRecord,
  QuotaReadModel,
  RequestRecord,
  UserProfile,
  JobConcurrency,
  VtonJobRecord,
  ViewKey
} from "./types";

const API_KEY_STORAGE = "tryops.console.api_key";
const ACCOUNT_ID_STORAGE = "tryops.console.account_id";
const ACCOUNT_JOB_CACHE_STORAGE = "tryops.console.account_jobs";

export function App() {
  const initialAccountId = useMemo(() => localStorage.getItem(ACCOUNT_ID_STORAGE) ?? "", []);
  const initialJobCache = useMemo(() => loadStoredAccountJobs(initialAccountId), [initialAccountId]);
  const [activeView, setActiveView] = useState<ViewKey>("vton");
  const [apiKey, setApiKey] = useState("");
  const [devApiKeyEnabled, setDevApiKeyEnabled] = useState(false);
  const [token, setToken] = useState<OidcTokenState | undefined>(() => loadStoredOidcToken());
  const [authConfig, setAuthConfig] = useState<AuthConfig | undefined>();
  const [health, setHealth] = useState<"checking" | "ready" | "degraded">("checking");
  const [dashboard, setDashboard] = useState<DashboardSummary | undefined>();
  const [requests, setRequests] = useState<RequestRecord[]>([]);
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationIndex | undefined>();
  const [experiments, setExperiments] = useState<ExperimentConsole | undefined>();
  const [quota, setQuota] = useState<QuotaReadModel | undefined>();
  const [accountDashboard, setAccountDashboard] = useState<AccountDashboard | undefined>();
  const [accountQuota, setAccountQuota] = useState<AccountQuota | undefined>();
  const [accountJobs, setAccountJobs] = useState<VtonJobRecord[]>(initialJobCache.jobs);
  const [accountJobConcurrency, setAccountJobConcurrency] = useState<JobConcurrency | undefined>(initialJobCache.concurrency);
  const [accountMembers, setAccountMembers] = useState<AccountMember[]>([]);
  const [accountInvitations, setAccountInvitations] = useState<AccountInvitation[]>([]);
  const [session, setSession] = useState<AuthSession | undefined>();
  const [lastError, setLastError] = useState<string | undefined>();
  const [selectedAccountId, setSelectedAccountIdState] = useState(initialAccountId);

  const activeApiKey = devApiKeyEnabled ? apiKey : "";
  const client = useMemo(
    () => new TryOpsClient(activeApiKey, token?.accessToken ?? "", selectedAccountId),
    [activeApiKey, selectedAccountId, token?.accessToken]
  );
  const authenticated = Boolean(token?.accessToken || activeApiKey.trim());

  useEffect(() => {
    localStorage.removeItem(API_KEY_STORAGE);
  }, []);

  useEffect(() => {
    if (!apiKey.trim()) {
      setDevApiKeyEnabled(false);
    }
  }, [apiKey]);

  useEffect(() => {
    let cancelled = false;
    const bootClient = new TryOpsClient("");
    void bootClient.authConfig()
      .then(async (config) => {
        if (cancelled) {
          return;
        }
        setAuthConfig(config);
        const nextToken = await completeOidcRedirect(config);
        if (!cancelled) {
          setToken(nextToken);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLastError(error instanceof Error ? error.message : "Authentication setup failed");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!authConfig || !token?.refreshToken) {
      return undefined;
    }
    const refreshInMs = Math.max(5_000, token.expiresAt - Date.now() - 60_000);
    const timer = window.setTimeout(() => {
      void refreshOidcToken(authConfig, token)
        .then((nextToken) => {
          setToken(nextToken);
          if (!nextToken) {
            setSession(undefined);
            setLastError("Your session expired. Log in again.");
          }
        })
        .catch(() => {
          setToken(undefined);
          setSession(undefined);
          setLastError("Your session expired. Log in again.");
        });
    }, refreshInMs);
    return () => window.clearTimeout(timer);
  }, [authConfig, token]);

  async function refreshConsole() {
    setLastError(undefined);
    try {
      await client.health();
      setHealth("ready");
    } catch (error) {
      setHealth("degraded");
      setLastError(error instanceof Error ? error.message : "API health check failed");
      return;
    }

    if (token?.accessToken && !authConfig) {
      return;
    }

    if (!authenticated) {
      setSession(undefined);
      setAccountDashboard(undefined);
      setAccountQuota(undefined);
      setAccountJobs([]);
      setAccountJobConcurrency(undefined);
      setAccountMembers([]);
      setAccountInvitations([]);
      return;
    }

    try {
      const requestClient = await freshClient();
      await requestClient.bootstrapAccount();
      const nextSession = await requestClient.session();
      setSession(nextSession);
      const nextAccounts = nextSession.accounts ?? [];
      const activeAccountId = nextSession.account?.id ?? nextSession.active_account?.id ?? "";
      if (activeAccountId && selectedAccountId !== activeAccountId) {
        setSelectedAccountId(activeAccountId);
      }
      const accountOutcomes = await Promise.allSettled([
        requestClient.accountDashboard(),
        requestClient.accountQuota(),
        requestClient.accountJobs("all", 20),
        requestClient.accountMembers(),
        activeAccountId ? requestClient.accountInvitations(activeAccountId) : Promise.resolve([])
      ]);
      if (accountOutcomes[0].status === "fulfilled") {
        setAccountDashboard(accountOutcomes[0].value);
      }
      if (accountOutcomes[1].status === "fulfilled") {
        setAccountQuota(accountOutcomes[1].value);
      }
      if (accountOutcomes[2].status === "fulfilled") {
        const nextJobs = accountOutcomes[2].value.data ?? [];
        const nextConcurrency = accountOutcomes[2].value.concurrency;
        setAccountJobs(nextJobs);
        setAccountJobConcurrency(nextConcurrency);
        storeAccountJobs(accountOutcomes[2].value.account.id, nextJobs, nextConcurrency);
      }
      if (accountOutcomes[3].status === "fulfilled") {
        setAccountMembers(accountOutcomes[3].value);
      } else if (!nextSession.permissions.can_manage_account || nextAccounts.length === 0) {
        setAccountMembers([]);
      }
      if (accountOutcomes[4].status === "fulfilled") {
        setAccountInvitations(accountOutcomes[4].value);
      } else if (!nextSession.permissions.can_manage_account || nextAccounts.length === 0) {
        setAccountInvitations([]);
      }

      if (!nextSession.permissions.can_read_admin) {
        return;
      }

      const adminOutcomes = await Promise.allSettled([
        requestClient.dashboard(),
        requestClient.quotaSummary(),
        requestClient.history(),
        requestClient.models(),
        requestClient.evaluations(),
        requestClient.experiments()
      ]);
      if (adminOutcomes[0].status === "fulfilled") {
        setDashboard(adminOutcomes[0].value);
      }
      if (adminOutcomes[1].status === "fulfilled") {
        setQuota(adminOutcomes[1].value);
      }
      if (adminOutcomes[2].status === "fulfilled") {
        setRequests(adminOutcomes[2].value);
      }
      if (adminOutcomes[3].status === "fulfilled") {
        setModels(adminOutcomes[3].value);
      }
      if (adminOutcomes[4].status === "fulfilled") {
        setEvaluations(adminOutcomes[4].value);
      }
      if (adminOutcomes[5].status === "fulfilled") {
        setExperiments(adminOutcomes[5].value);
      }
      const rejected = adminOutcomes.find((outcome) => outcome.status === "rejected");
      if (rejected?.status === "rejected") {
        setLastError(rejected.reason instanceof Error ? rejected.reason.message : "Console data refresh failed");
      }
    } catch (error) {
      if (token?.accessToken && isUnauthorizedSessionError(error)) {
        clearAuthState();
        setLastError("Your login session was stale. Log in again.");
        return;
      }
      setSession(undefined);
      setLastError(error instanceof Error ? error.message : "Session check failed");
    }
  }

  async function freshClient(): Promise<TryOpsClient> {
    if (activeApiKey.trim() || !authConfig || !token?.accessToken) {
      return client;
    }
    const nextToken = await refreshOidcToken(authConfig, token);
    if (!nextToken) {
      setToken(undefined);
      setSession(undefined);
      throw new Error("Your session expired. Log in again.");
    }
    if (nextToken.accessToken !== token.accessToken || nextToken.expiresAt !== token.expiresAt) {
      setToken(nextToken);
    }
    return new TryOpsClient(activeApiKey, nextToken.accessToken, selectedAccountId);
  }

  useEffect(() => {
    if (token?.accessToken && !authConfig) {
      return;
    }
    void refreshConsole();
  }, [authConfig, client, authenticated, token?.accessToken]);

  useEffect(() => {
    if (!authenticated || accountJobs.length === 0) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refreshConsole();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [accountJobs.length, authenticated, selectedAccountId, token?.accessToken, activeApiKey]);

  const allowedViews = useMemo<ViewKey[]>(
    () => session?.permissions.nav?.length ? session.permissions.nav : ["vton"],
    [session]
  );

  useEffect(() => {
    if (!allowedViews.includes(activeView)) {
      setActiveView(allowedViews[0] ?? "vton");
    }
  }, [activeView, allowedViews]);

  async function login() {
    if (!authConfig) {
      setLastError("Auth config is not loaded yet.");
      return;
    }
    await beginOidcLogin(authConfig, "login");
  }

  async function signup() {
    if (!authConfig) {
      setLastError("Auth config is not loaded yet.");
      return;
    }
    await beginOidcLogin(authConfig, "register");
  }

  function logout() {
    const tokenToLogout = token;
    clearAuthState();
    if (!authConfig) {
      return;
    }
    beginOidcLogout(authConfig, tokenToLogout);
  }

  function clearAuthState() {
    clearStoredOidcToken();
    setToken(undefined);
      setSession(undefined);
      setAccountDashboard(undefined);
      setAccountQuota(undefined);
      setAccountJobs([]);
      setAccountJobConcurrency(undefined);
      setAccountMembers([]);
      setAccountInvitations([]);
      setDevApiKeyEnabled(false);
      setApiKey("");
      localStorage.removeItem(API_KEY_STORAGE);
      localStorage.removeItem(ACCOUNT_ID_STORAGE);
      localStorage.removeItem(ACCOUNT_JOB_CACHE_STORAGE);
      setSelectedAccountIdState("");
  }

  function setSelectedAccountId(value: string) {
    setSelectedAccountIdState(value);
    if (value) {
      localStorage.setItem(ACCOUNT_ID_STORAGE, value);
    } else {
      localStorage.removeItem(ACCOUNT_ID_STORAGE);
    }
    const cached = loadStoredAccountJobs(value);
    setAccountJobs(cached.jobs);
    setAccountJobConcurrency(cached.concurrency);
  }

  async function createWorkspace(payload: { name: string; description?: string }) {
    const requestClient = await freshClient();
    const created = await requestClient.createAccount(payload);
    if (created.account?.id) {
      setSelectedAccountId(created.account.id);
    }
    await refreshConsole();
  }

  async function updateWorkspace(accountId: string, payload: { name?: string; description?: string }) {
    const requestClient = await freshClient();
    await requestClient.updateAccount(accountId, payload);
    await refreshConsole();
  }

  async function searchProfiles(query: string): Promise<UserProfile[]> {
    const requestClient = await freshClient();
    return requestClient.searchProfiles(query);
  }

  async function inviteMember(email: string, role: string) {
    const accountId = session?.account?.id ?? selectedAccountId;
    if (!accountId) {
      throw new Error("Select a workspace first.");
    }
    const requestClient = await freshClient();
    await requestClient.inviteAccountMember(accountId, { email, role });
    await refreshConsole();
  }

  async function revokeInvitation(invitationId: string) {
    const accountId = session?.account?.id ?? selectedAccountId;
    if (!accountId) {
      throw new Error("Select a workspace first.");
    }
    const requestClient = await freshClient();
    await requestClient.revokeInvitation(accountId, invitationId);
    await refreshConsole();
  }

  async function updateMember(memberId: string, payload: { role?: string; status?: string }) {
    const accountId = session?.account?.id ?? selectedAccountId;
    if (!accountId) {
      throw new Error("Select a workspace first.");
    }
    const requestClient = await freshClient();
    await requestClient.updateAccountMember(accountId, memberId, payload);
    await refreshConsole();
  }

  async function removeMember(memberId: string) {
    const accountId = session?.account?.id ?? selectedAccountId;
    if (!accountId) {
      throw new Error("Select a workspace first.");
    }
    const requestClient = await freshClient();
    await requestClient.removeAccountMember(accountId, memberId);
    await refreshConsole();
  }

  const view = (() => {
    switch (activeView) {
      case "account":
        return (
          <AccountDashboardView
            client={client}
            dashboard={accountDashboard}
            jobs={accountJobs}
            jobConcurrency={accountJobConcurrency}
            invitations={accountInvitations}
            members={accountMembers}
            quota={accountQuota}
            session={session}
            onCreateWorkspace={createWorkspace}
            onInviteMember={inviteMember}
            onRefresh={refreshConsole}
            onRemoveMember={removeMember}
            onRevokeInvitation={revokeInvitation}
            onSearchProfiles={searchProfiles}
            onUpdateMember={updateMember}
            onUpdateWorkspace={updateWorkspace}
          />
        );
      case "demo":
        return <ProfessorDemoView />;
      case "llm":
        return <LlmPlayground client={client} onMutate={refreshConsole} />;
      case "vton":
        return (
          <VtonStudio
            client={client}
            onMutate={refreshConsole}
            activeJobs={accountJobs}
            jobConcurrency={accountJobConcurrency}
            recentRequests={accountDashboard?.recent_requests ?? []}
          />
        );
      case "history":
        return <HistoryView client={client} requests={requests} onRefresh={refreshConsole} />;
      case "runs":
        return <PipelineRunsView index={evaluations} onRefresh={refreshConsole} />;
      case "registry":
        return <RegistryView models={models} />;
      case "evaluations":
        return <EvaluationView index={evaluations} onRefresh={refreshConsole} />;
      case "experiments":
        return <ExperimentView client={client} experiments={experiments} onRefresh={refreshConsole} />;
      case "governance":
        return <GovernanceView client={client} requests={requests} models={models} />;
      case "incidents":
        return <IncidentView client={client} dashboard={dashboard} models={models} />;
      case "dashboard":
      default:
        return (
          <DashboardView
            dashboard={dashboard}
            quota={quota}
            requests={requests}
            models={models}
            onRefresh={refreshConsole}
          />
        );
    }
  })();

  const authProps = {
    apiKey,
    authConfig,
    devApiKeyEnabled,
    authenticated,
    onApiKeyChange: setApiKey,
    onDevApiKeyEnabledChange: setDevApiKeyEnabled,
    onLogin: login,
    onLogout: logout,
    onSignup: signup
  };

  if (activeView === "vton" || activeView === "account" || !session?.permissions.can_read_admin) {
    return (
      <EndUserShell
        activeView={activeView}
        allowedViews={allowedViews}
        health={health}
        lastError={lastError}
        onRefresh={refreshConsole}
        onAccountChange={setSelectedAccountId}
        onViewChange={setActiveView}
        selectedAccountId={selectedAccountId}
        session={session}
        {...authProps}
      >
        {view}
      </EndUserShell>
    );
  }

  return (
    <AppShell
      activeView={activeView}
      allowedViews={allowedViews}
      health={health}
      lastError={lastError}
      onRefresh={refreshConsole}
      onViewChange={setActiveView}
      session={session}
      {...authProps}
    >
      {view}
    </AppShell>
  );
}

function isUnauthorizedSessionError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return /Unauthorized|auth_preflight_failed|missing_api_key|invalid_jwt|expired_jwt/.test(error.message);
}

function loadStoredAccountJobs(accountId: string): { jobs: VtonJobRecord[]; concurrency?: JobConcurrency } {
  if (!accountId) {
    return { jobs: [] };
  }
  try {
    const raw = localStorage.getItem(ACCOUNT_JOB_CACHE_STORAGE);
    if (!raw) {
      return { jobs: [] };
    }
    const cache = JSON.parse(raw) as {
      accountId?: string;
      jobs?: VtonJobRecord[];
      concurrency?: JobConcurrency;
      storedAt?: number;
    };
    if (cache.accountId !== accountId || !Array.isArray(cache.jobs)) {
      return { jobs: [] };
    }
    return {
      jobs: cache.jobs.slice(0, 20),
      concurrency: cache.concurrency
    };
  } catch {
    localStorage.removeItem(ACCOUNT_JOB_CACHE_STORAGE);
    return { jobs: [] };
  }
}

function storeAccountJobs(accountId: string, jobs: VtonJobRecord[], concurrency?: JobConcurrency): void {
  if (!accountId) {
    return;
  }
  try {
    localStorage.setItem(
      ACCOUNT_JOB_CACHE_STORAGE,
      JSON.stringify({
        accountId,
        jobs: jobs.slice(0, 20),
        concurrency,
        storedAt: Date.now()
      })
    );
  } catch {
    return;
  }
}
