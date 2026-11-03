# Limitations

## Authentication
- Registration is not rate limited (only login is). A bot could create many accounts.
- The login rate limiter is in-memory and single-process. Counters reset on restart
  and are not shared between multiple workers.
- The limiter key is (client IP, username). Behind Docker or a reverse proxy every
  client may appear to share one IP unless proxy headers are handled.
- bcrypt cost 12 is the default; nothing enforces that production keeps it.
- Access tokens only (1 hour). No refresh tokens and no server-side revocation:
  a stolen token stays valid until it expires.