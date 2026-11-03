import { apiRequest } from "./client";
import type { ExperimentList } from "../types/api";

export const EXPERIMENTS_QUERY_KEY = ["experiments"] as const;

export function getExperiments(): Promise<ExperimentList> {
  return apiRequest<ExperimentList>("/experiments?limit=100");
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
