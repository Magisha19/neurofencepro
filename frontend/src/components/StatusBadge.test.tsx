import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders a status label and its icon", () => {
    const { container } = render(<StatusBadge status="completed" />);

    expect(screen.getByText("completed")).toBeTruthy();
    expect(container.querySelector('[aria-hidden="true"]')?.textContent).toBe(
      "✓",
    );
  });
});
