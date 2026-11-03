# NeuroFence auth contract (Stage 3, implemented in Stage 4)

## Passwords
- bcrypt, cost 12. Password 12-128 chars and at most 72 bytes (bcrypt limit).
- Passwords and hashes are never returned, logged, or stored in audit detail.

## Register: POST /api/v1/auth/register
- Body: RegisterRequest. Username is stored lowercase and is unique.
- 201 UserPublic. Duplicate username: 409 problem+json.
- 422 problem+json for validation errors (no submitted values echoed).

## Login: POST /api/v1/auth/login
- Body: LoginRequest. 200 TokenResponse.
- Wrong username and wrong password give the SAME 401 response:
  "Invalid username or password". A dummy bcrypt check runs when the user does not exist
  (so response time does not reveal which usernames exist).
- Rate limit: 5 failed attempts per 5 minutes per (client IP, username).
  Over the limit: 429 with a Retry-After header. Successful login resets the counter.
  In-memory limiter (single process). Documented limitation.

## Tokens
- JWT, HS256, signed with NEUROFENCE_JWT_SECRET.
- Claims: sub (user id as string), iat, exp, jti. No username, no password, no personal data.
- Lifetime: 60 minutes (configurable 5-1440). No refresh tokens in v1.
- Sent as `Authorization: Bearer <token>`.
- Missing / malformed / expired / bad-signature token: 401 problem+json with
  `WWW-Authenticate: Bearer`. Same message for every case.
- Production refuses to start with the default or a short (<32 chars) secret.

## Authorization and isolation
- Every protected query filters by user_id taken from the token, never from the request.
- Another user's resource returns 404 (never 403). Same 404 body as a missing resource.

## SSE (live run events)
- Browser EventSource cannot send headers. Decision: the frontend uses a fetch-based
  stream with the Authorization header. Tokens are NEVER put in query strings.

## Audit log (append-only, per user)
Actions: auth.register, auth.login.success, auth.login.failure, auth.rate_limited,
experiment.create, experiment.cancel, experiment.rerun, experiment.delete,
report.create, report.download.
Stores: user_id (nullable for failed logins), action, resource type/id, small detail dict,
client IP, timestamp. Never stores passwords, tokens or request bodies.

## Errors
RFC 9457 application/problem+json via ProblemDetail. No stack traces, no echoed input.