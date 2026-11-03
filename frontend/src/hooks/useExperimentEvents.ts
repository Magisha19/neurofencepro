import { useEffect, useState } from "react";
import { streamExperimentEvents } from "../api/events";
import type { ExperimentEvent } from "../types/api";

export function useExperimentEvents(
  experimentId: number,
  active: boolean,
  terminalReplay = false,
) {
  const [events, setEvents] = useState<ExperimentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let mounted = true;
    setEvents([]);
    setError(null);
    setIsLoading(true);
    void streamExperimentEvents(
      experimentId,
      controller.signal,
      (event) => {
        setEvents((previous) =>
          previous.some((item) => item.seq === event.seq)
            ? previous
            : [...previous, event].sort((left, right) => left.seq - right.seq),
        );
      },
      terminalReplay,
    )
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            terminalReplay
              ? "Could not load events"
              : reason instanceof Error
                ? reason.message
                : "The event stream could not be connected.",
          );
        }
      })
      .finally(() => {
        if (mounted && !controller.signal.aborted) setIsLoading(false);
      });
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [active, experimentId, terminalReplay]);

  return { events, error, isLoading };
}
