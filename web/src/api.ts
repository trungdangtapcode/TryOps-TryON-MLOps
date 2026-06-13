import type {
  AccountDashboard,
  AccountInvitation,
  AccountJobFeed,
  AccountMembership,
  AccountMember,
  AccountQuota,
  AuthConfig,
  AuthSession,
  DashboardSummary,
  EvaluationIndex,
  ExperimentAnalysis,
  ExperimentConsole,
  ExperimentDecision,
  ExperimentVariant,
  IncidentWorkflowReport,
  LlmGenerationResponse,
  ModelCandidate,
  ModelRecord,
  PromotionDecision,
  QuotaReadModel,
  RequestRecord,
  RollbackState,
  UserProfile,
  VtonComparisonReport,
  VtonJobRecord,
  VtonResponse
} from "./types";

const API_BASE = (import.meta.env.VITE_TRYOPS_API_BASE ?? "").replace(/\/$/, "");

export interface LlmPayload {
  prompt: string;
  model_alias: string;
  max_tokens: number;
  structured: boolean;
  routing_mode: "direct" | "canary" | "experiment_ab" | "experiment_bandit";
  canary_percent: number;
  shadow: boolean;
  optimized_available: boolean;
  fallback_enabled: boolean;
  semantic_cache_enabled: boolean;
  user_id: string;
  quota_plan: string;
  experiment_id?: string;
  experiment_holdback_percent?: number;
  experiment_variants?: ExperimentVariant[];
  experiment_guardrail_thresholds?: Record<string, number>;
}

export interface VtonPayload {
  person_image_path: string;
  garment_image_path: string;
  output_image_path: string;
  model_alias: string;
  user_id: string;
  quota_plan: string;
  category?: "tops" | "bottoms" | "one-pieces";
  garment_photo_type?: "model" | "flat-lay";
  num_timesteps?: number;
  guidance_scale?: number;
  seed?: number;
  segmentation_free?: boolean;
  timeout_ms?: number;
}

export interface VtonUploadPayload {
  role: "person" | "garment";
  filename: string;
  data_url: string;
}

export interface VtonUploadResponse {
  status: string;
  data?: {
    path: string;
    url?: string;
    role: string;
    filename: string;
    content_type: string;
    source_size_bytes: number;
    size_bytes: number;
    width: number;
    height: number;
  };
  error?: {
    code: string;
    message: string;
    details?: Array<Record<string, unknown>>;
  };
}

export interface FeedbackPayload {
  request_id: string;
  user_id: string;
  rating: number;
  label: string;
  comment: string;
}

export class TryOpsClient {
  constructor(
    private readonly apiKey: string,
    private readonly accessToken = "",
    private readonly accountId = ""
  ) {}

  hasApiKey(): boolean {
    return Boolean(this.apiKey.trim());
  }

  hasCredentials(): boolean {
    return Boolean(this.apiKey.trim() || this.accessToken.trim());
  }

  async health(): Promise<{ status: string }> {
    return this.get("/api/health", false);
  }

  async authConfig(): Promise<AuthConfig> {
    const response = await this.get<{ data: AuthConfig }>("/api/auth/config", false);
    if (!response.data) {
      throw new Error("Auth config unavailable");
    }
    return response.data;
  }

  async ready(): Promise<Record<string, unknown>> {
    return this.get("/api/ready", false);
  }

  async session(): Promise<AuthSession> {
    const response = await this.get<{ data: AuthSession }>("/api/auth/session", true);
    if (!response.data) {
      throw new Error("RBAC session unavailable");
    }
    return response.data;
  }

  async bootstrapAccount(): Promise<{
    account: AuthSession["account"];
    membership: AuthSession["membership"];
    accounts?: AccountMembership[];
  }> {
    const response = await this.post<{ data: { account: AuthSession["account"]; membership: AuthSession["membership"] } }>(
      "/api/accounts/bootstrap",
      this.apiKey.trim() ? { api_key: this.apiKey.trim() } : {}
    );
    if (!response.data) {
      throw new Error("Account bootstrap unavailable");
    }
    return response.data;
  }

  async accounts(): Promise<AccountMembership[]> {
    const response = await this.get<{ data: AccountMembership[] }>("/api/accounts", true);
    return response.data ?? [];
  }

  async createAccount(payload: { name: string; description?: string }): Promise<{
    account: AuthSession["account"];
    membership: AuthSession["membership"];
    accounts?: AccountMembership[];
  }> {
    const response = await this.post<{ data: { account: AuthSession["account"]; membership: AuthSession["membership"]; accounts?: AccountMembership[] } }>(
      "/api/accounts",
      payload
    );
    if (!response.data) {
      throw new Error("Workspace creation failed");
    }
    return response.data;
  }

  async updateAccount(accountId: string, payload: { name?: string; description?: string }): Promise<AuthSession["account"]> {
    const response = await this.patch<{ data: AuthSession["account"] }>(`/api/accounts/${encodeURIComponent(accountId)}`, payload);
    if (!response.data) {
      throw new Error("Workspace update failed");
    }
    return response.data;
  }

  async accountDashboard(): Promise<AccountDashboard> {
    const response = await this.get<{ data: AccountDashboard }>("/api/account/dashboard", true);
    if (!response.data) {
      throw new Error("Account dashboard unavailable");
    }
    return response.data;
  }

  async accountQuota(): Promise<AccountQuota> {
    const response = await this.get<{ data: AccountQuota }>("/api/account/quota", true);
    if (!response.data) {
      throw new Error("Account quota unavailable");
    }
    return response.data;
  }

  async accountJobs(status = "active", limit = 20): Promise<AccountJobFeed> {
    const params = new URLSearchParams({ status, limit: String(limit) });
    const response = await this.get<AccountJobFeed>(`/api/account/jobs?${params}`, true);
    return response;
  }

  async accountMembers(): Promise<AccountMember[]> {
    const response = await this.get<{ data: AccountMember[] }>("/api/account/members", true);
    return response.data ?? [];
  }

  async searchProfiles(query: string): Promise<UserProfile[]> {
    const params = new URLSearchParams({ q: query });
    const response = await this.get<{ data: UserProfile[] }>(`/api/profiles/search?${params}`, true);
    return response.data ?? [];
  }

  async accountInvitations(accountId: string): Promise<AccountInvitation[]> {
    const response = await this.get<{ data: AccountInvitation[] }>(
      `/api/accounts/${encodeURIComponent(accountId)}/invitations`,
      true
    );
    return response.data ?? [];
  }

  async inviteAccountMember(accountId: string, payload: { email: string; role: string }): Promise<AccountInvitation> {
    const response = await this.post<{ data: AccountInvitation }>(
      `/api/accounts/${encodeURIComponent(accountId)}/invitations`,
      payload
    );
    if (!response.data) {
      throw new Error("Invitation failed");
    }
    return response.data;
  }

  async revokeInvitation(accountId: string, invitationId: string): Promise<AccountInvitation> {
    const response = await this.delete<{ data: AccountInvitation }>(
      `/api/accounts/${encodeURIComponent(accountId)}/invitations/${encodeURIComponent(invitationId)}`
    );
    if (!response.data) {
      throw new Error("Invitation revoke failed");
    }
    return response.data;
  }

  async updateAccountMember(accountId: string, memberId: string, payload: { role?: string; status?: string }): Promise<AccountMember> {
    const response = await this.patch<{ data: AccountMember }>(
      `/api/accounts/${encodeURIComponent(accountId)}/members/${encodeURIComponent(memberId)}`,
      payload
    );
    if (!response.data) {
      throw new Error("Member update failed");
    }
    return response.data;
  }

  async removeAccountMember(accountId: string, memberId: string): Promise<AccountMember> {
    const response = await this.delete<{ data: AccountMember }>(
      `/api/accounts/${encodeURIComponent(accountId)}/members/${encodeURIComponent(memberId)}`
    );
    if (!response.data) {
      throw new Error("Member removal failed");
    }
    return response.data;
  }

  async dashboard(): Promise<DashboardSummary> {
    return this.get("/api/dashboard", true);
  }

  async quotaSummary(): Promise<QuotaReadModel> {
    const response = await this.get<{ data: QuotaReadModel }>("/api/quota/summary", true);
    if (!response.data) {
      throw new Error("Quota read model unavailable");
    }
    return response.data;
  }

  async history(kind?: string): Promise<RequestRecord[]> {
    const params = new URLSearchParams();
    if (kind && kind !== "all") {
      params.set("kind", kind);
    }
    const response = await this.get<{ data: RequestRecord[] }>(`/api/history?${params}`, true);
    return response.data ?? [];
  }

  async models(): Promise<ModelRecord[]> {
    const response = await this.get<{ data: ModelRecord[] }>("/api/models", true);
    return response.data ?? [];
  }

  async evaluations(): Promise<EvaluationIndex> {
    const response = await this.get<{ data: EvaluationIndex }>("/api/evaluations/summary", true);
    if (!response.data) {
      throw new Error("Evaluation index unavailable");
    }
    return response.data;
  }

  async experiments(): Promise<ExperimentConsole> {
    const response = await this.get<{ data: ExperimentConsole }>("/api/experiments/summary", true);
    if (!response.data) {
      throw new Error("Experiment evidence unavailable");
    }
    return response.data;
  }

  async routeExperiment(payload: {
    mode: "ab" | "bandit";
    request_id: string;
    experiment_id: string;
    variants: ExperimentVariant[];
    holdback_percent: number;
    guardrail_thresholds: Record<string, number>;
  }): Promise<ExperimentDecision> {
    const response = await this.post<{ data: ExperimentDecision }>("/api/experiments/route", {
      ...payload,
      api_key: this.apiKey.trim(),
      workload: "llm"
    });
    if (!response.data) {
      throw new Error("Experiment route unavailable");
    }
    return response.data;
  }

  async analyzeExperiment(payload: {
    experiment_id: string;
    holdback: { name: string; impressions: number; rewards: number };
    variants: ExperimentVariant[];
  }): Promise<ExperimentAnalysis> {
    const response = await this.post<{ data: ExperimentAnalysis }>("/api/experiments/analyze", {
      ...payload,
      api_key: this.apiKey.trim()
    });
    if (!response.data) {
      throw new Error("Experiment analysis unavailable");
    }
    return response.data;
  }

  async vtonComparison(): Promise<VtonComparisonReport> {
    const response = await this.get<{ data: VtonComparisonReport }>("/api/vton/comparison", true);
    if (!response.data) {
      throw new Error("VTON comparison unavailable");
    }
    return response.data;
  }

  artifactUrl(pathOrUrl?: string): string | undefined {
    if (!pathOrUrl) {
      return undefined;
    }
    const raw = pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")
      ? pathOrUrl
      : pathOrUrl.startsWith("/api/")
        ? `${API_BASE}${pathOrUrl}`
        : `${API_BASE}/api/artifacts/file?path=${encodeURIComponent(pathOrUrl)}`;
    const url = new URL(raw, window.location.origin);
    if (this.apiKey.trim()) {
      url.searchParams.set("api_key", this.apiKey.trim());
    } else if (this.accessToken.trim()) {
      url.searchParams.set("access_token", this.accessToken.trim());
    }
    if (this.accountId.trim()) {
      url.searchParams.set("account_id", this.accountId.trim());
    }
    return url.toString();
  }

  async artifactObjectUrl(pathOrUrl?: string): Promise<string | undefined> {
    if (!pathOrUrl) {
      return undefined;
    }
    const raw = pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")
      ? pathOrUrl
      : pathOrUrl.startsWith("/api/")
        ? `${API_BASE}${pathOrUrl}`
        : `${API_BASE}/api/artifacts/file?path=${encodeURIComponent(pathOrUrl)}`;
    const url = new URL(raw, window.location.origin);
    if (this.apiKey.trim()) {
      url.searchParams.set("api_key", this.apiKey.trim());
    }
    if (this.accountId.trim()) {
      url.searchParams.set("account_id", this.accountId.trim());
    }
    const response = await fetch(url, { headers: this.authHeaders() });
    if (!response.ok) {
      return undefined;
    }
    return URL.createObjectURL(await response.blob());
  }

  async lineage(requestId: string): Promise<Record<string, unknown>> {
    return this.get(`/api/lineage/${encodeURIComponent(requestId)}`, true);
  }

  async evaluatePromotion(candidate: ModelCandidate, targetStage = "champion"): Promise<PromotionDecision> {
    return this.post(
      "/api/promotion/evaluate",
      {
        request_id: `req-console-block-${Date.now()}`,
        api_key: this.apiKey.trim(),
        target_stage: targetStage,
        candidate
      },
      { "x-tryops-artifact-signed": "true" }
    );
  }

  async rollbackState(path: string): Promise<RollbackState> {
    return this.artifact(path, "");
  }

  async incidentWorkflow(): Promise<IncidentWorkflowReport> {
    const response = await this.get<{ data: IncidentWorkflowReport }>("/api/incidents/workflow", true);
    if (!response.data) {
      throw new Error("Incident workflow unavailable");
    }
    return response.data;
  }

  async generateLlm(payload: LlmPayload): Promise<LlmGenerationResponse> {
    return this.post("/api/llm/generate", payload);
  }

  async runVton(payload: VtonPayload): Promise<VtonResponse> {
    return this.post("/api/vton/infer", payload);
  }

  async submitVtonJob(payload: VtonPayload): Promise<VtonJobRecord> {
    return this.post("/api/vton/jobs", payload);
  }

  async vtonJob(jobId: string): Promise<VtonJobRecord> {
    return this.get(`/api/vton/jobs/${encodeURIComponent(jobId)}`, true);
  }

  async uploadVtonImage(payload: VtonUploadPayload): Promise<VtonUploadResponse> {
    return this.post("/api/vton/upload", {
      ...payload,
      api_key: this.apiKey.trim()
    });
  }

  async submitFeedback(payload: FeedbackPayload): Promise<{ status: string; id?: string }> {
    return this.post("/api/feedback", payload);
  }

  private async get<T>(path: string, includeApiKey: boolean): Promise<T> {
    const url = new URL(`${API_BASE}${path}`, window.location.origin);
    if (includeApiKey && this.apiKey.trim()) {
      url.searchParams.set("api_key", this.apiKey.trim());
    }
    const response = await fetch(url, { headers: this.authHeaders() });
    return parseResponse<T>(response);
  }

  private async post<T>(path: string, payload: object, headers: Record<string, string> = {}): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.authHeaders(), ...headers },
      body: JSON.stringify(payload)
    });
    return parseResponse<T>(response);
  }

  private async patch<T>(path: string, payload: object): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...this.authHeaders() },
      body: JSON.stringify(payload)
    });
    return parseResponse<T>(response);
  }

  private async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "DELETE",
      headers: this.authHeaders()
    });
    return parseResponse<T>(response);
  }

  private async artifact<T>(path: string, fallbackApiKey: string): Promise<T> {
    const url = new URL(`${API_BASE}/api/artifacts/file`, window.location.origin);
    url.searchParams.set("path", path);
    url.searchParams.set("api_key", this.apiKey.trim() || fallbackApiKey);
    if (this.accountId.trim()) {
      url.searchParams.set("account_id", this.accountId.trim());
    }
    const response = await fetch(url, { headers: this.authHeaders() });
    return parseResponse<T>(response);
  }

  private authHeaders(): Record<string, string> {
    const headers: Record<string, string> = {};
    if (this.accessToken.trim()) {
      headers.Authorization = `Bearer ${this.accessToken.trim()}`;
    }
    if (this.accountId.trim()) {
      headers["X-TryOps-Account-Id"] = this.accountId.trim();
    }
    return headers;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof body === "string"
      ? body
      : body?.error?.message
        ?? body?.message
        ?? formatGatewayError(response.statusText, body);
    throw new Error(message);
  }
  if (typeof body !== "string" && body?.status === "rejected") {
    throw new Error(
      body?.error?.message
      ?? body?.message
      ?? "Request was rejected"
    );
  }
  return body as T;
}

function formatGatewayError(statusText: string, body: Record<string, unknown>): string {
  const error = typeof body.error === "string" ? body.error : undefined;
  const reason = typeof body.reason === "string" ? body.reason : undefined;
  if (error && reason) {
    return `${statusText}: ${error} (${reason})`;
  }
  return error || reason ? `${statusText}: ${error ?? reason}` : statusText;
}
