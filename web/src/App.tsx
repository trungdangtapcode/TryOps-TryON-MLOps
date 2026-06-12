import { useEffect, useMemo, useState } from "react";
import { TryOpsClient } from "./api";
import { AppShell } from "./components/AppShell";
import { DashboardView } from "./components/DashboardView";
import { GovernanceView } from "./components/GovernanceView";
import { HistoryView } from "./components/HistoryView";
import { IncidentView } from "./components/IncidentView";
import { LlmPlayground } from "./components/LlmPlayground";
import { PipelineRunsView } from "./components/PipelineRunsView";
import { ProfessorDemoView } from "./components/ProfessorDemoView";
import { RegistryView } from "./components/RegistryView";
import { VtonStudio } from "./components/VtonStudio";
import { EvaluationView } from "./components/EvaluationView";
import type { AuthSession, DashboardSummary, EvaluationIndex, ModelRecord, QuotaReadModel, RequestRecord, ViewKey } from "./types";

const API_KEY_STORAGE = "tryops.console.api_key";

export function App() {
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(API_KEY_STORAGE) ?? "");
  const [health, setHealth] = useState<"checking" | "ready" | "degraded">("checking");
  const [dashboard, setDashboard] = useState<DashboardSummary | undefined>();
  const [requests, setRequests] = useState<RequestRecord[]>([]);
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationIndex | undefined>();
  const [quota, setQuota] = useState<QuotaReadModel | undefined>();
  const [session, setSession] = useState<AuthSession | undefined>();
  const [lastError, setLastError] = useState<string | undefined>();

  const client = useMemo(() => new TryOpsClient(apiKey), [apiKey]);

  useEffect(() => {
    localStorage.setItem(API_KEY_STORAGE, apiKey);
  }, [apiKey]);

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

    if (apiKey.trim()) {
      try {
        setSession(await client.session());
      } catch (error) {
        setSession(undefined);
        setLastError(error instanceof Error ? error.message : "RBAC session check failed");
        return;
      }
    } else {
      setSession(undefined);
      return;
    }

    const outcomes = await Promise.allSettled([
      client.dashboard(),
      client.quotaSummary(),
      client.history(),
      client.models(),
      client.evaluations()
    ]);
    if (outcomes[0].status === "fulfilled") {
      setDashboard(outcomes[0].value);
    }
    if (outcomes[1].status === "fulfilled") {
      setQuota(outcomes[1].value);
    }
    if (outcomes[2].status === "fulfilled") {
      setRequests(outcomes[2].value);
    }
    if (outcomes[3].status === "fulfilled") {
      setModels(outcomes[3].value);
    }
    if (outcomes[4].status === "fulfilled") {
      setEvaluations(outcomes[4].value);
    }
    const rejected = outcomes.find((outcome) => outcome.status === "rejected");
    if (rejected?.status === "rejected") {
      setLastError(rejected.reason instanceof Error ? rejected.reason.message : "Console data refresh failed");
    }
  }

  useEffect(() => {
    void refreshConsole();
  }, [client]);

  const allowedViews = useMemo<ViewKey[]>(
    () => session?.permissions.nav?.length ? session.permissions.nav : ["demo", "llm", "vton"],
    [session]
  );

  useEffect(() => {
    if (!allowedViews.includes(activeView)) {
      setActiveView(allowedViews[0] ?? "demo");
    }
  }, [activeView, allowedViews]);

  const view = (() => {
    switch (activeView) {
      case "demo":
        return <ProfessorDemoView />;
      case "llm":
        return <LlmPlayground client={client} onMutate={refreshConsole} />;
      case "vton":
        return <VtonStudio client={client} onMutate={refreshConsole} />;
      case "history":
        return <HistoryView client={client} requests={requests} onRefresh={refreshConsole} />;
      case "runs":
        return <PipelineRunsView index={evaluations} onRefresh={refreshConsole} />;
      case "registry":
        return <RegistryView models={models} />;
      case "evaluations":
        return <EvaluationView index={evaluations} onRefresh={refreshConsole} />;
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

  return (
    <AppShell
      activeView={activeView}
      apiKey={apiKey}
      allowedViews={allowedViews}
      health={health}
      lastError={lastError}
      onApiKeyChange={setApiKey}
      onRefresh={refreshConsole}
      onViewChange={setActiveView}
      session={session}
    >
      {view}
    </AppShell>
  );
}
