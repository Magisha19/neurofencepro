import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiRequest, ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import type { ExperimentList } from "../types/api";

export function OverviewPage() {
  const { logout } = useAuth();
  const experiments = useQuery({
    queryKey: ["experiments"],
    queryFn: () => apiRequest<ExperimentList>("/experiments"),
  });

  return (
    <main className="page-layout">
      <header className="topbar">
        <Link aria-label="NeuroFence overview" className="brand-link" to="/">
          <span className="brand-mark small" aria-hidden="true">
            N
          </span>
          <span>NEUROFENCE</span>
        </Link>
        <button className="quiet-button" onClick={logout} type="button">
          Sign out
        </button>
      </header>

      <section className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE / EXPERIMENTS</p>
          <h1>Overview</h1>
          <p className="panel-copy">
            Your experiment runs and their current execution state.
          </p>
        </div>
        <span className="connection-pill">
          <span className="status-dot" aria-hidden="true" />
          API connected
        </span>
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
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Experiment</th>
                  <th scope="col">Status</th>
                  <th scope="col">Stage</th>
                  <th scope="col">Progress</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {experiments.data.items.map((experiment) => (
                  <tr key={experiment.id}>
                    <td>
                      <span className="experiment-name">{experiment.name}</span>
                      <span className="experiment-id">
                        RUN-{String(experiment.id).padStart(4, "0")}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`status-tag status-${experiment.status}`}
                      >
                        {experiment.status}
                      </span>
                    </td>
                    <td className="mono-cell">{experiment.stage}</td>
                    <td>
                      <div
                        aria-label={`${experiment.progress}% complete`}
                        className="progress-track"
                        role="progressbar"
                        aria-valuemax={100}
                        aria-valuemin={0}
                        aria-valuenow={experiment.progress}
                      >
                        <span
                          style={{ width: `${experiment.progress}%` }}
                        />
                      </div>
                      <span className="progress-label">
                        {experiment.progress.toFixed(0)}%
                      </span>
                    </td>
                    <td className="date-cell">
                      {new Date(experiment.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="overview-note">
        This console reports observations from NeuroFence’s toy-model pipeline.
      </p>
    </main>
  );
}
