import { apiRequest } from "./client";
import type { ExperimentConfig, ExperimentList, ExperimentOut } from "../types/api";

export const EXPERIMENTS_QUERY_KEY = ["experiments"] as const;

export function getExperiments(): Promise<ExperimentList> {
  return apiRequest<ExperimentList>("/experiments?limit=100");
}

export function createExperiment(
  config: ExperimentConfig,
): Promise<ExperimentOut> {
  return apiRequest<ExperimentOut>("/experiments", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export function activeExperimentsRefetchInterval(
  items: ExperimentList["items"] | undefined,
): number | false {
  return items?.some(
    (experiment) =>
      experiment.status === "queued" || experiment.status === "running",
  )
    ? 2000
    : false;
}
