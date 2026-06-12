import { RefreshCw, Route } from "lucide-react";
import type { EvaluationIndex, PipelineRun } from "../types";
import { MetricTile } from "./MetricTile";

interface PipelineRunsViewProps {
  index?: EvaluationIndex;
  onRefresh: () => void;
}

const eventTone: Record<string, "green" | "amber" | "blue" | "red"> = {
  COMPLETE: "green",
  START: "blue",
  RUNNING: "blue",
  ABORT: "red",
  FAIL: "red"
};

export function PipelineRunsView({ index, onRefresh }: PipelineRunsViewProps) {
  const runs = index?.pipeline_runs ?? [];
  const completeRuns = runs.filter((run) => run.event_type === "COMPLETE").length;
  const signedRuns = runs.filter((run) => run.signed).length;

  return (
    <div className="view-grid dashboard-grid">
      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Run history</p>
            <h2>Pipeline Runs</h2>
          </div>
          <button className="icon-button" onClick={onRefresh} title="Refresh pipeline runs" type="button">
            <RefreshCw aria-hidden="true" size={18} />
          </button>
        </div>
        <div className="metric-grid">
          <MetricTile label="Runs" value={runs.length} tone="blue" />
          <MetricTile label="Complete" value={completeRuns} tone="green" />
          <MetricTile label="Signed" value={signedRuns} tone={signedRuns === runs.length && runs.length ? "green" : "amber"} />
          <MetricTile label="Artifacts" value={runs.reduce((total, run) => total + Object.keys(run.paths ?? {}).length, 0)} tone="blue" />
        </div>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">OpenLineage-backed ledger</p>
            <h2>Promotion Pipeline Evidence</h2>
          </div>
          <Route aria-hidden="true" size={18} />
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Event</th>
                <th>Candidate</th>
                <th>Workload</th>
                <th>Model</th>
                <th>Dataset</th>
                <th>Trace</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <span className="empty-inline">No pipeline runs indexed.</span>
                  </td>
                </tr>
              ) : (
                runs.map((run) => <PipelineRunRow key={`${run.candidate_id}-${run.run_id}`} run={run} />)
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Artifacts</p>
            <h2>Run Evidence Paths</h2>
          </div>
        </div>
        <div className="evidence-grid">
          {runs.map((run) => (
            <article className="report-item evidence-item" key={`${run.run_id}-paths`}>
              <div className="evidence-heading">
                <strong>{run.run_name || run.job_name || run.run_id}</strong>
                <span className={`status-pill ${run.signed ? "green" : "amber"}`}>{run.signed ? "signed" : "unsigned"}</span>
              </div>
              <span className="mono">{run.code_version || "local"}</span>
              <dl className="evidence-summary">
                {Object.entries(run.paths ?? {}).map(([label, path]) => (
                  <div key={`${run.run_id}-${label}`}>
                    <dt>{label}</dt>
                    <dd className="mono">{path}</dd>
                  </div>
                ))}
              </dl>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function PipelineRunRow({ run }: { run: PipelineRun }) {
  const model = [run.model_name, run.model_version].filter(Boolean).join(":") || "-";
  return (
    <tr>
      <td>
        <strong>{run.run_id}</strong>
        <div className="muted-text">{run.run_name || run.job_name || "-"}</div>
      </td>
      <td>
        <span className={`status-pill ${eventTone[run.event_type ?? ""] ?? "blue"}`}>{run.event_type || "recorded"}</span>
        <div className="muted-text">{run.event_time ? new Date(run.event_time).toLocaleString() : "-"}</div>
      </td>
      <td>{run.candidate_id || "-"}</td>
      <td>{run.workload || "-"}</td>
      <td>{model}</td>
      <td>{run.dataset_version || "-"}</td>
      <td className="mono">{run.trace_id || "-"}</td>
    </tr>
  );
}
