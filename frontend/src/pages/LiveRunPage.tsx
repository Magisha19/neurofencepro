import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { apiRequest, ApiError } from "../api/client";
import { EXPERIMENTS_QUERY_KEY } from "../api/experiments";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { StatusBadge } from "../components/StatusBadge";
import { useExperimentEvents } from "../hooks/useExperimentEvents";
import type { ExperimentEvent, ExperimentOut, ExperimentStage } from "../types/api";

const stages: ExperimentStage[] = [
  "queued",
  "dataset",
  "train_clean",
  "plant_backdoor",
  "behaviour",
  "fuzzing",
  "features",
  "detectors",
  "scoring",
  "done",
];

const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

export function LiveRunPage() {
  const { id } = useParams();
  const location = useLocation();
  const experimentId = Number(id);
  const queryClient = useQueryClient();
  const [confirmCancel, setConfirmCancel] = useState(false);
  const eventLogRef = useRef<HTMLDivElement>(null);

  const experiment = useQuery({
    queryKey: ["experiment", experimentId],
    queryFn: () => apiRequest<ExperimentOut>(`/experiments/${experimentId}`),
    enabled: Number.isInteger(experimentId) && experimentId > 0,
    refetchInterval: (query) =>
      query.state.data &&
      !terminalStatuses.has(query.state.data.status)
        ? 2000
        : false,
  });
  const isTerminal =
    experiment.data !== undefined &&
    terminalStatuses.has(experiment.data.status);
  const { events, error: eventError, isLoading: eventLoading } = useExperimentEvents(
    experimentId,
    Boolean(experiment.data),
    isTerminal,
  );
  const cancel = useMutation({
    mutationFn: () =>
      apiRequest<ExperimentOut>(`/experiments/${experimentId}/cancel`, {
        method: "POST",
      }),
    onSuccess: async () => {
      setConfirmCancel(false);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["experiment", experimentId],
        }),
        queryClient.invalidateQueries({ queryKey: EXPERIMENTS_QUERY_KEY }),
      ]);
    },
  });

  const latestEvent = events.at(-1);
  const currentStage =
    experiment.data?.status === "completed"
      ? "done"
      : experiment.data?.stage ?? latestEvent?.stage ?? "queued";
  const stagePosition = stages.indexOf(currentStage);
  const progress = latestEvent?.progress ?? experiment.data?.progress ?? 0;
  const currentSeed = useMemo(() => {
    for (const event of [...events].reverse()) {
      const match = event.message.match(/\bseed\s*[:=#]?\s*(\d+)\b/i);
      if (match) return Number(match[1]);
    }
    return null;
  }, [events]);
  const previousStage = useRef<ExperimentStage | null>(null);
  const [stageAnnouncement, setStageAnnouncement] = useState("");

  useEffect(() => {
    if (previousStage.current !== currentStage) {
      previousStage.current = currentStage;
      setStageAnnouncement(`Current stage: ${stageLabel(currentStage)}`);
    }
  }, [currentStage]);

  useEffect(() => {
    if (eventLogRef.current) {
      eventLogRef.current.scrollTop = eventLogRef.current.scrollHeight;
    }
  }, [events]);

  if (!id || !Number.isInteger(experimentId) || experimentId < 1) {
    return <main className="page-layout"><p className="form-error">Invalid experiment ID.</p></main>;
  }
  if (experiment.isPending) {
    return <main className="page-layout"><p className="state-message" role="status">Loading experiment…</p></main>;
  }
  if (experiment.isError || !experiment.data) {
    return (
      <main className="page-layout">
        <p className="form-error" role="alert">
          {experiment.error instanceof ApiError
            ? experiment.error.detail
            : "Experiment details could not be loaded."}
        </p>
      </main>
    );
  }

  const item = experiment.data;
  const latestErrorEvent = [...events].reverse().find((event) => event.level === "error");
  const failureMessage =
    item.error ?? latestErrorEvent?.message ?? "The experiment did not complete.";

  return (
    <main className="page-layout">
      <section className="page-heading">
        <div>
          <p className="eyebrow">EXPERIMENT / LIVE RUN</p>
          <h1>{item.name}</h1>
          <p className="panel-copy">Run #{item.id} · {stageLabel(currentStage)}</p>
        </div>
        <div className="live-heading-actions">
          <StatusBadge status={item.status} />
          {(item.status === "queued" || item.status === "running") && (
            <button
              className="table-action table-action-danger"
              disabled={cancel.isPending}
              onClick={() => setConfirmCancel(true)}
              type="button"
            >
              Cancel
            </button>
          )}
          {item.status === "completed" && (
            <Link className="primary-button live-link-button" to={`/experiments/${item.id}`}>
              View results
            </Link>
          )}
        </div>
      </section>

      {typeof (location.state as { createdExperimentId?: unknown } | null)
        ?.createdExperimentId === "number" && (
        <p className="success-notice" role="status">
          Experiment created: #{(location.state as { createdExperimentId: number }).createdExperimentId}
        </p>
      )}

      <section aria-labelledby="run-progress-heading" className="panel live-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">EXECUTION</p>
            <h2 id="run-progress-heading">Progress</h2>
          </div>
          <strong className="live-percent">{progress.toFixed(0)}%</strong>
        </div>
        <div className="live-progress-wrap">
          <div
            aria-label={`${progress.toFixed(0)}% complete`}
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={progress}
            className="live-progress-track"
            role="progressbar"
          >
            <span style={{ width: `${progress}%` }} />
          </div>
          {currentSeed !== null && (
            <p className="current-seed">Current seed: {currentSeed}</p>
          )}
        </div>
        <ol aria-label="Experiment stage timeline" className="stage-timeline">
          {stages.map((stage, index) => {
            const stageComplete =
              item.status === "completed" || index < stagePosition;
            const stageState =
              stageComplete
                ? "stage-complete"
                : index === stagePosition
                  ? "stage-current"
                  : "stage-pending";
            return (
              <li
                aria-current={
                  item.status !== "completed" && index === stagePosition
                    ? "step"
                    : undefined
                }
                className={stageState}
                key={stage}
              >
                <span aria-hidden="true" className="stage-marker">
                  {stageComplete ? "✓" : index + 1}
                </span>
                <span>{stageLabel(stage)}</span>
              </li>
            );
          })}
        </ol>
        <p aria-live="polite" className="sr-only">
          {stageAnnouncement}
        </p>
      </section>

      {item.status === "failed" && (
        <p className="form-error" role="alert">{failureMessage}</p>
      )}
      {item.status === "cancelled" && (
        <p className="state-message terminal-message">{failureMessage}</p>
      )}
      <section aria-labelledby="event-log-heading" className="panel live-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">SERVER EVENTS</p>
            <h2 id="event-log-heading">Event log</h2>
          </div>
          <span className="count-chip">{events.length} events</span>
        </div>
        {eventError && (
          <p className="form-error result-panel-error" role="alert">
            {isTerminal ? "Could not load events" : eventError}
          </p>
        )}
        {!eventError && isTerminal && events.length === 0 && (
          <p className="state-message" role="status">
            {eventLoading
              ? "Loading events…"
              : "No experiment events were recorded"}
          </p>
        )}
        {!eventError && !isTerminal && events.length === 0 && (
          <p className="state-message" role="status">
            Waiting for experiment events…
          </p>
        )}
        {events.length > 0 && (
          <div className="event-log" ref={eventLogRef}>
            {events.map((event) => (
              <EventRow event={event} key={event.seq} />
            ))}
          </div>
        )}
      </section>

      {item.status === "completed" && (
        <p className="success-notice">
          The experiment completed. <Link to={`/experiments/${item.id}`}>View results</Link>
        </p>
      )}

      {confirmCancel && (
        <ConfirmDialog
          cancelLabel="Keep running"
          confirmDisabled={cancel.isPending}
          confirmLabel={cancel.isPending ? "Cancelling…" : "Cancel experiment"}
          description="Cancel this experiment run?"
          onCancel={() => {
            if (!cancel.isPending) setConfirmCancel(false);
          }}
          onConfirm={() => cancel.mutate()}
          title="Cancel experiment"
        />
      )}
      {cancel.isError && (
        <p className="form-error" role="alert">
          {cancel.error instanceof ApiError
            ? cancel.error.detail
            : "The experiment could not be cancelled."}
        </p>
      )}
    </main>
  );
}

function EventRow({ event }: { event: ExperimentEvent }) {
  return (
    <article className={`event-row event-${event.level}`}>
      <time dateTime={event.created_at}>
        {new Date(event.created_at).toLocaleTimeString()}
      </time>
      <span className="event-stage">{stageLabel(event.stage)}</span>
      <span className="event-message">{event.message}</span>
      <span className="event-progress">{event.progress.toFixed(0)}%</span>
    </article>
  );
}

function stageLabel(stage: ExperimentStage): string {
  return stage.replaceAll("_", " ");
}
