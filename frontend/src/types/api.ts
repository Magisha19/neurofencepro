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

export interface ExperimentConfig {
  name: string;
  seeds: number[];
  poison_rate: number;
  trigger_token: string;
  target_label: 0 | 1;
  n_train: number;
  n_test: number;
  strategies: string[];
  fuzz_samples_per_strategy: number;
  detectors: string[];
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

export interface ExperimentList {
  items: ExperimentOut[];
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
