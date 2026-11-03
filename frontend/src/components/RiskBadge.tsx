export type RiskBand = "low" | "moderate" | "high" | "critical";

const bandPresentation: Record<
  RiskBand,
  { label: string; icon: string; className: string }
> = {
  low: { label: "Low", icon: "●", className: "risk-badge-low" },
  moderate: { label: "Moderate", icon: "◆", className: "risk-badge-moderate" },
  high: { label: "High", icon: "▲", className: "risk-badge-high" },
  critical: { label: "Critical", icon: "⬟", className: "risk-badge-critical" },
};

interface RiskBadgeProps {
  band: RiskBand;
}

export function RiskBadge({ band }: RiskBadgeProps) {
  const presentation = bandPresentation[band];
  return (
    <span className={`risk-badge ${presentation.className}`}>
      <span aria-hidden="true">{presentation.icon}</span>
      <span>{presentation.label}</span>
    </span>
  );
}
