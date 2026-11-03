import { describe, expect, it } from "vitest";
import { formatMeanStd } from "./format";

describe("formatMeanStd", () => {
  it("formats mean and sample standard deviation as percentages", () => {
    expect(
      formatMeanStd({ mean: 0.5, std: 0.1, n_defined: 2, n_total: 2 }),
    ).toEqual({ value: "50.00% ± 10.00%" });
  });

  it("shows n/a and explains a zero-denominator null", () => {
    expect(
      formatMeanStd({ mean: null, std: null, n_defined: 0, n_total: 2 }),
    ).toEqual({
      value: "n/a",
      title: "Metric undefined because its denominator was zero for all seeds.",
    });
  });
});
