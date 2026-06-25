import { Play, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import type { TryOpsClient } from "../api";
import { experimentVariants } from "../data";
import { compactJson, formatNumber, formatOptionalMs } from "../format";
import type { ExperimentAnalysis, ExperimentConsole, ExperimentDecision } from "../types";
import { MetricTile } from "./MetricTile";

interface ExperimentViewProps {
  client: TryOpsClient;
  experiments?: ExperimentConsole;
  onRefresh: () => void;
}

export function ExperimentView({ client, experiments, onRefresh }: ExperimentViewProps) {
  const [mode, setMode] = useState<"ab" | "bandit">("bandit");
  const [decision, setDecision] = useState<ExperimentDecision | undefined>();
  const [analysis, setAnalysis] = useState<ExperimentAnalysis | undefined>(
    experiments?.analysis_report?.native_experiment_stats
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const reportDecision = mode === "ab"
    ? experiments?.routing_report?.decisions?.ab
    : experiments?.routing_report?.decisions?.bandit;
  const activeDecision = decision ?? reportDecision;
  const activeAnalysis = analysis ?? experiments?.analysis_report?.native_experiment_stats;
  const variants = activeDecision?.experiment?.variants ?? [];
  const eligibleCount = variants.filter((variant) => variant.eligible).length;
  const blockedCount = variants.length - eligibleCount;
  const selected = activeDecision?.experiment?.selected?.variant ?? activeDecision?.primary_alias;
  const bestVariant = activeAnalysis?.best_variant ?? "-";
  const productionReady = experiments?.production_ready ?? false;

  const analysisRows = useMemo(() => activeAnalysis?.variants ?? [], [activeAnalysis]);

  async function runDecision() {
    setBusy(true);
    setError(undefined);
    try {
      const nextDecision = await client.routeExperiment({
        mode,
        request_id: `req-console-experiment-${Date.now()}`,
        experiment_id: experiments?.experiment_id ?? "tryops-llm-answer-quality",
        variants: experimentVariants,
        holdback_percent: 5,
        guardrail_thresholds: {
          max_block_rate: 0.02,
          max_latency_p95_ms: 120,
          max_error_rate: 0.01
        }
      });
      const nextAnalysis = await client.analyzeExperiment({
        experiment_id: experiments?.experiment_id ?? "tryops-llm-answer-quality",
        holdback: {
          name: "champion_holdback",
          impressions: 1000,
          rewards: 820
        },
        variants: experimentVariants.filter((variant) => variant.name !== "candidate")
      });
      setDecision(nextDecision);
      setAnalysis(nextAnalysis);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Experiment route failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view-grid dashboard-grid">
      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Online experiments</p>
            <h2>A/B and bandit routing</h2>
          </div>
          <div className="button-row">
            <select className="compact-select" onChange={(event) => setMode(event.target.value as "ab" | "bandit")} value={mode}>
              <option value="bandit">Bandit</option>
              <option value="ab">A/B</option>
            </select>
            <button className="icon-button" onClick={onRefresh} title="Refresh experiment evidence" type="button">
              <RefreshCw aria-hidden="true" size={18} />
            </button>
            <button className="primary-button" disabled={busy} onClick={() => void runDecision()} type="button">
              <Play aria-hidden="true" size={17} />
              {busy ? "Routing" : "Route"}
            </button>
          </div>
        </div>
        <div className="metric-grid">
          <MetricTile label="Production" value={productionReady ? "ready" : "partial"} tone={productionReady ? "green" : "amber"} />
          <MetricTile label="Selected" value={selected ?? "-"} tone="green" />
          <MetricTile label="Eligible" value={eligibleCount} tone="blue" />
          <MetricTile label="Blocked" value={blockedCount} tone={blockedCount > 0 ? "amber" : "green"} />
        </div>
        {error ? <div className="error-box">{error}</div> : null}
      </section>

      <section className="panel panel-wide">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Native route</p>
            <h2>{activeDecision?.experiment?.source ?? "unavailable"}</h2>
          </div>
          <span className={`status-pill ${activeDecision?.experiment?.available ? "green" : "amber"}`}>
            {activeDecision?.experiment?.available ? "native" : "native unavailable"}
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Variant</th>
                <th>Status</th>
                <th>Traffic</th>
                <th>Reward</th>
                <th>p95</th>
                <th>Violations</th>
              </tr>
            </thead>
            <tbody>
              {variants.map((variant) => (
                <tr key={variant.name}>
                  <td>{variant.name}</td>
                  <td>
                    <span className={`status-pill ${variant.eligible ? "green" : "red"}`}>
                      {variant.eligible ? "eligible" : "blocked"}
                    </span>
                  </td>
                  <td>{formatNumber(variant.traffic_percent)}%</td>
                  <td>{formatNumber(variant.reward_rate)}</td>
                  <td>{formatOptionalMs(variant.latency_p95_ms)}</td>
                  <td className="mono">{variant.violations?.join(", ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header compact">
          <h2>Sequential verdict</h2>
          <span className="status-pill blue">{bestVariant}</span>
        </div>
        <div className="capacity-stack">
          {analysisRows.map((variant) => (
            <MetricTile
              key={variant.name}
              label={variant.name}
              tone={variant.sequential.early_stop ? "green" : "amber"}
              value={variant.sequential.verdict}
            />
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header compact">
          <h2>Raw contract</h2>
        </div>
        <pre className="json-box">{compactJson({ decision: activeDecision, analysis: activeAnalysis })}</pre>
      </section>
    </div>
  );
}
