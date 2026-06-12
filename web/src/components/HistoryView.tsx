import { useState } from "react";
import { Search } from "lucide-react";
import type { TryOpsClient } from "../api";
import { formatOptionalMs } from "../format";
import type { RequestRecord } from "../types";

interface HistoryViewProps {
  client: TryOpsClient;
  requests: RequestRecord[];
  onRefresh: () => void;
}

export function HistoryView({ client, requests, onRefresh }: HistoryViewProps) {
  const [kind, setKind] = useState("all");
  const [filtered, setFiltered] = useState<RequestRecord[] | undefined>();

  async function filterHistory(nextKind: string) {
    setKind(nextKind);
    setFiltered(await client.history(nextKind));
  }

  const rows = filtered ?? requests;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Request ledger</p>
          <h2>History</h2>
        </div>
        <div className="segmented">
          {["all", "llm", "vton"].map((value) => (
            <button
              className={kind === value ? "active" : ""}
              key={value}
              onClick={() => void filterHistory(value)}
              type="button"
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Created</th>
              <th>Kind</th>
              <th>Model</th>
              <th>Status</th>
              <th>Latency</th>
              <th>Trace</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <span className="empty-inline"><Search aria-hidden="true" size={16} /> No requests found.</span>
                </td>
              </tr>
            ) : (
              rows.map((request) => (
                <tr key={request.id}>
                  <td>{new Date(request.created_at).toLocaleString()}</td>
                  <td>{request.kind}</td>
                  <td>{request.model_alias || request.adapter || "-"}</td>
                  <td><span className="status-pill green">{request.status}</span></td>
                  <td>{formatOptionalMs(request.latency_ms)}</td>
                  <td className="mono">{request.trace_id || request.request_id || "-"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <button className="text-button table-action" onClick={onRefresh} type="button">Refresh history</button>
    </section>
  );
}
