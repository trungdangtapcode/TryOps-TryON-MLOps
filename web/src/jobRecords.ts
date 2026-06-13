import type { RequestRecord, VtonJobRecord } from "./types";

export function requestRecordsToVtonJobs(requests: RequestRecord[], limit = 20): VtonJobRecord[] {
  return requests
    .filter((request) => request.kind === "vton")
    .slice(0, limit)
    .map((request) => {
      const requestId = request.request_id || request.id;
      const outputPath = request.status === "completed" ? request.output_summary?.trim() : undefined;
      return {
        schema_version: "tryops.job.v1",
        job_id: `request-${requestId}`,
        workload: "vton",
        request_id: requestId,
        status: request.status,
        created_at: request.created_at,
        queued_at: request.created_at,
        completed_at: request.created_at,
        payload_metadata: {
          model_alias: request.model_alias,
          adapter: request.adapter
        },
        result: outputPath
          ? {
              status: "completed",
              request_id: requestId,
              report: {
                output: {
                  path: outputPath
                }
              }
            }
          : undefined,
        error: request.status === "failed"
          ? {
              code: "request_failed",
              message: request.output_summary || "Try-on request failed"
            }
          : undefined
      };
    });
}
