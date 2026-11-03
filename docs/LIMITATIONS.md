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

## Execution
- Experiments run in an in-process thread pool (default 1 worker). A server restart marks
  running experiments as failed ("Interrupted by server restart"); queued ones are picked up again.
- Cancel is cooperative: computational stages check between seeds, then the current run stops.
- Dataset generation, clean training, and backdoor planting use deterministic synthetic sentiment
  text and 16-unit toy MLP classifiers only; the data and trained models stay in memory.
- Clean accuracy, clean-model baseline ASR, and poisoned-model ASR are computed per seed but are
  not yet persisted or exposed through an API. Behavior, fuzzing, feature, detector, and scoring
  stages remain stubs, so a completed experiment does not yet indicate that those analyses ran.
- The event stream polls the database (0.5 s); it is not a push channel.