import { CheckCircle2, FileCheck2, Network, ShieldCheck, WifiOff } from "lucide-react";
import { useMemo, useState } from "react";
import { professorDemoMetrics, professorDemoSteps } from "../data";
import type { ProfessorDemoStep } from "../types";
import { MetricTile } from "./MetricTile";

export function ProfessorDemoView() {
  const [selectedStepId, setSelectedStepId] = useState(professorDemoSteps[0]?.id ?? "");
  const selectedStep = professorDemoSteps.find((step) => step.id === selectedStepId) ?? professorDemoSteps[0];
  const seededArtifacts = useMemo(
    () => Array.from(new Set(professorDemoSteps.flatMap((step) => step.artifacts))).slice(0, 12),
    []
  );

  return (
    <section className="view-grid demo-grid">
      <div className="panel demo-overview">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Seeded offline walkthrough</p>
            <h2>Professor demo runbook</h2>
          </div>
          <div className="demo-mode-flags" aria-label="Demo execution constraints">
            <span className="status-pill green">
              <WifiOff aria-hidden="true" size={15} />
              no network
            </span>
            <span className="status-pill green">
              <Network aria-hidden="true" size={15} />
              no GPU
            </span>
            <span className="status-pill blue">
              <ShieldCheck aria-hidden="true" size={15} />
              seeded evidence
            </span>
          </div>
        </div>
        <div className="metric-grid">
          {professorDemoMetrics.map((metric) => (
            <MetricTile
              detail={metric.detail}
              key={metric.label}
              label={metric.label}
              tone={metric.tone}
              value={metric.value}
            />
          ))}
        </div>
      </div>

      <div className="panel demo-rail">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Walkthrough</p>
            <h2>Demo Steps</h2>
          </div>
          <span className="status-pill green">{professorDemoSteps.length}/7 ready</span>
        </div>
        <div className="demo-step-list">
          {professorDemoSteps.map((step) => (
            <DemoStepButton
              key={step.id}
              onSelect={() => setSelectedStepId(step.id)}
              selected={step.id === selectedStep.id}
              step={step}
            />
          ))}
        </div>
      </div>

      <div className="panel demo-main">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{selectedStep.track}</p>
            <h2>{selectedStep.title}</h2>
          </div>
          <span className={`status-pill ${selectedStep.tone}`}>{selectedStep.status}</span>
        </div>

        <div className="demo-operator-strip">
          <CheckCircle2 aria-hidden="true" size={19} />
          <div>
            <strong>{selectedStep.summary}</strong>
            <span>{selectedStep.operatorLine}</span>
          </div>
        </div>

        <div className="metric-grid demo-selected-metrics">
          {selectedStep.metrics.map((metric) => (
            <MetricTile
              detail={metric.detail}
              key={metric.label}
              label={metric.label}
              tone={metric.tone}
              value={metric.value}
            />
          ))}
        </div>

        <div className="demo-detail-grid">
          <div className="demo-script">
            {selectedStep.transcript.map((line, index) => (
              <div className="decision-row demo-transcript-row" key={line}>
                <span className="status-pill green">{String(index + 1).padStart(2, "0")}</span>
                <strong>{line}</strong>
              </div>
            ))}
          </div>
          <div className="demo-command-box">
            <span>Command</span>
            <strong className="mono">{selectedStep.command}</strong>
            <span>Primary artifact</span>
            <strong className="mono">{selectedStep.primaryArtifact}</strong>
          </div>
        </div>
      </div>

      <div className="panel demo-evidence-panel">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Local proof</p>
            <h2>Seeded Artifacts</h2>
          </div>
          <FileCheck2 aria-hidden="true" size={18} />
        </div>
        <div className="demo-artifact-list">
          {seededArtifacts.map((path) => (
            <div className="report-item demo-artifact" key={path}>
              <span>artifact</span>
              <strong className="mono">{path}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function DemoStepButton({
  onSelect,
  selected,
  step
}: {
  onSelect: () => void;
  selected: boolean;
  step: ProfessorDemoStep;
}) {
  return (
    <button
      className={selected ? "demo-step-button active" : "demo-step-button"}
      onClick={onSelect}
      title={step.title}
      type="button"
    >
      <span className="demo-step-index">{step.order}</span>
      <span className="demo-step-copy">
        <strong>{step.title}</strong>
        <small>{step.track}</small>
      </span>
      <span className={`status-pill ${step.tone}`}>{step.status}</span>
    </button>
  );
}
