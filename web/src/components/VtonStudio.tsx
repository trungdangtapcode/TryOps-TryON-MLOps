import { useEffect, useMemo, useState } from "react";
import { ImagePlus, Play } from "lucide-react";
import type { TryOpsClient } from "../api";
import { quotaPlans, vtonAliases } from "../data";
import { compactJson, formatNumber, formatOptionalMs } from "../format";
import type { VtonComparisonReport, VtonComparisonRun, VtonResponse } from "../types";
import { MetricTile } from "./MetricTile";

interface VtonStudioProps {
  client: TryOpsClient;
  onMutate: () => void;
}

export function VtonStudio({ client, onMutate }: VtonStudioProps) {
  const [personPath, setPersonPath] = useState("artifacts/demo/vton/person.png");
  const [garmentPath, setGarmentPath] = useState("artifacts/demo/vton/garment.png");
  const [outputPath, setOutputPath] = useState("artifacts/runtime/vton/console-output.png");
  const [modelAlias, setModelAlias] = useState("champion");
  const [quotaPlan, setQuotaPlan] = useState("free");
  const [personPreview, setPersonPreview] = useState<string | undefined>();
  const [garmentPreview, setGarmentPreview] = useState<string | undefined>();
  const [result, setResult] = useState<VtonResponse | undefined>();
  const [comparison, setComparison] = useState<VtonComparisonReport | undefined>();
  const [comparisonError, setComparisonError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);

  const reportEntries = useMemo(() => Object.entries(result?.report ?? {}).slice(0, 6), [result]);
  const comparisonRuns = useMemo(() => comparison?.runs.slice(0, 2) ?? [], [comparison]);

  useEffect(() => {
    let cancelled = false;
    setComparisonError(undefined);
    client.vtonComparison()
      .then((response) => {
        if (!cancelled) {
          setComparison(response);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setComparisonError(error instanceof Error ? error.message : "VTON comparison unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  async function runVton() {
    setBusy(true);
    setResult(undefined);
    try {
      const response = await client.runVton({
        person_image_path: personPath,
        garment_image_path: garmentPath,
        output_image_path: outputPath,
        model_alias: modelAlias,
        user_id: "console-user",
        quota_plan: quotaPlan
      });
      setResult(response);
      onMutate();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workbench-grid">
      <form
        className="panel workbench-primary"
        onSubmit={(event) => {
          event.preventDefault();
          void runVton();
        }}
      >
        <div className="panel-header">
          <div>
            <p className="eyebrow">VTON request</p>
            <h2>Studio</h2>
          </div>
          <button className="primary-button" disabled={busy} type="submit">
            <Play aria-hidden="true" size={17} />
            {busy ? "Running" : "Run"}
          </button>
        </div>
        <div className="image-input-grid">
          <AssetInput
            label="Person"
            path={personPath}
            preview={personPreview}
            onPathChange={setPersonPath}
            onPreviewChange={setPersonPreview}
          />
          <AssetInput
            label="Garment"
            path={garmentPath}
            preview={garmentPreview}
            onPathChange={setGarmentPath}
            onPreviewChange={setGarmentPreview}
          />
        </div>
        <div className="form-grid">
          <label className="field">
            <span>Model</span>
            <select onChange={(event) => setModelAlias(event.target.value)} value={modelAlias}>
              {vtonAliases.map((alias) => (
                <option key={alias} value={alias}>{alias}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Quota plan</span>
            <select onChange={(event) => setQuotaPlan(event.target.value)} value={quotaPlan}>
              {quotaPlans.map((plan) => (
                <option key={plan} value={plan}>{plan}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Output path</span>
            <input onChange={(event) => setOutputPath(event.target.value)} value={outputPath} />
          </label>
        </div>
      </form>

      <aside className="panel">
        <div className="panel-header compact">
          <h2>Run status</h2>
        </div>
        <div className="capacity-stack">
          <MetricTile label="Status" value={result?.status || "idle"} tone={result?.error ? "red" : "green"} />
          <MetricTile label="Quota" value={result?.quota?.allowed === false ? "blocked" : "allowed"} />
          <MetricTile label="Trace" value={result?.trace?.trace_id?.slice(0, 10) || "-"} />
        </div>
      </aside>

      <section className="panel workbench-output">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Evaluation gallery</p>
            <h2>Side-by-side outputs</h2>
          </div>
          <span className="mono">{comparison?.schema_version || "-"}</span>
        </div>
        {comparisonError ? <div className="error-box">{comparisonError}</div> : null}
        <div className="comparison-strip source-strip">
          <ComparisonImage
            label="Person"
            metric="input"
            src={client.artifactUrl(comparison?.person_image_path_url ?? comparison?.person_image_path)}
          />
          <ComparisonImage
            label="Garment"
            metric="input"
            src={client.artifactUrl(comparison?.garment_image_path_url ?? comparison?.garment_image_path)}
          />
        </div>
        <div className="comparison-strip output-strip">
          {comparisonRuns.length === 0 ? (
            <p className="empty-state">No comparison outputs found.</p>
          ) : (
            comparisonRuns.map((run) => (
              <ComparisonRunCard
                key={run.name}
                run={run}
                src={client.artifactUrl(run.output_url ?? run.output_path)}
                winner={run.name === comparison?.winner_by_structural_similarity}
              />
            ))
          )}
        </div>
      </section>

      <section className="panel workbench-output">
        <div className="panel-header compact">
          <h2>Report</h2>
          <span className="mono">{result?.request_id || "-"}</span>
        </div>
        {result?.error ? <div className="error-box">{result.error.code}: {result.error.message}</div> : null}
        <div className="report-grid">
          {reportEntries.length === 0 ? (
            <p className="empty-state">No report yet.</p>
          ) : (
            reportEntries.map(([key, value]) => (
              <div className="report-item" key={key}>
                <span>{key}</span>
                <strong>{typeof value === "object" ? JSON.stringify(value) : String(value)}</strong>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header compact">
          <h2>Raw contract</h2>
        </div>
        <pre className="json-box">{result ? compactJson(result) : "{}"}</pre>
      </section>
    </section>
  );
}

interface ComparisonImageProps {
  label: string;
  metric: string;
  src?: string;
}

function ComparisonImage({ label, metric, src }: ComparisonImageProps) {
  return (
    <article className="comparison-card">
      <div className="comparison-frame">
        {src ? <img alt={`${label} artifact`} src={src} /> : <ImagePlus aria-hidden="true" size={28} />}
      </div>
      <div className="comparison-meta">
        <strong>{label}</strong>
        <span>{metric}</span>
      </div>
    </article>
  );
}

interface ComparisonRunCardProps {
  run: VtonComparisonRun;
  src?: string;
  winner: boolean;
}

function ComparisonRunCard({ run, src, winner }: ComparisonRunCardProps) {
  const proxyScore = run.garment_similarity?.proxy?.score;
  const structural = run.metrics_against_person?.global_ssim_luma;
  const labels = run.failure_labels ?? [];
  return (
    <article className="comparison-card result-card">
      <div className="comparison-frame">
        {src ? <img alt={`${run.name} VTON output`} src={src} /> : <ImagePlus aria-hidden="true" size={28} />}
      </div>
      <div className="comparison-meta">
        <strong>{run.name}</strong>
        <span>{winner ? "winner" : "candidate"}</span>
      </div>
      <dl className="comparison-metrics">
        <div>
          <dt>Latency</dt>
          <dd>{formatOptionalMs(run.latency_ms)}</dd>
        </div>
        <div>
          <dt>Garment</dt>
          <dd>{formatNumber(proxyScore)}</dd>
        </div>
        <div>
          <dt>SSIM</dt>
          <dd>{formatNumber(structural)}</dd>
        </div>
      </dl>
      <div className="failure-list">
        {labels.length === 0 ? (
          <span className="status-pill green">clear</span>
        ) : (
          labels.slice(0, 3).map((label) => (
            <span className="status-pill amber" key={label}>{label}</span>
          ))
        )}
      </div>
    </article>
  );
}

interface AssetInputProps {
  label: string;
  path: string;
  preview?: string;
  onPathChange: (value: string) => void;
  onPreviewChange: (value?: string) => void;
}

function AssetInput({ label, path, preview, onPathChange, onPreviewChange }: AssetInputProps) {
  return (
    <div className="asset-input">
      <div className="asset-preview">
        {preview ? <img alt={`${label} preview`} src={preview} /> : <ImagePlus aria-hidden="true" size={34} />}
      </div>
      <label className="field stacked">
        <span>{label} path</span>
        <input onChange={(event) => onPathChange(event.target.value)} value={path} />
      </label>
      <label className="file-button">
        <ImagePlus aria-hidden="true" size={16} />
        Preview
        <input
          accept="image/png,image/jpeg"
          onChange={(event) => {
            const file = event.target.files?.[0];
            onPreviewChange(file ? URL.createObjectURL(file) : undefined);
          }}
          type="file"
        />
      </label>
    </div>
  );
}
