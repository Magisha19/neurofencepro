import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest, ApiError } from "../api/client";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { RiskBadge } from "../components/RiskBadge";
import type {
  BehaviourResultsResponse,
  ExperimentOut,
  FuzzingResultsResponse,
  MetricsResponse,
  MetricSummary,
  RiskResponse,
} from "../types/api";
import { formatMeanStd } from "../utils/format";

export function ResultsPage() {
  const { id } = useParams();
  const experimentId = Number(id);
  const detail = useQuery({
    queryKey: ["experiment", experimentId],
    queryFn: () => apiRequest<ExperimentOut>(`/experiments/${experimentId}`),
    enabled: Number.isInteger(experimentId) && experimentId > 0,
  });
  const completed = detail.data?.status === "completed";
  const metrics = useQuery({
    queryKey: ["experiment", experimentId, "metrics"],
    queryFn: () => apiRequest<MetricsResponse>(`/experiments/${experimentId}/metrics`),
    enabled: completed,
  });
  const risk = useQuery({
    queryKey: ["experiment", experimentId, "risk"],
    queryFn: () => apiRequest<RiskResponse>(`/experiments/${experimentId}/risk`),
    enabled: completed,
  });
  const behaviour = useQuery({
    queryKey: ["experiment", experimentId, "behaviour"],
    queryFn: () =>
      apiRequest<BehaviourResultsResponse>(
        `/experiments/${experimentId}/behaviour`,
      ),
    enabled: completed,
  });
  const fuzzing = useQuery({
    queryKey: ["experiment", experimentId, "fuzzing"],
    queryFn: () =>
      apiRequest<FuzzingResultsResponse>(`/experiments/${experimentId}/fuzzing`),
    enabled: completed,
  });

  if (!id || !Number.isInteger(experimentId) || experimentId < 1) {
    return <main className="page-layout"><p className="form-error">Invalid experiment ID.</p></main>;
  }
  if (detail.isPending) {
    return <main className="page-layout"><p className="state-message" role="status">Loading experiment…</p></main>;
  }
  if (detail.isError || !detail.data) {
    return (
      <main className="page-layout">
        <p className="form-error" role="alert">
          {detail.error instanceof ApiError
            ? detail.error.detail
            : "Experiment details could not be loaded."}
        </p>
      </main>
    );
  }

  const experiment = detail.data;
  const notCompleted = experiment.status !== "completed";

  return (
    <main className="page-layout results-page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">EXPERIMENT / RESULTS</p>
          <h1>{experiment.name}</h1>
          <div className="results-run-meta">
            <p className="panel-copy">Run #{experiment.id}</p>
            {experiment.feature_provenance && (
              <ProvenanceBadge provenance={experiment.feature_provenance} />
            )}
          </div>
        </div>
        {experiment.status === "queued" || experiment.status === "running" ? (
          <Link className="quiet-button results-live-link" to={`/experiments/${experiment.id}/live`}>
            Open Live Run
          </Link>
        ) : (
          <Link className="quiet-button results-live-link" to="/history">
            Back to History
          </Link>
        )}
      </section>

      <p className="scope-copy results-scope">{experiment.scope_statement}</p>
      {notCompleted && (
        <section className="panel result-state-panel" role="status">
          <h2>Results are not available</h2>
          <p>
            This experiment is <strong>{experiment.status}</strong>. Results
            will be shown after the run completes.
          </p>
          {experiment.error && <p className="result-error">{experiment.error}</p>}
        </section>
      )}

      {!notCompleted && (
        <>
          <ResultPanel
            error={risk.error}
            isLoading={risk.isPending}
            provenance={risk.data?.provenance}
            title="Risk indicators observed in this experiment"
          >
            {risk.data ? (
              <>
                <div className="risk-overview">
                  <RiskBadge band={risk.data.score.band} />
                  <ProvenanceBadge provenance={risk.data.provenance} />
                  <strong>{risk.data.score.total.toFixed(2)}<span>/100</span></strong>
                </div>
                <p className="risk-label">{risk.data.score.label}</p>
                <div className="component-breakdown">
                  {risk.data.score.components.map((component) => (
                    <article className="component-card" key={component.name}>
                      <div className="component-heading">
                        <strong>{component.name.replaceAll("_", " ")}</strong>
                        <ProvenanceBadge provenance={risk.data.provenance} />
                        <span>
                          {component.points.toFixed(2)} / {component.max_points}
                        </span>
                      </div>
                      <p>{component.explanation}</p>
                    </article>
                  ))}
                </div>
              </>
            ) : null}
          </ResultPanel>

          <ResultPanel
            error={metrics.error}
            isLoading={metrics.isPending}
            provenance={metrics.data?.provenance}
            title="Detector metrics"
          >
            {metrics.data && metrics.data.detectors_summary.length > 0 ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Detector</th>
                      <th scope="col">Precision</th>
                      <th scope="col">Recall</th>
                      <th scope="col">F1</th>
                      <th scope="col">Accuracy</th>
                      <th scope="col">FPR</th>
                      <th scope="col">FNR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.data.detectors_summary.map((detector) => (
                      <tr key={detector.detector}>
                        <td className="mono-cell">{detector.detector}</td>
                        <MetricCell summary={detector.precision} />
                        <MetricCell summary={detector.recall} />
                        <MetricCell summary={detector.f1} />
                        <MetricCell summary={detector.accuracy} />
                        <MetricCell summary={detector.fpr} />
                        <MetricCell summary={detector.fnr} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : metrics.data ? (
              <p className="empty-panel">No detector metrics were returned.</p>
            ) : null}
          </ResultPanel>

          <ResultPanel
            error={behaviour.error}
            isLoading={behaviour.isPending || metrics.isPending}
            provenance={behaviour.data?.provenance ?? metrics.data?.provenance}
            title="Behaviour summary"
          >
            {metrics.data && behaviour.data ? (
              <>
                <div className="summary-cards">
                  <SummaryCard
                    label="Clean accuracy"
                    summary={metrics.data.behaviour_summary.clean_accuracy}
                    provenance={behaviour.data.provenance}
                  />
                  <SummaryCard
                    label="Attack success rate"
                    summary={metrics.data.behaviour_summary.attack_success_rate}
                    provenance={behaviour.data.provenance}
                  />
                </div>
                {behaviour.data.items.length > 0 ? (
                  <div className="table-scroll result-subtable">
                    <table>
                      <thead>
                        <tr>
                          <th scope="col">Seed</th>
                          <th scope="col">Clean accuracy</th>
                          <th scope="col">Attack success rate</th>
                        </tr>
                      </thead>
                      <tbody>
                        {behaviour.data.items.map((row) => (
                          <tr key={row.seed}>
                            <td>{row.seed}</td>
                            <td>{formatRatio(row.clean_accuracy)}</td>
                            <td>{formatRatio(row.attack_success_rate)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="empty-panel">No per-seed behaviour results were returned.</p>
                )}
              </>
            ) : null}
          </ResultPanel>

          <ResultPanel
            error={fuzzing.error}
            isLoading={fuzzing.isPending || metrics.isPending}
            provenance={fuzzing.data?.provenance ?? metrics.data?.provenance}
            title="Fuzzing flip rate by strategy"
          >
            {metrics.data && fuzzing.data ? (
              metrics.data.fuzzing_summary.length > 0 ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Strategy</th>
                        <th scope="col">Flip rate (mean ± std)</th>
                        <th scope="col">Samples</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.data.fuzzing_summary.map((summary) => {
                        const sampleCount = fuzzing.data.items
                          .filter((row) => row.strategy === summary.strategy)
                          .reduce((total, row) => total + row.n_samples, 0);
                        return (
                          <tr key={summary.strategy}>
                            <td className="mono-cell">{summary.strategy}</td>
                            <MetricCell summary={summary.flip_rate} />
                            <td>{sampleCount}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty-panel">No fuzzing summaries were returned.</p>
              )
            ) : null}
          </ResultPanel>
        </>
      )}
    </main>
  );
}

interface ResultPanelProps {
  title: string;
  provenance?: MetricsResponse["provenance"];
  isLoading: boolean;
  error: unknown;
  children: ReactNode;
}

function ResultPanel({
  title,
  provenance,
  isLoading,
  error,
  children,
}: ResultPanelProps) {
  return (
    <section aria-label={title} className="panel result-panel">
      <div className="result-panel-heading">
        <h2>{title}</h2>
        {provenance && <ProvenanceBadge provenance={provenance} />}
      </div>
      {isLoading && <p className="state-message" role="status">Loading results…</p>}
      {Boolean(error) && (
        <p className="form-error result-panel-error" role="alert">
          {error instanceof ApiError
            ? error.detail
            : `${title} could not be loaded.`}
        </p>
      )}
      {!isLoading && !error && !provenance && (
        <p className="empty-panel">No results are available in this panel.</p>
      )}
      {!isLoading && !error && provenance && children}
    </section>
  );
}

function MetricCell({ summary }: { summary: MetricSummary }) {
  const formatted = formatMeanStd(summary);
  return (
    <td>
      <span title={formatted.title}>{formatted.value}</span>
    </td>
  );
}

function SummaryCard({
  label,
  summary,
  provenance,
}: {
  label: string;
  summary: MetricSummary;
  provenance: MetricsResponse["provenance"];
}) {
  const formatted = formatMeanStd(summary);
  return (
    <article className="summary-card">
      <span>{label}</span>
      <ProvenanceBadge provenance={provenance} />
      <strong title={formatted.title}>{formatted.value}</strong>
      <small>
        {summary.n_defined} of {summary.n_total} seeds defined
      </small>
    </article>
  );
}

function formatRatio(value: number | null): string {
  return value === null ? "n/a" : `${(value * 100).toFixed(2)}%`;
}
