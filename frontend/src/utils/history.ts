import type { ExperimentList, ExperimentStatus, ExperimentOut } from "../types/api";

export type HistoryFilter = "all" | ExperimentStatus;

export function filterExperiments(
  experiments: ExperimentList["items"],
  status: HistoryFilter,
): ExperimentOut[] {
  return experiments
    .filter((experiment) => status === "all" || experiment.status === status)
    .sort((left, right) => {
      const byCreatedTime =
        new Date(right.created_at).getTime() -
        new Date(left.created_at).getTime();
      return byCreatedTime || right.id - left.id;
    });
}
