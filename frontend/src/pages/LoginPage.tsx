import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";

export function LoginPage() {
  const { login, register, isPending, error, resetError } = useAuth();
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const destination =
    (location.state as { from?: string } | null)?.from ?? "/";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    resetError();
    try {
      if (isRegistering) {
        await register({ username, password });
      }
      await login({ username, password });
      navigate(destination, { replace: true });
    } catch {
      // Mutation error is rendered below using the structured API response.
    }
  }

  const errorMessage =
    error instanceof ApiError
      ? error.detail
      : error instanceof Error
        ? error.message
        : null;

  return (
    <main className="login-layout">
      <section className="login-panel panel">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            N
          </div>
          <div>
            <p className="eyebrow">NEUROFENCE / LOCAL CONSOLE</p>
            <h1>Experiment access</h1>
          </div>
        </div>
        <p className="panel-copy">
          Sign in to review your toy-model experiment runs and results.
        </p>

        <div className="mode-switch" aria-label="Account action">
          <button
            type="button"
            className={!isRegistering ? "mode-active" : ""}
            aria-pressed={!isRegistering}
            onClick={() => {
              resetError();
              setIsRegistering(false);
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            className={isRegistering ? "mode-active" : ""}
            aria-pressed={isRegistering}
            onClick={() => {
              resetError();
              setIsRegistering(true);
            }}
          >
            Create account
          </button>
        </div>

        <form className="form-stack" onSubmit={handleSubmit}>
          <label htmlFor="username">Username</label>
          <input
            autoComplete="username"
            id="username"
            name="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />

          <label htmlFor="password">Password</label>
          <input
            autoComplete={isRegistering ? "new-password" : "current-password"}
            id="password"
            name="password"
            required
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          {errorMessage && (
            <p className="form-error" role="alert">
              {errorMessage}
            </p>
          )}

          <button className="primary-button" disabled={isPending} type="submit">
            {isPending
              ? "Please wait…"
              : isRegistering
                ? "Create account"
                : "Sign in"}
          </button>
        </form>

        <p className="login-meta">
          <span className="status-dot" aria-hidden="true" />
          Local API connection · token scoped to this session
        </p>
      </section>
    </main>
  );
}
