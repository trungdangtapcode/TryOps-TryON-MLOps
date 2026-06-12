import type { ComponentType } from "react";
import type { LucideProps } from "lucide-react";

export type ViewKey =
  | "dashboard"
  | "demo"
  | "llm"
  | "vton"
  | "history"
  | "runs"
  | "registry"
  | "evaluations"
  | "experiments"
  | "governance"
  | "incidents";

export interface NavItem {
  key: ViewKey;
  label: string;
  icon: ComponentType<LucideProps>;
  requiredScope?: string;
}

export interface AuthSession {
  schema_version: string;
  principal: {
    key_id: string;
    role: string;
    scopes: string[];
  };
  permissions: {
    nav: ViewKey[];
    can_read_admin: boolean;
    can_read_lineage: boolean;
    can_create_lineage: boolean;
    can_promote: boolean;
  };
}

export type ProfessorDemoTone = "green" | "amber" | "blue" | "red" | "neutral";

export interface ProfessorDemoMetric {
  label: string;
  value: string | number;
  detail?: string;
  tone?: ProfessorDemoTone;
}

export interface ProfessorDemoStep {
  id: string;
  order: string;
  title: string;
  track: string;
  status: string;
  tone: ProfessorDemoTone;
  summary: string;
  operatorLine: string;
  command: string;
  primaryArtifact: string;
  artifacts: string[];
  metrics: ProfessorDemoMetric[];
  transcript: string[];
}

export interface WorkloadSummary {
  requests: number;
  avg_latency_ms: number | null;
  avg_energy_wh: number | null;
  avg_cost_usd: number | null;
  avg_quality: number | null;
}

export interface DashboardSummary {
  schema_version: string;
  generated_at: string;
  total_requests: number;
  llm: WorkloadSummary;
  vton: WorkloadSummary;
  feedback: {
    count: number;
    avg_rating: number | null;
  };
  models_by_stage: Record<string, number>;
}

export interface QuotaReadModel {
  schema_version: string;
  generated_at?: string;
  passed?: boolean;
  source?: string;
  source_engine?: string;
  summary: {
    tenants: number;
    periods: number;
    dimensions: number;
    total_used: number;
    total_limit: number;
    showback_usd: number;
    native_source: boolean;
    at_risk_tenants: number;
  };
  tenants: QuotaTenant[];
  checks?: Record<string, boolean>;
}

export interface QuotaTenant {
  period: string;
  user_hash: string;
  plan: string;
  total_used: number;
  total_limit: number;
  remaining: number;
  utilization_pct: number;
  showback_usd: number;
  risk: "low" | "medium" | "high" | "exhausted" | string;
  dimensions: QuotaDimension[];
}

export interface QuotaDimension {
  dimension: string;
  used: number;
  limit: number;
  remaining: number;
  utilization_pct: number;
  unit_price_usd?: number;
  showback_usd: number;
}

export interface ExperimentVariant {
  name: string;
  adapter?: string;
  allocation_percent?: number;
  impressions: number;
  rewards: number;
  guardrail_block_rate?: number;
  latency_p95_ms?: number;
  error_rate?: number;
}

export interface ExperimentDecision {
  mode: string;
  routing_mode?: string;
  workload?: string;
  request_id?: string;
  experiment_id: string;
  requested_alias?: string;
  primary_alias: string;
  primary_adapter: string;
  reason: string;
  bucket?: number;
  experiment: {
    schema_version: string;
    available?: boolean;
    source?: string;
    mode: string;
    holdback?: boolean;
    selected?: {
      variant: string;
      adapter: string;
      reason: string;
    };
    variants: Array<{
      name: string;
      eligible: boolean;
      traffic_percent: number;
      reward_rate?: number;
      ucb_score?: number;
      violations?: string[];
      guardrail_block_rate?: number;
      latency_p95_ms?: number;
      error_rate?: number;
    }>;
  };
}

export interface ExperimentAnalysis {
  schema_version: string;
  available?: boolean;
  source?: string;
  experiment_id: string;
  best_variant?: string;
  holdback?: {
    name: string;
    impressions: number;
    rewards: number;
    rate?: number;
  };
  variants?: Array<{
    name: string;
    impressions: number;
    rewards: number;
    rate: number;
    uplift_absolute: number;
    uplift_relative: number;
    uplift_ci: {
      lo: number;
      hi: number;
      excludes_zero: boolean;
    };
    sequential: {
      early_stop: boolean;
      verdict: string;
      reason: string;
    };
  }>;
}

export interface ExperimentConsole {
  schema_version: string;
  experiment_id: string;
  production_ready: boolean;
  routing_report?: {
    schema_version: string;
    passed?: boolean;
    algorithm?: string;
    decisions?: {
      ab?: ExperimentDecision;
      bandit?: ExperimentDecision;
    };
  };
  analysis_report?: {
    schema_version: string;
    passed?: boolean;
    native_experiment_stats?: ExperimentAnalysis;
  };
}

export interface RequestRecord {
  id: string;
  created_at: string;
  kind: "llm" | "vton" | string;
  model_alias?: string | null;
  adapter?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  latency_ms?: number | null;
  energy_wh?: number | null;
  cost_usd?: number | null;
  quality?: number | null;
  status: string;
  request_id?: string | null;
  trace_id?: string | null;
}

export interface ModelRecord {
  id: string;
  name: string;
  workload: string;
  stage: string;
  version?: string | null;
  signed: number | boolean;
  approved: number | boolean;
  metrics?: Record<string, unknown>;
  created_at: string;
}

export interface ModelCandidate {
  candidate_id: string;
  workload: string;
  model_name: string;
  model_version: string;
  metrics: Record<string, number>;
  artifacts: Record<string, string>;
  approvals: string[];
  risk_status: string;
  vulnerabilities: Record<string, number>;
  signed: boolean;
  metadata: Record<string, unknown>;
}

export interface PromotionDecision {
  approved?: boolean;
  target_stage?: string;
  reasons?: string[];
  warnings?: string[];
  request_id?: string;
  auth?: {
    allowed?: boolean;
    reason?: string;
    required_scope?: string;
    principal?: {
      role?: string;
      key_id?: string;
      scopes?: string[];
    };
  };
  status?: string;
  error?: {
    code: string;
    message: string;
  };
}

export interface RollbackRecord {
  schema_version: string;
  created_at?: string;
  package_id: string;
  profile?: string;
  status: string;
  reason: string;
  rolled_back_candidate_id: string;
  restored_candidate_id: string;
  triggered_by?: string[];
}

export interface RollbackState {
  schema_version: string;
  updated_at?: string;
  latest_rollback: RollbackRecord;
}

export interface IncidentWorkflowReport {
  schema_version: string;
  generated_at: string;
  passed: boolean;
  production_ready: boolean;
  coverage_level: string;
  incident: {
    id: string;
    title: string;
    severity: string;
    status: string;
    workload: string;
    owner: string;
    source: string;
    created_at: string;
    resolved_at: string;
    error_fingerprint: string;
    impacted_components: string[];
    rollback_required: boolean;
    postmortem_path: string;
  };
  error_tracking: {
    event_count: number;
    fingerprint: string;
    trace_id: string;
    span_id: string;
    service_name: string;
    severity_text: string;
    external_tracker: {
      configured: boolean;
      provider: string;
      mode: string;
      detail: string;
    };
  };
  postmortem: {
    path: string;
    template_path: string;
    action_items: number;
    written: boolean;
  };
  summary: {
    passed_checks: number;
    failed_checks: number;
    total_checks: number;
    timeline_steps: number;
    error_events: number;
    postmortem_ready: boolean;
    external_tracking: boolean;
  };
  timeline: IncidentTimelineStep[];
  checks: Array<{
    name: string;
    passed: boolean;
    detail: string;
  }>;
}

export interface IncidentTimelineStep {
  order: number;
  state: string;
  status: string;
  owner: string;
  evidence: string[];
  description: string;
}

export interface LlmGenerationResponse {
  status?: string;
  request_id?: string;
  model_alias?: string;
  output?: {
    text?: string;
    estimated_tokens?: number;
  };
  metrics?: {
    latency_ms?: number;
    tokens_per_second?: number;
    memory_gb?: number;
  };
  cost_estimate?: {
    request_usd?: number;
    total_tokens?: number;
  };
  quota?: {
    allowed?: boolean;
    checks?: Array<{
      dimension: string;
      limit: number;
      used: number;
      requested: number;
      remaining_after: number;
    }>;
  };
  trace?: {
    trace_id?: string;
    span_id?: string;
  };
  error?: {
    code: string;
    message: string;
  };
}

export interface VtonResponse {
  status?: string;
  request_id?: string;
  adapter?: string;
  routing?: {
    primary_alias?: string;
    primary_adapter?: string;
  };
  report?: Record<string, unknown>;
  quota?: LlmGenerationResponse["quota"];
  trace?: LlmGenerationResponse["trace"];
  error?: {
    code: string;
    message: string;
  };
}

export interface VtonComparisonRun {
  name: string;
  output_path: string;
  output_url?: string;
  report_path?: string;
  report_url?: string;
  latency_ms?: number;
  failure_labels?: string[];
  metrics_against_person?: {
    dhash_similarity?: number;
    global_ssim_luma?: number;
    mse?: number;
    psnr?: number | null;
    native?: {
      available?: boolean;
      schema_version?: string;
      psnr?: number;
      mse?: number;
    };
  };
  garment_similarity?: {
    proxy?: {
      score?: number;
      structural_similarity?: number;
      dhash_similarity?: number;
      histogram_similarity?: number;
    };
  };
}

export interface VtonComparisonReport {
  schema_version: string;
  created_at?: string;
  person_image_path: string;
  person_image_path_url?: string;
  garment_image_path: string;
  garment_image_path_url?: string;
  runs: VtonComparisonRun[];
  winner_by_garment_similarity_proxy?: string;
  winner_by_perceptual_hash?: string;
  winner_by_structural_similarity?: string;
  notes?: string[];
}

export interface EvaluationSummaryItem {
  label: string;
  value: string;
}

export interface EvaluationArtifactReport {
  name: string;
  title: string;
  category: string;
  path: string;
  schema_version?: string;
  created_at?: string;
  status: string;
  summary?: EvaluationSummaryItem[];
  metadata?: Record<string, string>;
}

export interface EvaluationIndex {
  schema_version: string;
  generated_at: string;
  source_roots: string[];
  total_reports: number;
  status_counts: Record<string, number>;
  category_counts: Record<string, number>;
  highlights: Record<string, EvaluationArtifactReport>;
  optimization_panel?: OptimizationPanel;
  pipeline_runs?: PipelineRun[];
  reports: EvaluationArtifactReport[];
}

export interface OptimizationPanel {
  recommended_variant: string;
  recommendation: string;
  carbon_gate_verdict: string;
  greenest_variant?: string;
  model_id?: string;
  judge_backend?: string;
  ranking?: string[];
  variants: OptimizationVariant[];
  sources: Record<string, string>;
}

export interface OptimizationVariant {
  variant: string;
  adapter?: string;
  leaderboard_rank?: number;
  quality_score?: number;
  latency_p50_ms?: number;
  tokens_per_second?: number;
  peak_vram_gb?: number;
  energy_wh_per_1k_tokens?: number;
  sci_g_per_1k_tokens?: number;
  slo_verdict?: string;
  pareto_frontier: boolean;
  recommended: boolean;
}

export interface PipelineRun {
  run_id: string;
  run_name?: string;
  candidate_id?: string;
  workload?: string;
  job_name?: string;
  event_type?: string;
  event_time?: string;
  trace_id?: string;
  code_version?: string;
  dataset_version?: string;
  model_name?: string;
  model_version?: string;
  risk_status?: string;
  signed: boolean;
  paths: Record<string, string>;
}

export interface ApiResult<T> {
  data?: T;
  error?: string;
  status: "idle" | "loading" | "ready" | "error";
}
