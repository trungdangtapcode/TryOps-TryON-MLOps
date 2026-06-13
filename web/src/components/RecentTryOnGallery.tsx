import { ExternalLink, ImagePlus } from "lucide-react";
import type { TryOpsClient } from "../api";
import { formatOptionalMs } from "../format";
import type { RequestRecord } from "../types";

interface RecentTryOnGalleryProps {
  client: TryOpsClient;
  requests: RequestRecord[];
  limit?: number;
}

export function RecentTryOnGallery({ client, requests, limit = 6 }: RecentTryOnGalleryProps) {
  const tryOns = requests
    .filter((request) => request.kind === "vton")
    .slice(0, limit);

  if (tryOns.length === 0) {
    return (
      <div className="tryon-gallery-empty">
        <ImagePlus aria-hidden="true" size={30} />
        <span>No saved looks yet.</span>
      </div>
    );
  }

  return (
    <div className="tryon-gallery">
      {tryOns.map((request) => {
        const imageUrl = request.status === "completed"
          ? client.artifactUrl(request.output_summary ?? undefined)
          : undefined;
        return (
          <article className="tryon-gallery-item" key={request.id}>
            <div className="tryon-gallery-image">
              {imageUrl ? (
                <img alt="Saved try-on result" src={imageUrl} />
              ) : (
                <div className="tryon-gallery-placeholder">
                  <ImagePlus aria-hidden="true" size={28} />
                  <span>{request.status}</span>
                </div>
              )}
            </div>
            <div className="tryon-gallery-meta">
              <div>
                <span>{new Date(request.created_at).toLocaleString()}</span>
                <strong>{request.model_alias || request.adapter || "Try-on"}</strong>
              </div>
              <span className={`status-pill ${request.status === "completed" ? "green" : "red"}`}>
                {request.status}
              </span>
            </div>
            <div className="tryon-gallery-actions">
              <span>{formatOptionalMs(request.latency_ms)}</span>
              {imageUrl ? (
                <a href={imageUrl} rel="noreferrer" target="_blank">
                  <ExternalLink aria-hidden="true" size={15} />
                  Open
                </a>
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}
