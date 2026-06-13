import {
  Activity,
  BarChart3,
  Boxes,
  CircuitBoard,
  FlaskConical,
  Gauge,
  History,
  Images,
  LayoutDashboard,
  ShieldAlert,
  Shuffle,
  Workflow
} from "lucide-react";
import type { ModelCandidate, NavItem, ProfessorDemoMetric, ProfessorDemoStep } from "./types";
import professorDemoStoryboard from "./professor_demo_storyboard.json";

export const navItems: NavItem[] = [
  { key: "account", label: "My Account", icon: LayoutDashboard, requiredScope: "account:read" },
  { key: "vton", label: "Try-On Studio", icon: Images },
  { key: "llm", label: "AI Playground", icon: Activity },
  { key: "demo", label: "Professor Demo", icon: FlaskConical },
  { key: "dashboard", label: "Admin Dashboard", icon: Gauge, requiredScope: "admin:read" },
  { key: "history", label: "Request History", icon: History, requiredScope: "admin:read" },
  { key: "runs", label: "Pipeline Runs", icon: Workflow, requiredScope: "admin:read" },
  { key: "registry", label: "Registry", icon: Boxes, requiredScope: "admin:read" },
  { key: "evaluations", label: "Evaluations", icon: BarChart3, requiredScope: "admin:read" },
  { key: "experiments", label: "Experiments", icon: Shuffle, requiredScope: "admin:read" },
  { key: "governance", label: "Governance", icon: CircuitBoard, requiredScope: "lineage:read" },
  { key: "incidents", label: "Incidents", icon: ShieldAlert, requiredScope: "promotion:evaluate" }
];

export const llmVariants = ["baseline", "champion", "challenger", "candidate"];
export const quotaPlans = ["free", "team", "enterprise"];
export const vtonAliases = [
  { value: "champion", label: "FASHN VTON 1.5 GPU" },
  { value: "baseline", label: "Diagnostic compositor" }
];

export const experimentVariants = [
  {
    name: "champion",
    adapter: "tryops-rule-baseline",
    allocation_percent: 45,
    impressions: 1000,
    rewards: 820,
    guardrail_block_rate: 0.002,
    latency_p95_ms: 42,
    error_rate: 0.002
  },
  {
    name: "challenger",
    adapter: "tryops-rule-baseline",
    allocation_percent: 45,
    impressions: 500,
    rewards: 465,
    guardrail_block_rate: 0.004,
    latency_p95_ms: 38,
    error_rate: 0.003
  },
  {
    name: "candidate",
    adapter: "tryops-rule-baseline",
    allocation_percent: 10,
    impressions: 50,
    rewards: 49,
    guardrail_block_rate: 0.08,
    latency_p95_ms: 35,
    error_rate: 0.003
  }
];

export const rollbackStatePath = "artifacts/deployments/rollback_state.json";

export const samplePrompt =
  "Summarize the production risks of moving TryOps LLM traffic behind the Rust gateway.";

export const professorDemoMetrics = professorDemoStoryboard.metrics as ProfessorDemoMetric[];
export const professorDemoSteps = professorDemoStoryboard.steps as ProfessorDemoStep[];

export const releaseLanes = [
  { name: "Champion", stage: "champion", tone: "green" },
  { name: "Challenger", stage: "challenger", tone: "amber" },
  { name: "Candidate", stage: "candidate", tone: "blue" },
  { name: "Rejected", stage: "rejected", tone: "red" }
];

export const badVtonCandidate: ModelCandidate = {
  candidate_id: "vton-catvton-2026-06-11-bad",
  workload: "vton",
  model_name: "catvton-baseline",
  model_version: "0.1.1",
  metrics: {
    garment_fidelity: 0.61,
    identity_preservation: 0.65,
    artifact_rate: 0.21,
    latency_p95_ms: 18100
  },
  artifacts: {
    model_card: "s3://tryops-artifacts/model-cards/vton-catvton-bad.md",
    evaluation_report: "s3://tryops-artifacts/reports/vton-catvton-bad.json"
  },
  approvals: ["mlops_owner"],
  risk_status: "unreviewed",
  vulnerabilities: {
    critical: 1,
    high: 2
  },
  signed: false,
  metadata: {
    code_version: "local-dev",
    dataset_version: "vitonhd-demo-v1",
    pipeline_run_id: "run-vton-bad"
  }
};
