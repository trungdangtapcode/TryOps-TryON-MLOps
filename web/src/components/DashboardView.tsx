import { Activity, Database, Gauge, RefreshCw } from "lucide-react";
import type { DashboardSummary, ModelRecord, QuotaReadModel, RequestRecord } from "../types";
import { formatNumber, formatOptionalMs, stageTone } from "../format";
import { MetricTile } from "./MetricTile";

interface DashboardViewProps {
  dashboard?: DashboardSummary;
  quota?: QuotaReadModel;
  models: ModelRecord[];
  requests: RequestRecord[];
  onRefresh: () => void;
}

export function DashboardView({ dashboard, quota, models, requests, onRefresh }: DashboardViewProps) {
  const recent = requests.slice(0, 6);
  const quotaSummary = quota?.summary;
  const topTenants = (quota?.tenants ?? [])
    .slice()
    .sort((left, right) => right.utilization_pct - left.utilization_pct)
    .slice(0, 3);
  return (
    <section className="view-grid dashboard-grid">
      <div className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Live rollup</p>
            <h2>Service posture</h2>
          </div>
          <button className="text-button" onClick={onRefresh} type="button">
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
        <div className="metric-grid">
          <MetricTile label="Requests" value={dashboard?.total_requests ?? 0} tone="blue" />
          <MetricTile label="LLM latency" value={formatOptionalMs(dashboard?.llm.avg_latency_ms)} tone="green" />
          <MetricTile label="VTON latency" value={formatOptionalMs(dashboard?.vton.avg_latency_ms)} tone="amber" />
          <MetricTile label="Feedback" value={dashboard?.feedback.count ?? 0} detail={`avg ${dashboard?.feedback.avg_rating ?? "-"}`} />
        </div>
      </div>

      <div className="panel">
        <div className="panel-header compact">
          <h2>Model stages</h2>
          <Database aria-hidden="true" size={18} />
        </div>
        <div className="stage-list">
          {Object.entries(dashboard?.models_by_stage ?? {}).length === 0 ? (
            <p className="empty-state">No registered models.</p>
          ) : (
            Object.entries(dashboard?.models_by_stage ?? {}).map(([stage, count]) => (
              <div className="stage-row" key={stage}>
                <span className={`status-pill ${stageTone(stage)}`}>{stage}</span>
                <strong>{count}</strong>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="panel panel-wide">
        <div className="panel-header compact">
          <h2>Recent requests</h2>
          <Activity aria-hidden="true" size={18} />
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Kind</th>
                <th>Model</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Trace</th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 ? (
                <tr>
                  <td colSpan={5}>No requests recorded.</td>
                </tr>
              ) : (
                recent.map((request) => (
                  <tr key={request.id}>
                    <td>{request.kind}</td>
                    <td>{request.model_alias || request.adapter || "-"}</td>
                    <td><span className="status-pill green">{request.status}</span></td>
                    <td>{formatOptionalMs(request.latency_ms)}</td>
                    <td className="mono">{request.trace_id?.slice(0, 12) || "-"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header compact">
          <h2>Quota</h2>
          <Gauge aria-hidden="true" size={18} />
        </div>
        <div className="capacity-stack">
          <MetricTile
            label="Tenants"
            value={quotaSummary?.tenants ?? 0}
            detail={`${quotaSummary?.at_risk_tenants ?? 0} at risk`}
            tone={(quotaSummary?.at_risk_tenants ?? 0) > 0 ? "amber" : "green"}
          />
          <MetricTile
            label="Used units"
            value={formatNumber(quotaSummary?.total_used)}
            detail={`limit ${formatNumber(quotaSummary?.total_limit)}`}
            tone="blue"
          />
          <MetricTile
            label="Showback"
            value={formatUsd(quotaSummary?.showback_usd)}
            detail={quotaSummary?.native_source ? "native ledger" : "runtime fallback"}
            tone={quotaSummary?.native_source ? "green" : "amber"}
          />
          <MetricTile label="Models" value={models.length} detail="registry rows" />
          {topTenants.length === 0 ? (
            <p className="empty-state">No quota tenants.</p>
          ) : (
            <div className="stage-list">
              {topTenants.map((tenant) => (
                <div className="stage-row" key={`${tenant.period}-${tenant.user_hash}`}>
                  <span className={`status-pill ${riskTone(tenant.risk)}`}>{tenant.risk}</span>
                  <span className="mono">{tenant.user_hash.slice(0, 12)}</span>
                  <strong>{formatNumber(tenant.utilization_pct)}%</strong>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function formatUsd(value?: number | null): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 4, minimumFractionDigits: 2 })}`;
}

function riskTone(risk: string): "green" | "amber" | "blue" | "red" | "neutral" {
  if (risk === "exhausted" || risk === "high") {
    return "red";
  }
  if (risk === "medium") {
    return "amber";
  }
  if (risk === "low") {
    return "green";
  }
  return "blue";
}
