import type { Provenance } from "../types/api";

interface ProvenanceBadgeProps {
  provenance: Provenance;
}

export function ProvenanceBadge({ provenance }: ProvenanceBadgeProps) {
  return <span className="provenance-badge">{provenance}</span>;
}
