import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

afterEach(cleanup);

function ClosingDialog() {
  const [open, setOpen] = useState(true);
  return open ? (
    <ConfirmDialog
      confirmLabel="Delete"
      description="Delete this run?"
      onCancel={() => setOpen(false)}
      onConfirm={vi.fn()}
      title="Delete experiment"
    />
  ) : null;
}

describe("ConfirmDialog", () => {
  it("closes when Escape is pressed", () => {
    render(<ClosingDialog />);

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("calls the confirm handler", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        confirmLabel="Delete"
        description="Delete this run?"
        onCancel={vi.fn()}
        onConfirm={onConfirm}
        title="Delete experiment"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(onConfirm).toHaveBeenCalledOnce();
  });
});
