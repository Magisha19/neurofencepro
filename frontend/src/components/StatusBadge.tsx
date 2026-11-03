import type { ExperimentStatus } from "../types/api";

const statusPresentation: Record<
  ExperimentStatus,
  { icon: string; className: string }
> = {
  queued: { icon: "◷", className: "status-queued" },
  running: { icon: "↻", className: "status-running" },
  completed: { icon: "✓", className: "status-completed" },
  failed: { icon: "!", className: "status-failed" },
  cancelled: { icon: "×", className: "status-cancelled" },
};

interface StatusBadgeProps {
  status: ExperimentStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <span className={`status-tag ${presentation.className}`}>
      <span aria-hidden="true">{presentation.icon}</span>
      <span>{status}</span>
    </span>
  );
}
