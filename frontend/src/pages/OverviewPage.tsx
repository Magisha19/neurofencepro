import { ApiError } from "../api/client";
import { ExperimentsTable } from "../components/ExperimentsTable";
import { useExperiments } from "../hooks/useExperiments";

export function OverviewPage() {
  const experiments = useExperiments();

  return (
    <main className="page-layout">
      <section className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE / EXPERIMENTS</p>
          <h1>Overview</h1>
          <p className="panel-copy">
            Your experiment runs and their current execution state.
          </p>
        </div>
        <button
          className="quiet-button refresh-button"
          disabled={experiments.isFetching}
          onClick={() => void experiments.refetch()}
          type="button"
        >
          {experiments.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </section>

      <section aria-labelledby="experiments-heading" className="panel table-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">RUN HISTORY</p>
            <h2 id="experiments-heading">Experiments</h2>
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
          <p className="form-error" role="alert">
            {experiments.error instanceof ApiError
              ? experiments.error.detail
              : "Experiments could not be loaded."}
          </p>
        )}
        {experiments.data?.items.length === 0 && (
          <div className="empty-state">
            <span className="empty-glyph" aria-hidden="true">
              ◇
            </span>
            <h3>No experiments yet</h3>
            <p>New runs will appear here when they are submitted.</p>
          </div>
        )}
        {experiments.data && experiments.data.items.length > 0 && (
          <ExperimentsTable experiments={experiments.data.items} />
        )}
      </section>

      <p className="overview-note">
        This console reports observations from NeuroFence’s toy-model pipeline.
      </p>
    </main>
  );
}
