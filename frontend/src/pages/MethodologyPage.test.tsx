import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { MethodologyPage } from "./MethodologyPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <MethodologyPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("MethodologyPage", () => {
  it("renders all limitations and weights from the API response", async () => {
    const items = [
      "First API limitation text.",
      "Second API limitation text.",
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            scope_statement:
              "Toy-model results only. Not evidence of production-model backdoor detection.",
            risk_score_label: "Risk indicators observed in this experiment",
            weights: {
              behavioural_divergence: 40,
              detector_consensus: 30,
              fuzzing_fragility: 20,
              detector_disagreement: 10,
            },
            weights_note: "Weights are design choices, not a validated standard.",
            limitations: items,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      ),
    );
    renderPage();

    expect(await screen.findByText(items[0])).toBeTruthy();
    expect(screen.getByText(items[1])).toBeTruthy();
    expect(screen.getByText("Risk indicators observed in this experiment")).toBeTruthy();
    expect(screen.getByText("Behavioural divergence")).toBeTruthy();
    expect(screen.getByText("Weights are design choices, not a validated standard.")).toBeTruthy();
  });

  it("shows an error state when the limitations request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Service unavailable",
            status: 503,
            detail: "Limitations are temporarily unavailable.",
          }),
          {
            status: 503,
            headers: { "content-type": "application/problem+json" },
          },
        ),
      ),
    );
    renderPage();

    expect(
      await screen.findByText("Limitations are temporarily unavailable."),
    ).toBeTruthy();
  });
});
