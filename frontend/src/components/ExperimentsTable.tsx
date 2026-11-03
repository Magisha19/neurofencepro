import type { ReactNode } from "react";
import type { ExperimentOut } from "../types/api";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { StatusBadge } from "./StatusBadge";

interface ExperimentsTableProps {
  experiments: ExperimentOut[];
  actions?: (experiment: ExperimentOut) => ReactNode;
}

export function ExperimentsTable({
  experiments,
  actions,
}: ExperimentsTableProps) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">Experiment</th>
            <th scope="col">Status</th>
            <th scope="col">Stage</th>
            <th scope="col">Progress</th>
            <th scope="col">Created</th>
            <th scope="col">Provenance</th>
            {actions && <th scope="col">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {experiments.map((experiment) => (
            <tr key={experiment.id}>
              <td>
                <span className="experiment-name">{experiment.name}</span>
                <span className="experiment-id">
                  RUN-{String(experiment.id).padStart(4, "0")}
                </span>
              </td>
              <td>
                <StatusBadge status={experiment.status} />
              </td>
              <td className="mono-cell">{experiment.stage}</td>
              <td>
                <div
                  aria-label={`${experiment.progress.toFixed(0)}% complete`}
                  className="progress-track"
                  role="progressbar"
                  aria-valuemax={100}
                  aria-valuemin={0}
                  aria-valuenow={experiment.progress}
                >
                  <span style={{ width: `${experiment.progress}%` }} />
                </div>
                <span className="progress-label">
                  {experiment.progress.toFixed(0)}%
                </span>
              </td>
              <td className="date-cell">
                {new Date(experiment.created_at).toLocaleString()}
              </td>
              <td>
                {experiment.feature_provenance ? (
                  <ProvenanceBadge provenance={experiment.feature_provenance} />
                ) : (
                  <span className="muted-cell">—</span>
                )}
              </td>
              {actions && <td className="row-actions">{actions(experiment)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
