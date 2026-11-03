import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest, ApiError } from "../api/client";
import { EXPERIMENTS_QUERY_KEY } from "../api/experiments";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ExperimentsTable } from "../components/ExperimentsTable";
import { useExperiments } from "../hooks/useExperiments";
import type {
  ExperimentOut,
  ExperimentStatus,
} from "../types/api";
import {
  filterExperiments,
  type HistoryFilter,
} from "../utils/history";

const statuses: ExperimentStatus[] = [
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
];

export function HistoryPage() {
  const queryClient = useQueryClient();
  const experiments = useExperiments();
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const [deleteTarget, setDeleteTarget] = useState<ExperimentOut | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  function invalidateExperiments() {
    void queryClient.invalidateQueries({ queryKey: EXPERIMENTS_QUERY_KEY });
  }

  function errorMessage(error: unknown): string {
    return error instanceof ApiError
      ? error.detail
      : "The experiment action could not be completed.";
  }

  const cancelMutation = useMutation({
    mutationFn: (id: number) =>
      apiRequest<ExperimentOut>(`/experiments/${id}/cancel`, {
        method: "POST",
      }),
    onSuccess: invalidateExperiments,
    onError: (error) => setActionError(errorMessage(error)),
    onMutate: () => setActionError(null),
  });
  const rerunMutation = useMutation({
    mutationFn: (id: number) =>
      apiRequest<ExperimentOut>(`/experiments/${id}/rerun`, {
        method: "POST",
      }),
    onSuccess: invalidateExperiments,
    onError: (error) => setActionError(errorMessage(error)),
    onMutate: () => setActionError(null),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      apiRequest<void>(`/experiments/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleteTarget(null);
      invalidateExperiments();
    },
    onError: (error) => setActionError(errorMessage(error)),
    onMutate: () => setActionError(null),
  });

  const visibleExperiments = filterExperiments(
    experiments.data?.items ?? [],
    filter,
  );
  const isMutating =
    cancelMutation.isPending ||
    rerunMutation.isPending ||
    deleteMutation.isPending;

  return (
    <main className="page-layout">
      <section className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE / RUN HISTORY</p>
          <h1>History</h1>
          <p className="panel-copy">
            Review experiment runs and manage their state.
          </p>
        </div>
        <label className="filter-control">
          <span>Filter by status</span>
          <select
            onChange={(event) => setFilter(event.target.value as HistoryFilter)}
            value={filter}
          >
            <option value="all">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section aria-labelledby="history-heading" className="panel table-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">EXPERIMENTS</p>
            <h2 id="history-heading">All runs</h2>
          </div>
          {experiments.data && (
            <span className="count-chip">{experiments.data.total} total</span>
          )}
        </div>
        {experiments.isPending && (
          <p className="state-message" role="status">
            Loading experiments…
          </p>
        )}
        {experiments.isError && (
          <p className="form-error state-error" role="alert">
            {errorMessage(experiments.error)}
          </p>
        )}
        {actionError && (
          <p className="form-error state-error" role="alert">
            {actionError}
          </p>
        )}
        {experiments.data && visibleExperiments.length === 0 && (
          <div className="empty-state">
            <span aria-hidden="true" className="empty-glyph">
              ◇
            </span>
            <h3>
              {filter === "all" ? "No experiments yet" : "No matching runs"}
            </h3>
            <p>
              {filter === "all"
                ? "Submitted experiment runs will appear here."
                : `There are no ${filter} experiments in this list.`}
            </p>
          </div>
        )}
        {visibleExperiments.length > 0 && (
          <ExperimentsTable
            actions={(experiment) => (
              <div className="row-action-buttons">
                {(experiment.status === "queued" ||
                  experiment.status === "running") && (
                  <button
                    className="table-action"
                    disabled={isMutating}
                    onClick={() => cancelMutation.mutate(experiment.id)}
                    type="button"
                  >
                    Cancel
                  </button>
                )}
                {(experiment.status === "completed" ||
                  experiment.status === "failed" ||
                  experiment.status === "cancelled") && (
                  <button
                    className="table-action"
                    disabled={isMutating}
                    onClick={() => rerunMutation.mutate(experiment.id)}
                    type="button"
                  >
                    Rerun
                  </button>
                )}
                <button
                  className="table-action table-action-danger"
                  disabled={isMutating}
                  onClick={() => {
                    setActionError(null);
                    setDeleteTarget(experiment);
                  }}
                  type="button"
                >
                  Delete
                </button>
              </div>
            )}
            experiments={visibleExperiments}
          />
        )}
      </section>

      {deleteTarget && (
        <ConfirmDialog
          confirmDisabled={deleteMutation.isPending}
          confirmLabel={deleteMutation.isPending ? "Deleting…" : "Delete"}
          description={`Delete “${deleteTarget.name}”? This action cannot be undone.`}
          onCancel={() => {
            if (!deleteMutation.isPending) setDeleteTarget(null);
          }}
          onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
          title="Delete experiment"
        />
      )}
    </main>
  );
}
