import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, ApiError, setToken } from "./client";

describe("apiRequest problem responses", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setToken(null);
  });

  it("parses problem+json into an ApiError", async () => {
    setToken(null);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Validation failed",
            status: 422,
            detail: "Check the submitted fields.",
            errors: [{ field: "body.username", message: "Invalid username." }],
          }),
          {
            status: 422,
            headers: { "content-type": "application/problem+json" },
          },
        ),
      ),
    );

    const error = await apiRequest("/auth/login").catch((result: unknown) => result);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      title: "Validation failed",
      detail: "Check the submitted fields.",
      errors: [{ field: "body.username", message: "Invalid username." }],
    });
  });
});
