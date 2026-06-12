import { Boxes } from "lucide-react";
import { releaseLanes } from "../data";
import { compactJson, stageTone } from "../format";
import type { ModelRecord } from "../types";

interface RegistryViewProps {
  models: ModelRecord[];
}

export function RegistryView({ models }: RegistryViewProps) {
  return (
    <section className="view-grid">
      <div className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Promotion state</p>
            <h2>Model registry</h2>
          </div>
          <Boxes aria-hidden="true" size={20} />
        </div>
        <div className="lane-grid">
          {releaseLanes.map((lane) => {
            const laneModels = models.filter((model) => model.stage === lane.stage);
            return (
              <div className={`release-lane ${lane.tone}`} key={lane.stage}>
                <div className="lane-title">
                  <span>{lane.name}</span>
                  <strong>{laneModels.length}</strong>
                </div>
                {laneModels.length === 0 ? (
                  <p className="empty-state">Empty</p>
                ) : (
                  laneModels.map((model) => (
                    <article className="model-row" key={model.id}>
                      <strong>{model.name}</strong>
                      <span>{model.workload} · {model.version || "unversioned"}</span>
                      <span className={`status-pill ${stageTone(model.stage)}`}>{model.stage}</span>
                    </article>
                  ))
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="panel">
        <div className="panel-header compact">
          <h2>Registry JSON</h2>
        </div>
        <pre className="json-box">{compactJson(models)}</pre>
      </div>
    </section>
  );
}
