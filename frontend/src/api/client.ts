import type { ProblemDetail } from "../types/api";

const API_BASE = "/api/v1";
const TOKEN_KEY = "neurofence_access_token";

let memoryToken: string | null = null;
const tokenListeners = new Set<(token: string | null) => void>();

function readStoredToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

memoryToken = readStoredToken();

export function getToken(): string | null {
  return memoryToken;
}

export function getAuthHeaders(headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  if (memoryToken) result.set("Authorization", `Bearer ${memoryToken}`);
  return result;
}

export function handleUnauthorized(): void {
  setToken(null);
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

export function setToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token) {
      window.sessionStorage.setItem(TOKEN_KEY, token);
    } else {
      window.sessionStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Keep the in-memory token when browser storage is unavailable.
  }
  tokenListeners.forEach((listener) => listener(memoryToken));
}

export function subscribeToToken(
  listener: (token: string | null) => void,
): () => void {
  tokenListeners.add(listener);
  return () => tokenListeners.delete(listener);
}

export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail: string;
  readonly errors: ProblemDetail["errors"];

  constructor(
    status: number,
    title: string,
    detail: string,
    errors?: ProblemDetail["errors"],
  ) {
    super(detail || title);
    this.name = "ApiError";
    this.status = status;
    this.title = title;
    this.detail = detail;
    this.errors = errors;
  }
}

async function problemFrom(response: Response): Promise<ApiError> {
  const fallbackTitle = response.statusText || "Request failed";
  let title = fallbackTitle;
  let detail = "The request could not be completed.";
  let errors: ProblemDetail["errors"];

  if (response.headers.get("content-type")?.includes("application/problem+json")) {
    try {
      const body = (await response.json()) as ProblemDetail;
      title = typeof body.title === "string" ? body.title : fallbackTitle;
      detail = typeof body.detail === "string" ? body.detail : title;
      errors = body.errors;
    } catch {
      detail = "The request returned an invalid problem response.";
    }
  }

  return new ApiError(response.status, title, detail, errors);
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = getAuthHeaders(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (response.status === 401) {
    handleUnauthorized();
  }
  if (!response.ok) {
    throw await problemFrom(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// sessionStorage is convenient across reloads, but same-origin JavaScript can read it;
// an XSS flaw could expose the session token.
