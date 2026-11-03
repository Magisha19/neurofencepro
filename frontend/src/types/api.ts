export type ScopeStatement =
  "Toy-model results only. Not evidence of production-model backdoor detection.";

export interface RegisterRequest {
  username: string;
  password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface UserPublic {
  id: number;
  username: string;
  created_at: string;
}

export type ExperimentStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type ExperimentStage =
  | "queued"
  | "dataset"
  | "train_clean"
  | "plant_backdoor"
  | "behaviour"
  | "fuzzing"
  | "features"
  | "detectors"
  | "scoring"
  | "done";

export type Provenance =
  | "SIMULATED"
  | "TOY_MODEL_HIDDEN"
  | "TRANSFORMER_HIDDEN";

export type MutationStrategy =
  | "homoglyph"
  | "leetspeak"
  | "case_perturbation"
  | "zero_width"
  | "synonym_swap"
  | "instruction_injection"
  | "encoding_wrap";

export type DetectorName = "isolation_forest" | "one_class_svm" | "lof";

export interface ExperimentConfig {
  name: string;
  seeds: number[];
  poison_rate: number;
  trigger_token: string;
  target_label: 0 | 1;
  n_train: number;
  n_test: number;
  strategies: MutationStrategy[];
  fuzz_samples_per_strategy: number;
  detectors: DetectorName[];
  contamination: number;
  feature_source: Provenance;
}

export interface ExperimentOut {
  id: number;
  name: string;
  status: ExperimentStatus;
  stage: ExperimentStage;
  progress: number;
  config: ExperimentConfig;
  config_hash: string;
  feature_provenance: Provenance | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  scope_statement: ScopeStatement;
}

export interface ExperimentEvent {
  id: number;
  experiment_id: number;
  seq: number;
  stage: ExperimentStage;
  level: "info" | "warning" | "error";
  message: string;
  progress: number;
  created_at: string;
}

export interface MetricSummary {
  mean: number | null;
  std: number | null;
  n_defined: number;
  n_total: number;
}

export interface ClassificationMetrics {
  precision: number | null;
  recall: number | null;
  f1: number | null;
  accuracy: number | null;
  fpr: number | null;
  fnr: number | null;
}

export interface DetectorSummary {
  detector: DetectorName;
  precision: MetricSummary;
  recall: MetricSummary;
  f1: MetricSummary;
  accuracy: MetricSummary;
  fpr: MetricSummary;
  fnr: MetricSummary;
}

export interface BehaviourSummary {
  clean_accuracy: MetricSummary;
  attack_success_rate: MetricSummary;
  label_flip_rate: MetricSummary;
}

export interface FuzzingSummary {
  strategy: MutationStrategy;
  flip_rate: MetricSummary;
}

export interface MetricsResponse {
  scope_statement: ScopeStatement;
  provenance: Provenance;
  experiment_id: number;
  seeds: number[];
  detectors_per_seed: Array<{
    detector: DetectorName;
    seed: number;
    counts: { tp: number; fn: number; fp: number; tn: number };
    metrics: ClassificationMetrics;
  }>;
  detectors_summary: DetectorSummary[];
  behaviour_per_seed: Array<{
    seed: number;
    n_eval: number;
    n_non_target: number;
    n_attack_success: number;
    n_label_flipped: number;
    clean_accuracy: number | null;
    attack_success_rate: number | null;
    label_flip_rate: number | null;
  }>;
  behaviour_summary: BehaviourSummary;
  fuzzing_per_seed: Array<{
    seed: number;
    strategy: MutationStrategy;
    n_samples: number;
    n_flipped: number;
    flip_rate: number | null;
  }>;
  fuzzing_summary: FuzzingSummary[];
  fuzz_examples: Array<{
    strategy: MutationStrategy;
    original: string;
    mutated_display: string;
  }>;
}

export interface ScoreComponent {
  name:
    | "behavioural_divergence"
    | "detector_consensus"
    | "fuzzing_fragility"
    | "detector_disagreement";
  points: number;
  max_points: number;
  explanation: string;
  inputs: Record<string, number | null>;
}

export interface RiskScore {
  total: number;
  band: "low" | "moderate" | "high" | "critical";
  label: string;
  components: ScoreComponent[];
  weights_note: string;
}

export interface RiskResponse {
  scope_statement: ScopeStatement;
  provenance: Provenance;
  experiment_id: number;
  score: RiskScore;
}

export interface BehaviourResultsResponse {
  scope_statement: ScopeStatement;
  provenance: Provenance;
  experiment_id: number;
  items: MetricsResponse["behaviour_per_seed"];
}

export interface FuzzingResultsResponse {
  scope_statement: ScopeStatement;
  provenance: Provenance;
  experiment_id: number;
  items: MetricsResponse["fuzzing_per_seed"];
}

export interface ExperimentList {
  items: ExperimentOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLogOut {
  id: number;
  action: string;
  resource_type: string | null;
  resource_id: number | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLogOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProblemFieldError {
  field: string;
  message: string;
}

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  errors?: ProblemFieldError[];
}
