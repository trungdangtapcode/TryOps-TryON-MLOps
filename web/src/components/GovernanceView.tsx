import { useMemo, useState } from "react";
import { GitBranch, Search } from "lucide-react";
import type { TryOpsClient } from "../api";
import { compactJson, stageTone } from "../format";
import type { ModelRecord, RequestRecord } from "../types";

interface GovernanceViewProps {
  client: TryOpsClient;
  requests: RequestRecord[];
  models: ModelRecord[];
}

export function GovernanceView({ client, requests, models }: GovernanceViewProps) {
  const [selectedId, setSelectedId] = useState(requests[0]?.id ?? "");
  const [lineage, setLineage] = useState<Record<string, unknown> | undefined>();
  const [error, setError] = useState<string | undefined>();

  const signedModels = useMemo(() => models.filter((model) => Boolean(model.signed)), [models]);

  async function loadLineage() {
    if (!selectedId.trim()) {
      return;
    }
    setError(undefined);
    try {
      setLineage(await client.lineage(selectedId.trim()));
    } catch (lineageError) {
      setError(lineageError instanceof Error ? lineageError.message : "Lineage lookup failed");
    }
  }

  return (
    <section className="view-grid">
      <div className="panel">
        <div className="panel-header compact">
          <h2>Lineage lookup</h2>
          <GitBranch aria-hidden="true" size={18} />
        </div>
        <label className="field stacked">
          <span>Request ID</span>
          <input
            list="request-ids"
            onChange={(event) => setSelectedId(event.target.value)}
            value={selectedId}
          />
        </label>
        <datalist id="request-ids">
          {requests.map((request) => (
            <option key={request.id} value={request.id} />
          ))}
        </datalist>
        <button className="primary-button full-width" onClick={() => void loadLineage()} type="button">
          <Search aria-hidden="true" size={17} />
          Inspect
        </button>
        {error ? <div className="error-box">{error}</div> : null}
      </div>

      <div className="panel panel-wide">
        <div className="panel-header compact">
          <h2>Evidence</h2>
        </div>
        <pre className="json-box tall">{lineage ? compactJson(lineage) : "{}"}</pre>
      </div>

      <div className="panel">
        <div className="panel-header compact">
          <h2>Signed artifacts</h2>
        </div>
        <div className="stage-list">
          {signedModels.length === 0 ? (
            <p className="empty-state">No signed models.</p>
          ) : (
            signedModels.map((model) => (
              <div className="stage-row" key={model.id}>
                <span>{model.name}</span>
                <span className={`status-pill ${stageTone(model.stage)}`}>{model.stage}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
