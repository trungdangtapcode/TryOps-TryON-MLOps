import { useEffect, useMemo, useState, type DragEvent } from "react";
import { ImagePlus, Loader2, Play, Settings2, UploadCloud } from "lucide-react";
import type { TryOpsClient } from "../api";
import { quotaPlans, vtonAliases } from "../data";
import { compactJson } from "../format";
import type { JobConcurrency, RequestRecord, VtonJobRecord, VtonResponse } from "../types";
import { isActiveVtonJob, JobStatusList } from "./JobStatusList";
import { MetricTile } from "./MetricTile";
import { RecentTryOnGallery } from "./RecentTryOnGallery";

interface VtonStudioProps {
  client: TryOpsClient;
  onMutate: () => void;
  activeJobs?: VtonJobRecord[];
  jobConcurrency?: JobConcurrency;
  recentRequests?: RequestRecord[];
}

export function VtonStudio({
  client,
  onMutate,
  activeJobs = [],
  jobConcurrency,
  recentRequests = []
}: VtonStudioProps) {
  const [personPath, setPersonPath] = useState("");
  const [garmentPath, setGarmentPath] = useState("");
  const [outputPath, setOutputPath] = useState("artifacts/runtime/vton/studio-output.png");
  const [modelAlias, setModelAlias] = useState("champion");
  const [quotaPlan, setQuotaPlan] = useState("team");
  const [category, setCategory] = useState<VtonCategory>("tops");
  const [garmentPhotoType, setGarmentPhotoType] = useState<VtonGarmentPhotoType>("model");
  const [quality, setQuality] = useState<VtonQuality>("best");
  const [personPreview, setPersonPreview] = useState<string | undefined>();
  const [garmentPreview, setGarmentPreview] = useState<string | undefined>();
  const [personUploadBusy, setPersonUploadBusy] = useState(false);
  const [garmentUploadBusy, setGarmentUploadBusy] = useState(false);
  const [personUploadError, setPersonUploadError] = useState<string | undefined>();
  const [garmentUploadError, setGarmentUploadError] = useState<string | undefined>();
  const [result, setResult] = useState<VtonResponse | undefined>();
  const [trackedJob, setTrackedJob] = useState<VtonJobRecord | undefined>();
  const [pollingJobId, setPollingJobId] = useState<string | undefined>();
  const [resultObjectUrl, setResultObjectUrl] = useState<string | undefined>();
  const [runError, setRunError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);

  const reportEntries = useMemo(() => Object.entries(result?.report ?? {}).slice(0, 6), [result]);
  const uploadBusy = personUploadBusy || garmentUploadBusy;
  const hasPersonAsset = Boolean(personPath.trim());
  const hasGarmentAsset = Boolean(garmentPath.trim());
  const hasRequiredAssets = hasPersonAsset && hasGarmentAsset;
  const runOutputPath = vtonOutputPath(result, outputPath);
  const runOutputUrl = client.artifactUrl(runOutputPath);
  const visibleJobs = useMemo(() => mergeJobs(activeJobs, trackedJob), [activeJobs, trackedJob]);
  const activeJobCount = visibleJobs.filter(isActiveVtonJob).length;
  const concurrencyActive = Math.max(jobConcurrency?.active ?? 0, activeJobCount);
  const concurrencyLimit = jobConcurrency?.limit;
  const concurrencyRemaining = concurrencyLimit === undefined ? undefined : Math.max(0, concurrencyLimit - concurrencyActive);
  const concurrencyLimited = concurrencyLimit !== undefined && concurrencyRemaining === 0 && !busy;
  const runDisabled = busy || uploadBusy || !hasRequiredAssets || concurrencyLimited;
  const runButtonLabel = busy
    ? "Rendering"
    : concurrencyLimited
      ? "Limit reached"
      : hasRequiredAssets
        ? "Generate"
        : "Upload first";
  const resultImageUrl = resultObjectUrl ?? cacheBustedUrl(runOutputUrl, result?.request_id);
  const personImageUrl = personPreview ?? (hasPersonAsset ? client.artifactUrl(personPath) : undefined);
  const garmentImageUrl = garmentPreview ?? (hasGarmentAsset ? client.artifactUrl(garmentPath) : undefined);
  const stageImageUrl = resultImageUrl ?? personImageUrl;
  const runModel = vtonModelSummary(result);
  const qualityConfig = qualitySettings[quality];
  const resultStatus = busy ? trackedJob?.status ?? "running" : result?.status ?? "ready";
  const statusTone = runError || result?.error
    ? "red"
    : result?.status === "completed"
      ? "green"
      : busy
        ? "blue"
        : "green";

  useEffect(() => {
    let revokedUrl: string | undefined;
    let cancelled = false;
    setResultObjectUrl(undefined);
    if (!runOutputPath || result?.error || result?.status !== "completed") {
      return undefined;
    }
    void client.artifactObjectUrl(runOutputPath).then((url) => {
      if (cancelled) {
        if (url) {
          URL.revokeObjectURL(url);
        }
        return;
      }
      revokedUrl = url;
      setResultObjectUrl(url);
    });
    return () => {
      cancelled = true;
      if (revokedUrl) {
        URL.revokeObjectURL(revokedUrl);
      }
    };
  }, [client, result?.error, result?.request_id, result?.status, runOutputPath]);

  useEffect(() => {
    const nextActiveJob = activeJobs.find(isActiveVtonJob);
    if (!pollingJobId && nextActiveJob) {
      setTrackedJob(nextActiveJob);
      setPollingJobId(nextActiveJob.job_id);
      setBusy(true);
      setRunError(undefined);
    }
  }, [activeJobs, pollingJobId]);

  useEffect(() => {
    if (!pollingJobId) {
      return undefined;
    }
    const jobId = pollingJobId;
    let cancelled = false;
    async function pollJob() {
      for (let attempt = 0; attempt < 180 && !cancelled; attempt += 1) {
        try {
          const snapshot = await client.vtonJob(jobId);
          if (cancelled) {
            return;
          }
          setTrackedJob(snapshot);
          if (snapshot.status === "completed" || snapshot.status === "failed") {
            setPollingJobId(undefined);
            setBusy(false);
            if (snapshot.result) {
              setResult(snapshot.result);
              if (snapshot.result.status === "completed") {
                setRunError(undefined);
              } else if (snapshot.result.error) {
                setRunError(`${snapshot.result.error.code}: ${snapshot.result.error.message}`);
              }
            } else if (snapshot.error?.message) {
              setRunError(snapshot.error.message);
            }
            onMutate();
            return;
          }
        } catch (error: unknown) {
          if (cancelled) {
            return;
          }
          if (isRecoverablePollingError(error)) {
            setRunError(undefined);
            setBusy(true);
            await delay(2000);
            continue;
          }
          setRunError(error instanceof Error ? error.message : "Could not poll running job");
          setBusy(false);
          setPollingJobId(undefined);
          return;
        }
        await delay(2000);
      }
      if (!cancelled) {
        setPollingJobId(undefined);
        setBusy(false);
        setRunError("The job is still running, but polling timed out. Refresh the page to check it again.");
      }
    }
    void pollJob();
    return () => {
      cancelled = true;
    };
  }, [client, onMutate, pollingJobId]);

  async function runVton() {
    if (!hasRequiredAssets) {
      setResult(undefined);
      setRunError("Upload a model photo and garment photo before generating.");
      setPersonUploadError(hasPersonAsset ? undefined : "Upload a model photo first.");
      setGarmentUploadError(hasGarmentAsset ? undefined : "Upload a garment photo first.");
      return;
    }
    if (concurrencyLimited) {
      setRunError(
        `This ${jobConcurrency?.plan ?? "workspace"} workspace is already using ${concurrencyActive} / ${concurrencyLimit} VTON job slots. Wait for one to finish.`
      );
      return;
    }
    setBusy(true);
    setResult(undefined);
    setTrackedJob(undefined);
    setRunError(undefined);
    try {
      const accepted = await client.submitVtonJob({
        person_image_path: personPath,
        garment_image_path: garmentPath,
        output_image_path: outputPath,
        model_alias: modelAlias,
        user_id: "studio-user",
        quota_plan: quotaPlan,
        category,
        garment_photo_type: garmentPhotoType,
        num_timesteps: qualityConfig.numTimesteps,
        guidance_scale: qualityConfig.guidanceScale,
        seed: 555,
        segmentation_free: true,
        timeout_ms: 300000
      });
      setTrackedJob(accepted);
      setPollingJobId(accepted.job_id);
      onMutate();
    } catch (error: unknown) {
      setRunError(error instanceof Error ? error.message : "Try-on run failed");
      setBusy(false);
    }
  }

  async function uploadAsset(role: VtonUploadRole, file: File) {
    const setUploadBusy = role === "person" ? setPersonUploadBusy : setGarmentUploadBusy;
    const setUploadError = role === "person" ? setPersonUploadError : setGarmentUploadError;
    const setPath = role === "person" ? setPersonPath : setGarmentPath;
    const setPreview = role === "person" ? setPersonPreview : setGarmentPreview;

    setUploadError(undefined);
    if (!client.hasCredentials()) {
      setUploadError("Sign in or enter a local demo API key before uploading.");
      return;
    }
    if (!isSupportedImageFile(file)) {
      setUploadError("Upload a PNG, JPEG, or WebP image.");
      return;
    }

    setUploadBusy(true);
    setResult(undefined);
    setRunError(undefined);
    try {
      const dataUrl = await imageFileToPngDataUrl(file);
      const response = await client.uploadVtonImage({
        role,
        filename: file.name || `${role}.png`,
        data_url: dataUrl
      });
      if (!response.data?.path || response.status === "rejected") {
        throw new Error(uploadErrorMessage(response.error?.code, response.error?.message));
      }
      setPath(response.data.path);
      setPreview(dataUrl);
      onMutate();
    } catch (error: unknown) {
      setUploadError(error instanceof Error ? error.message : "Image upload failed");
    } finally {
      setUploadBusy(false);
    }
  }

  return (
    <section className="fashion-studio">
      <form
        className="fashion-layout"
        onSubmit={(event) => {
          event.preventDefault();
          void runVton();
        }}
      >
        <section className="fashion-stage-card">
          <div className="fashion-kicker">
            <span>Atelier session</span>
            <span>Look 01</span>
          </div>
          <div className="fashion-stage-copy">
            <p>AI fitting room</p>
            <h2>{result?.status === "completed" ? "The look is ready." : "Compose the silhouette."}</h2>
          </div>
          <div className={`fashion-canvas${resultImageUrl ? " has-result" : ""}`}>
            {busy ? (
              <div className="fashion-processing">
                <Loader2 aria-hidden="true" className="spin" size={30} />
                <span>Rendering look</span>
              </div>
            ) : stageImageUrl ? (
              <img alt={resultImageUrl ? "Generated virtual try-on result" : "Selected person"} src={stageImageUrl} />
            ) : (
              <div className="fashion-empty-canvas">
                <ImagePlus aria-hidden="true" size={42} />
                <span>Upload a model photo to begin</span>
              </div>
            )}
            {garmentImageUrl ? (
              <figure className="fashion-floating-garment">
                <img alt="Selected garment" src={garmentImageUrl} />
                <figcaption>Selected piece</figcaption>
              </figure>
            ) : null}
          </div>
          <div className="fashion-stage-footer">
            <span className={`fashion-status ${statusTone}`}>{resultStatus}</span>
            <span>{runModel.isBaseline ? "Diagnostic preview" : "FASHN VTON 1.5"}</span>
          </div>
          {runError ? <div className="error-box">{runError}</div> : null}
          {result?.error ? <div className="error-box">{result.error.code}: {result.error.message}</div> : null}
          {runModel.isBaseline ? (
            <div className="warning-box">
              This run used the diagnostic compositor instead of neural VTON inference.
            </div>
          ) : null}
        </section>

        <aside className="fashion-control-panel">
          <div className="fashion-panel-heading">
            <div>
              <p>Fitting room</p>
              <h3>Style the frame</h3>
            </div>
            <button className="fashion-run-button" disabled={runDisabled} type="submit">
              {busy ? <Loader2 aria-hidden="true" className="spin" size={18} /> : <Play aria-hidden="true" size={18} />}
              {runButtonLabel}
            </button>
          </div>

          <div className="fashion-upload-grid">
            <AssetInput
              label="Model"
              path={personPath}
              preview={personImageUrl}
              uploading={personUploadBusy}
              error={personUploadError}
              onFileUpload={(file) => uploadAsset("person", file)}
            />
            <AssetInput
              label="Piece"
              path={garmentPath}
              preview={garmentImageUrl}
              uploading={garmentUploadBusy}
              error={garmentUploadError}
              onFileUpload={(file) => uploadAsset("garment", file)}
            />
          </div>

          <div className="fashion-controls">
            <SegmentedControl
              label="Garment"
              options={categoryOptions}
              value={category}
              onChange={setCategory}
            />
            <SegmentedControl
              label="Source"
              options={garmentPhotoTypeOptions}
              value={garmentPhotoType}
              onChange={setGarmentPhotoType}
            />
            <SegmentedControl
              label="Finish"
              options={qualityOptions}
              value={quality}
              onChange={setQuality}
            />
          </div>

            <div className="fashion-look-strip" aria-label="Current styling selection">
            <div>
              <span>Model</span>
              <strong>{personUploadBusy ? "Uploading" : hasPersonAsset ? "Selected" : "Needed"}</strong>
            </div>
            <div>
              <span>Piece</span>
              <strong>{garmentUploadBusy ? "Uploading" : hasGarmentAsset ? "Selected" : "Needed"}</strong>
            </div>
              <div>
                <span>Finish</span>
                <strong>{quality === "best" ? "Editorial" : "Daily"}</strong>
              </div>
              <div>
                <span>Slots</span>
                <strong>{concurrencyLimit === undefined ? `${activeJobCount} active` : `${concurrencyActive}/${concurrencyLimit}`}</strong>
              </div>
            </div>

          <details className="fashion-advanced">
            <summary>
              <Settings2 aria-hidden="true" size={17} />
              Studio settings
            </summary>
            <div className="form-grid">
              <label className="field">
                <span>Execution target</span>
                <select onChange={(event) => setModelAlias(event.target.value)} value={modelAlias}>
                  {vtonAliases.map((alias) => (
                    <option key={alias.value} value={alias.value}>{alias.label}</option>
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
            <div className="tryon-detail-grid">
              <MetricTile label="Status" value={result?.status || "idle"} tone={result?.error ? "red" : "green"} />
              <MetricTile label="Quota" value={result?.quota?.allowed === false ? "blocked" : "allowed"} />
              <MetricTile label="Adapter" value={runModel.adapter} tone={runModel.isBaseline ? "amber" : "green"} />
              <MetricTile label="Model type" value={runModel.type} tone={runModel.isBaseline ? "amber" : "green"} />
              <MetricTile label="Trace" value={result?.trace?.trace_id?.slice(0, 10) || "-"} />
            </div>
            <div className="asset-current">
              <span>Person asset</span>
              <strong title={personPath || "Upload required"}>{personPath || "Upload required"}</strong>
            </div>
            <div className="asset-current">
              <span>Garment asset</span>
              <strong title={garmentPath || "Upload required"}>{garmentPath || "Upload required"}</strong>
            </div>
            <div className="asset-current">
              <span>Saved result</span>
              <strong title={runOutputPath ?? outputPath}>{runOutputPath ?? outputPath}</strong>
            </div>
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
            <pre className="json-box">{result ? compactJson(result) : "{}"}</pre>
          </details>
        </aside>
      </form>
      <section className="fashion-job-feed" aria-label="Running try-on jobs">
        <div className="fashion-saved-heading">
          <div>
            <p>Work in progress</p>
            <h3>Running jobs</h3>
          </div>
          <span className="status-pill blue">
            {concurrencyLimit === undefined ? `${activeJobCount} active` : `${concurrencyActive} / ${concurrencyLimit} active`}
          </span>
        </div>
        {jobConcurrency ? (
          <p className="job-concurrency-note">
            {jobConcurrency.plan} plan capacity · {concurrencyRemaining ?? jobConcurrency.remaining} slot{(concurrencyRemaining ?? jobConcurrency.remaining) === 1 ? "" : "s"} available · {jobConcurrency.global_workers ?? 1} global worker{jobConcurrency.global_workers === 1 ? "" : "s"}
          </p>
        ) : null}
        <JobStatusList client={client} jobs={visibleJobs} emptyText="No active generation jobs." />
      </section>
      <section className="fashion-saved-looks" aria-label="Saved looks">
        <div className="fashion-saved-heading">
          <div>
            <p>My wardrobe</p>
            <h3>Saved looks</h3>
          </div>
        </div>
        <RecentTryOnGallery client={client} requests={recentRequests} />
      </section>
    </section>
  );
}

interface SegmentedOption<T extends string> {
  label: string;
  value: T;
}

interface SegmentedControlProps<T extends string> {
  label: string;
  options: Array<SegmentedOption<T>>;
  value: T;
  onChange: (value: T) => void;
}

function SegmentedControl<T extends string>({ label, options, value, onChange }: SegmentedControlProps<T>) {
  return (
    <div className="tryon-control-group">
      <span>{label}</span>
      <div className="segmented tryon-segmented">
        {options.map((option) => (
          <button
            className={option.value === value ? "active" : ""}
            key={option.value}
            onClick={() => onChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

type VtonCategory = "tops" | "bottoms" | "one-pieces";
type VtonGarmentPhotoType = "model" | "flat-lay";
type VtonQuality = "standard" | "best";

const categoryOptions: Array<SegmentedOption<VtonCategory>> = [
  { value: "tops", label: "Tops" },
  { value: "bottoms", label: "Bottoms" },
  { value: "one-pieces", label: "One-piece" }
];

const garmentPhotoTypeOptions: Array<SegmentedOption<VtonGarmentPhotoType>> = [
  { value: "model", label: "On model" },
  { value: "flat-lay", label: "Flat lay" }
];

const qualityOptions: Array<SegmentedOption<VtonQuality>> = [
  { value: "standard", label: "Standard" },
  { value: "best", label: "Best" }
];

const qualitySettings: Record<VtonQuality, { numTimesteps: number; guidanceScale: number }> = {
  standard: { numTimesteps: 28, guidanceScale: 1.5 },
  best: { numTimesteps: 50, guidanceScale: 1.5 }
};

function cacheBustedUrl(url: string | undefined, cacheKey: string | undefined): string | undefined {
  if (!url || !cacheKey) {
    return url;
  }
  const cacheUrl = new URL(url, window.location.origin);
  cacheUrl.searchParams.set("v", cacheKey);
  return cacheUrl.toString();
}

function mergeJobs(activeJobs: VtonJobRecord[], trackedJob: VtonJobRecord | undefined): VtonJobRecord[] {
  const byId = new Map<string, VtonJobRecord>();
  for (const job of activeJobs) {
    byId.set(job.job_id, job);
  }
  if (trackedJob) {
    byId.set(trackedJob.job_id, trackedJob);
  }
  return Array.from(byId.values())
    .filter((job) => isActiveVtonJob(job) || job.job_id === trackedJob?.job_id)
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isRecoverablePollingError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return /authenticated account|required scope|Unauthorized|auth_preflight_failed|invalid_jwt|expired_jwt|session expired/i.test(error.message);
}

function vtonOutputPath(result: VtonResponse | undefined, fallbackPath: string): string | undefined {
  if (!result || result.error || result.status !== "completed") {
    return undefined;
  }
  const output = result.report?.output;
  if (isRecord(output) && typeof output.path === "string" && output.path.trim()) {
    return output.path;
  }
  return fallbackPath.trim() || undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function vtonModelSummary(result: VtonResponse | undefined): {
  adapter: string;
  type: string;
  isBaseline: boolean;
} {
  const model = isRecord(result?.report?.model) ? result?.report?.model : undefined;
  const adapter = result?.adapter || result?.routing?.primary_adapter || stringValue(model?.name) || "-";
  const type = stringValue(model?.type) || "-";
  return {
    adapter,
    type,
    isBaseline: adapter === "naive-overlay-vton" || type === "deterministic_baseline",
  };
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

type VtonUploadRole = "person" | "garment";

const SUPPORTED_IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const SUPPORTED_IMAGE_EXTENSIONS = /\.(png|jpe?g|webp)$/i;

function isSupportedImageFile(file: File): boolean {
  return SUPPORTED_IMAGE_MIME_TYPES.has(file.type) || SUPPORTED_IMAGE_EXTENSIONS.test(file.name);
}

async function imageFileToPngDataUrl(file: File): Promise<string> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await loadImage(objectUrl);
    if (image.naturalWidth < 1 || image.naturalHeight < 1) {
      throw new Error("Image has no readable pixels");
    }
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Browser image conversion is unavailable");
    }
    context.drawImage(image, 0, 0);
    return canvas.toDataURL("image/png");
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Browser could not read this image"));
    image.src = src;
  });
}

function uploadErrorMessage(code?: string, message?: string): string {
  if (code === "unauthorized_admin_action") {
    return "Sign in again or enter a local demo API key.";
  }
  return message ?? "Image upload was rejected";
}

interface AssetInputProps {
  label: string;
  path: string;
  preview?: string;
  uploading: boolean;
  error?: string;
  onFileUpload: (file: File) => Promise<void>;
}

function AssetInput({ label, path, preview, uploading, error, onFileUpload }: AssetInputProps) {
  const [dragActive, setDragActive] = useState(false);
  const statusLabel = uploading ? "Uploading" : preview ? "Ready" : "Needed";

  function uploadFirstFile(files: FileList | null) {
    const file = files?.[0];
    if (file) {
      void onFileUpload(file);
    }
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDragActive(true);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    uploadFirstFile(event.dataTransfer.files);
  }

  return (
    <div className={`asset-input${dragActive ? " drag-active" : ""}`}>
      <div className="asset-input-header">
        <strong>{label}</strong>
        <span title={path || `${label} photo needed`}>{statusLabel}</span>
      </div>
      <div
        aria-label={`${label} image upload`}
        className="asset-preview"
        onDragLeave={() => setDragActive(false)}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
      >
        {preview ? (
          <img alt={`${label} preview`} src={preview} />
        ) : (
          <div className="asset-placeholder">
            <ImagePlus aria-hidden="true" size={30} />
            <span>{label} photo</span>
          </div>
        )}
        {uploading ? (
          <div className="upload-overlay">
            <Loader2 aria-hidden="true" className="spin" size={18} />
            Uploading
          </div>
        ) : null}
      </div>
      <label className={`file-button${uploading ? " disabled" : ""}`}>
        <UploadCloud aria-hidden="true" size={16} />
        {uploading ? "Uploading" : "Upload"}
        <input
          accept="image/png,image/jpeg,image/webp"
          disabled={uploading}
          onChange={(event) => {
            uploadFirstFile(event.target.files);
            event.currentTarget.value = "";
          }}
          type="file"
        />
      </label>
      {error ? <div className="asset-error">{error}</div> : null}
    </div>
  );
}
