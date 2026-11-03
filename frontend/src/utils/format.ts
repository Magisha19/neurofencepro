import type { MetricSummary } from "../types/api";

export interface FormattedMetric {
  value: string;
  title?: string;
}

export function formatMeanStd(summary: MetricSummary): FormattedMetric {
  if (summary.mean === null) {
    return {
      value: "n/a",
      title: "Metric undefined because its denominator was zero for all seeds.",
    };
  }
  const mean = `${(summary.mean * 100).toFixed(2)}%`;
  if (summary.std === null) {
    return {
      value: `${mean} ± n/a`,
      title: "Sample standard deviation requires at least two defined values.",
    };
  }
  return {
    value: `${mean} ± ${(summary.std * 100).toFixed(2)}%`,
  };
}
