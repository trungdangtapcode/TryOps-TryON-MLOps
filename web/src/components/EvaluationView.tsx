import { RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import type { EvaluationArtifactReport, EvaluationIndex, OptimizationPanel, OptimizationVariant } from "../types";
import { MetricTile } from "./MetricTile";

interface EvaluationViewProps {
  index?: EvaluationIndex;
  onRefresh: () => void;
}

const highlightOrder = [
  "llm_pareto",
  "energy",
  "vton_comparison",
  "drift",
  "full_stack",
  "demo_acceptance",
  "demo_video",
  "vulnerability"
];

const statusTone: Record<string, "green" | "amber" | "blue" | "red"> = {
  approved: "green",
  passed: "green",
  recorded: "blue",
  partial: "amber",
  warning: "amber",
  blocked: "red",
  failed: "red"
};

export function EvaluationView({ index, onRefresh }: EvaluationViewProps) {
  const categories = useMemo(() => Object.keys(index?.category_counts ?? {}).sort(), [index]);
  const [category, setCategory] = useState("all");
  const [selectedVariant, setSelectedVariant] = useState<string | undefined>();

  const reports = useMemo(() => {
    const allReports = index?.reports ?? [];
    if (category === "all") {
      return allReports;
    }
    return allReports.filter((report) => report.category === category);
  }, [category, index]);

  const highlights = highlightOrder
    .map((key) => index?.highlights?.[key])
    .filter((report): report is EvaluationArtifactReport => Boolean(report));
  const optimization = index?.optimization_panel;
  const selectedOptimizationVariant =
    optimization?.variants.find((variant) => variant.variant === (selectedVariant ?? optimization.recommended_variant)) ??
    optimization?.variants[0];

  return (
    <div className="view-grid dashboard-grid">
      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Evidence index</p>
            <h2>Evaluation Reports</h2>
          </div>
          <button className="icon-button" onClick={onRefresh} title="Refresh evaluation reports" type="button">
            <RefreshCw aria-hidden="true" size={18} />
          </button>
        </div>
        {index ? (
          <div className="metric-grid">
            <MetricTile label="Reports" value={index.total_reports} />
            <MetricTile label="Passed" tone="green" value={index.status_counts.passed ?? 0} />
            <MetricTile label="Warnings" tone="amber" value={(index.status_counts.warning ?? 0) + (index.status_counts.partial ?? 0)} />
            <MetricTile label="Failed" tone="red" value={index.status_counts.failed ?? 0} />
          </div>
        ) : (
          <p className="empty-state">Evaluation index unavailable.</p>
        )}
      </section>

      {optimization ? (
        <OptimizationPanelView
          onSelectVariant={setSelectedVariant}
          panel={optimization}
          selected={selectedOptimizationVariant}
        />
      ) : null}

      <section className="panel panel-wide">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Highlights</p>
            <h2>Demo Evidence</h2>
          </div>
        </div>
        <div className="evidence-grid">
          {highlights.map((report) => (
            <article className="report-item evidence-item" key={report.path}>
              <div className="evidence-heading">
                <strong>{report.title}</strong>
                <span className={`status-pill ${statusTone[report.status] ?? "blue"}`}>{report.status}</span>
              </div>
              <span className="mono">{report.schema_version ?? report.path}</span>
              <dl className="evidence-summary">
                {(report.summary ?? []).slice(0, 4).map((item) => (
                  <div key={`${report.path}-${item.label}`}>
                    <dt>{item.label}</dt>
                    <dd>{item.value || "n/a"}</dd>
                  </div>
                ))}
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Artifacts</p>
            <h2>Report Registry</h2>
          </div>
          <select className="compact-select" onChange={(event) => setCategory(event.target.value)} value={category}>
            <option value="all">All categories</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Report</th>
                <th>Status</th>
                <th>Category</th>
                <th>Schema</th>
                <th>Path</th>
              </tr>
            </thead>
            <tbody>
              {reports.slice(0, 40).map((report) => (
                <tr key={report.path}>
                  <td>{report.title}</td>
                  <td>
                    <span className={`status-pill ${statusTone[report.status] ?? "blue"}`}>{report.status}</span>
                  </td>
                  <td>{report.category}</td>
                  <td className="mono">{report.schema_version ?? "raw-json"}</td>
                  <td className="mono">{report.path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function OptimizationPanelView({
  onSelectVariant,
  panel,
  selected
}: {
  onSelectVariant: (variant: string) => void;
  panel: OptimizationPanel;
  selected?: OptimizationVariant;
}) {
  const chartVariants = panel.variants.filter(
    (variant) => variant.quality_score !== undefined && variant.latency_p50_ms !== undefined
  );
  const maxQuality = Math.max(...chartVariants.map((variant) => variant.quality_score ?? 0), 1);
  const latencies = chartVariants.map((variant) => variant.latency_p50_ms ?? 0);
  const minLatency = latencies.length ? Math.min(...latencies) : 0;
  const maxLatency = Math.max(...latencies, 1);
  const latencyRange = Math.max(maxLatency - minLatency, 1);

  return (
    <section className="panel panel-wide">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Optimization frontier</p>
          <h2>Pareto, energy, leaderboard</h2>
        </div>
        <span className={`status-pill ${panel.carbon_gate_verdict === "pass" ? "green" : "red"}`}>
          carbon {panel.carbon_gate_verdict || "unknown"}
        </span>
      </div>
      <div className="metric-grid">
        <MetricTile label="Recommended" value={panel.recommended_variant || "-"} tone="green" />
        <MetricTile label="Greenest" value={panel.greenest_variant || "-"} tone="blue" />
        <MetricTile label="Judge" value={panel.judge_backend || "local"} tone="amber" />
        <MetricTile label="Variants" value={panel.variants.length} tone="blue" />
      </div>
      <div className="optimization-grid">
        <div className="pareto-chart" role="img" aria-label="Quality versus latency Pareto chart">
          <span className="chart-axis chart-y">Lower latency</span>
          <span className="chart-axis chart-x">Higher quality</span>
          {chartVariants.map((variant) => {
            const left = Math.max(4, Math.min(92, ((variant.quality_score ?? 0) / maxQuality) * 88 + 4));
            const bottom = Math.max(
              7,
              Math.min(88, (1 - ((variant.latency_p50_ms ?? maxLatency) - minLatency) / latencyRange) * 78 + 7)
            );
            const active = selected?.variant === variant.variant;
            return (
              <button
                aria-label={`Select ${variant.variant}`}
                className={`pareto-point ${variant.recommended ? "recommended" : ""} ${variant.pareto_frontier ? "frontier" : ""} ${active ? "active" : ""}`}
                key={variant.variant}
                onClick={() => onSelectVariant(variant.variant)}
                style={{ left: `${left}%`, bottom: `${bottom}%` }}
                title={`${variant.variant}: quality ${formatNumber(variant.quality_score)}, latency ${formatNumber(variant.latency_p50_ms)} ms`}
                type="button"
              >
                <span>{variant.variant}</span>
              </button>
            );
          })}
        </div>
        <div className="optimization-detail">
          <div className="evidence-heading">
            <strong>{selected?.variant ?? panel.recommended_variant}</strong>
            <span className={`status-pill ${selected?.slo_verdict === "fail" ? "red" : "green"}`}>
              {selected?.slo_verdict || "ranked"}
            </span>
          </div>
          <p className="muted-text">{selected?.adapter || panel.recommendation}</p>
          <dl className="evidence-summary">
            <div>
              <dt>rank</dt>
              <dd>{selected?.leaderboard_rank ?? "-"}</dd>
            </div>
            <div>
              <dt>quality</dt>
              <dd>{formatNumber(selected?.quality_score)}</dd>
            </div>
            <div>
              <dt>latency</dt>
              <dd>{formatNumber(selected?.latency_p50_ms)} ms</dd>
            </div>
            <div>
              <dt>VRAM</dt>
              <dd>{formatNumber(selected?.peak_vram_gb)} GB</dd>
            </div>
            <div>
              <dt>energy</dt>
              <dd>{formatNumber(selected?.energy_wh_per_1k_tokens)} Wh/1k tokens</dd>
            </div>
            <div>
              <dt>SCI</dt>
              <dd>{formatNumber(selected?.sci_g_per_1k_tokens)} gCO2e/1k</dd>
            </div>
          </dl>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Variant</th>
              <th>Rank</th>
              <th>Quality</th>
              <th>Latency</th>
              <th>VRAM</th>
              <th>Energy</th>
              <th>SCI</th>
              <th>Gate</th>
            </tr>
          </thead>
          <tbody>
            {panel.variants.map((variant) => (
              <tr key={variant.variant}>
                <td>
                  <strong>{variant.variant}</strong>
                  {variant.recommended ? <span className="status-pill green inline-pill">recommended</span> : null}
                  {variant.pareto_frontier ? <span className="status-pill blue inline-pill">frontier</span> : null}
                </td>
                <td>{variant.leaderboard_rank ?? "-"}</td>
                <td>{formatNumber(variant.quality_score)}</td>
                <td>{formatNumber(variant.latency_p50_ms)} ms</td>
                <td>{formatNumber(variant.peak_vram_gb)} GB</td>
                <td>{formatNumber(variant.energy_wh_per_1k_tokens)} Wh</td>
                <td>{formatNumber(variant.sci_g_per_1k_tokens)} gCO2e</td>
                <td>
                  <span className={`status-pill ${variant.slo_verdict === "fail" ? "red" : "green"}`}>
                    {variant.slo_verdict || "n/a"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatNumber(value?: number): string {
  if (value === undefined || Number.isNaN(value)) {
    return "-";
  }
  if (Math.abs(value) >= 100) {
    return value.toFixed(0);
  }
  return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
