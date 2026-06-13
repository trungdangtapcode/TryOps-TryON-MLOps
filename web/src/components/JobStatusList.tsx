import { CheckCircle2, CircleAlert, Clock3, ExternalLink, Loader2 } from "lucide-react";
import type { TryOpsClient } from "../api";
import type { VtonJobRecord } from "../types";

interface JobStatusListProps {
  client: TryOpsClient;
  jobs: VtonJobRecord[];
  emptyText?: string;
  limit?: number;
}

export function JobStatusList({ client, jobs, emptyText = "No running jobs.", limit = 8 }: JobStatusListProps) {
  const visibleJobs = jobs.slice(0, limit);

  if (visibleJobs.length === 0) {
    return (
      <div className="job-list-empty">
        <Clock3 aria-hidden="true" size={24} />
        <span>{emptyText}</span>
      </div>
    );
  }

  return (
    <div className="job-list">
      {visibleJobs.map((job) => {
        const outputPath = vtonJobOutputPath(job);
        const outputUrl = outputPath ? client.artifactUrl(outputPath) : undefined;
        return (
          <article className="job-row" key={job.job_id}>
            <span className={`job-icon ${jobTone(job.status)}`}>
              {job.status === "queued" || job.status === "running" || job.status === "accepted" ? (
                <Loader2 aria-hidden="true" className="spin" size={17} />
              ) : job.status === "completed" ? (
                <CheckCircle2 aria-hidden="true" size={17} />
              ) : (
                <CircleAlert aria-hidden="true" size={17} />
              )}
            </span>
            <div className="job-main">
              <div className="job-title-line">
                <strong>{labelStatus(job.status)}</strong>
                <span className={`status-pill ${jobTone(job.status)}`}>{job.status}</span>
              </div>
              <span>{new Date(job.created_at).toLocaleString()}</span>
              <small title={job.request_id}>{job.request_id}</small>
              {job.error?.message ? <em>{job.error.message}</em> : null}
            </div>
            {outputUrl ? (
              <a className="job-open-link" href={outputUrl} rel="noreferrer" target="_blank">
                <ExternalLink aria-hidden="true" size={15} />
                Open
              </a>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

export function isActiveVtonJob(job: VtonJobRecord): boolean {
  return job.status === "accepted" || job.status === "queued" || job.status === "running";
}

function labelStatus(status: string): string {
  if (status === "queued") {
    return "Waiting for model";
  }
  if (status === "running" || status === "accepted") {
    return "Generating look";
  }
  if (status === "completed") {
    return "Look ready";
  }
  return "Generation failed";
}

function jobTone(status: string): "green" | "amber" | "blue" | "red" {
  if (status === "completed") {
    return "green";
  }
  if (status === "queued" || status === "accepted") {
    return "amber";
  }
  if (status === "running") {
    return "blue";
  }
  return "red";
}

function vtonJobOutputPath(job: VtonJobRecord): string | undefined {
  if (job.status !== "completed" || !job.result?.report) {
    return undefined;
  }
  const output = job.result.report.output;
  if (typeof output === "object" && output !== null && "path" in output) {
    const path = output.path;
    return typeof path === "string" && path.trim() ? path : undefined;
  }
  return undefined;
}
