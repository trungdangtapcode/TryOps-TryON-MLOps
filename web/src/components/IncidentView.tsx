import { useState } from "react";
import { AlertTriangle, FileText, Play, RotateCcw, ShieldAlert } from "lucide-react";
import type { TryOpsClient } from "../api";
import { badVtonCandidate, rollbackStatePath } from "../data";
import type { DashboardSummary, IncidentWorkflowReport, ModelRecord, PromotionDecision, RollbackState } from "../types";
import { MetricTile } from "./MetricTile";

interface IncidentViewProps {
  client: TryOpsClient;
  dashboard?: DashboardSummary;
  models: ModelRecord[];
}

export function IncidentView({ client, dashboard, models }: IncidentViewProps) {
  const blockedModels = models.filter((model) => model.stage === "rejected").length;
  const avgRating = dashboard?.feedback.avg_rating ?? 0;
  const feedbackRisk = dashboard?.feedback.count ? avgRating < 3.5 : false;
  const requestRisk = (dashboard?.total_requests ?? 0) === 0;
  const [decision, setDecision] = useState<PromotionDecision | undefined>();
  const [busy, setBusy] = useState(false);
  const [rollback, setRollback] = useState<RollbackState | undefined>();
  const [rollbackBusy, setRollbackBusy] = useState(false);
  const [workflow, setWorkflow] = useState<IncidentWorkflowReport | undefined>();
  const [workflowBusy, setWorkflowBusy] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | undefined>();

  async function runBadCandidateGate() {
    setBusy(true);
    setDecision(undefined);
    try {
      setDecision(await client.evaluatePromotion(badVtonCandidate));
    } finally {
      setBusy(false);
    }
  }

  async function runRollbackDrill() {
    setRollbackBusy(true);
    setRollback(undefined);
    try {
      setRollback(await client.rollbackState(rollbackStatePath));
    } finally {
      setRollbackBusy(false);
    }
  }

  async function loadIncidentWorkflow() {
    setWorkflowBusy(true);
    setWorkflow(undefined);
    setWorkflowError(undefined);
    try {
      setWorkflow(await client.incidentWorkflow());
    } catch (error) {
      setWorkflowError(error instanceof Error ? error.message : "Incident workflow unavailable");
    } finally {
      setWorkflowBusy(false);
    }
  }

  const latestRollback = rollback?.latest_rollback;
  const workflowChecks = workflow?.summary
    ? `${workflow.summary.passed_checks}/${workflow.summary.total_checks}`
    : "-";

  return (
    <section className="view-grid">
      <div className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">SLO and rollout posture</p>
            <h2>Incident console</h2>
          </div>
          <ShieldAlert aria-hidden="true" size={20} />
        </div>
        <div className="metric-grid">
          <MetricTile label="Rejected models" value={blockedModels} tone={blockedModels ? "red" : "green"} />
          <MetricTile label="Feedback risk" value={feedbackRisk ? "review" : "clear"} tone={feedbackRisk ? "amber" : "green"} />
          <MetricTile label="Traffic" value={dashboard?.total_requests ?? 0} tone={requestRisk ? "amber" : "blue"} />
          <MetricTile label="Open alerts" value={Number(feedbackRisk) + Number(requestRisk)} tone={feedbackRisk || requestRisk ? "amber" : "green"} />
        </div>
      </div>

      <div className="panel panel-wide">
        <div className="panel-header compact">
          <h2>Active drills</h2>
          <AlertTriangle aria-hidden="true" size={18} />
        </div>
        <div className="incident-list">
          <IncidentRow status={requestRisk ? "watch" : "clear"} title="No live traffic" />
          <IncidentRow status={feedbackRisk ? "watch" : "clear"} title="Feedback quality below threshold" />
          <IncidentRow status={blockedModels ? "watch" : "clear"} title="Rejected model present in registry" />
        </div>
      </div>

      <div className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Incident workflow</p>
            <h2>Error tracking and postmortem</h2>
          </div>
          <button className="primary-button" disabled={workflowBusy} onClick={() => void loadIncidentWorkflow()} type="button">
            <FileText aria-hidden="true" size={17} />
            {workflowBusy ? "Loading" : "Load workflow"}
          </button>
        </div>
        {workflowError ? <div className="error-box">{workflowError}</div> : null}
        <div className="metric-grid">
          <MetricTile label="Workflow" value={workflow ? (workflow.passed ? "passed" : "failed") : "idle"} tone={workflow?.passed ? "green" : workflow ? "red" : "amber"} />
          <MetricTile label="Checks" value={workflowChecks} tone={workflow?.summary.failed_checks ? "red" : workflow ? "green" : "amber"} />
          <MetricTile label="Error events" value={workflow?.summary.error_events ?? 0} tone={workflow ? "blue" : "amber"} />
          <MetricTile label="External tracker" value={workflow?.error_tracking.external_tracker.configured ? "ready" : "local"} tone={workflow?.error_tracking.external_tracker.configured ? "green" : "amber"} />
        </div>
        <div className="gate-detail-grid">
          <div className="report-item">
            <span>Incident</span>
            <strong>{workflow?.incident.id ?? "-"}</strong>
          </div>
          <div className="report-item">
            <span>Fingerprint</span>
            <strong>{workflow?.error_tracking.fingerprint ?? "-"}</strong>
          </div>
          <div className="report-item">
            <span>Postmortem</span>
            {workflow?.postmortem.path ? (
              <a href={client.artifactUrl(workflow.postmortem.path)} target="_blank" rel="noreferrer">
                <strong>{workflow.postmortem.written ? "draft ready" : "pending"}</strong>
              </a>
            ) : (
              <strong>-</strong>
            )}
          </div>
        </div>
        <div className="incident-timeline">
          {(workflow?.timeline ?? []).map((step) => (
            <div className="incident-timeline-row" key={step.state}>
              <span className={`status-pill ${step.status === "complete" ? "green" : "amber"}`}>{step.state}</span>
              <div>
                <strong>{step.description}</strong>
                <p className="muted-text">{step.owner} - {step.evidence.slice(0, 2).join(", ")}</p>
              </div>
            </div>
          ))}
          {!workflow ? (
            <div className="incident-timeline-row">
              <span className="status-pill amber">idle</span>
              <div>
                <strong>No workflow artifact loaded.</strong>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Promotion drill</p>
            <h2>Block bad model</h2>
          </div>
          <button className="primary-button" disabled={busy} onClick={() => void runBadCandidateGate()} type="button">
            <Play aria-hidden="true" size={17} />
            {busy ? "Running" : "Run gate"}
          </button>
        </div>
        <div className="metric-grid">
          <MetricTile label="Gate" value={decision ? (decision.approved ? "approved" : "blocked") : "idle"} tone={decision?.approved ? "green" : decision ? "red" : "amber"} />
          <MetricTile label="Candidate" value={badVtonCandidate.candidate_id} tone="blue" />
          <MetricTile label="Actor" value={decision?.auth?.principal?.role ?? "-"} tone={decision?.auth?.allowed ? "green" : "amber"} />
          <MetricTile label="Reasons" value={decision?.reasons?.length ?? 0} tone={decision?.approved ? "green" : decision ? "red" : "amber"} />
        </div>
        {decision?.error ? <div className="error-box">{decision.error.code}: {decision.error.message}</div> : null}
        <div className="gate-detail-grid">
          <div className="report-item">
            <span>Target</span>
            <strong>{decision?.target_stage ?? "champion"}</strong>
          </div>
          <div className="report-item">
            <span>Vulnerabilities</span>
            <strong>{badVtonCandidate.vulnerabilities.critical} critical / {badVtonCandidate.vulnerabilities.high} high</strong>
          </div>
          <div className="report-item">
            <span>Signed</span>
            <strong>{badVtonCandidate.signed ? "true" : "false"}</strong>
          </div>
        </div>
        <div className="decision-list">
          {(decision?.reasons ?? ["No gate run yet."]).slice(0, 8).map((reason) => (
            <div className="decision-row" key={reason}>
              <span className={`status-pill ${decision?.approved ? "green" : "red"}`}>
                {decision?.approved ? "pass" : "block"}
              </span>
              <strong>{reason}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Rollback drill</p>
            <h2>Restore champion</h2>
          </div>
          <button className="primary-button" disabled={rollbackBusy} onClick={() => void runRollbackDrill()} type="button">
            <RotateCcw aria-hidden="true" size={17} />
            {rollbackBusy ? "Running" : "Run rollback"}
          </button>
        </div>
        <div className="metric-grid">
          <MetricTile label="Status" value={latestRollback?.status ?? "idle"} tone={latestRollback ? "green" : "amber"} />
          <MetricTile label="Restore" value={latestRollback?.restored_candidate_id ?? "-"} tone="blue" />
          <MetricTile label="Rolled back" value={latestRollback?.rolled_back_candidate_id ?? "-"} tone={latestRollback ? "amber" : "blue"} />
          <MetricTile label="Schema" value={latestRollback?.schema_version ?? "-"} tone="green" />
        </div>
        <div className="gate-detail-grid">
          <div className="report-item">
            <span>Package</span>
            <strong>{latestRollback?.package_id ?? "-"}</strong>
          </div>
          <div className="report-item">
            <span>Profile</span>
            <strong>{latestRollback?.profile ?? "-"}</strong>
          </div>
          <div className="report-item">
            <span>Updated</span>
            <strong>{rollback?.updated_at ?? "-"}</strong>
          </div>
        </div>
        <div className="decision-list">
          <div className="decision-row">
            <span className={`status-pill ${latestRollback ? "green" : "amber"}`}>
              {latestRollback ? "recorded" : "idle"}
            </span>
            <strong>{latestRollback?.reason ?? "No rollback drill loaded."}</strong>
          </div>
          {(latestRollback?.triggered_by ?? []).map((trigger) => (
            <div className="decision-row" key={trigger}>
              <span className="status-pill amber">trigger</span>
              <strong>{trigger}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function IncidentRow({ status, title }: { status: "clear" | "watch"; title: string }) {
  return (
    <div className="incident-row">
      <span className={`status-pill ${status === "clear" ? "green" : "amber"}`}>{status}</span>
      <strong>{title}</strong>
    </div>
  );
}
