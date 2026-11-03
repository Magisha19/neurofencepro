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
- Behavior and mutation-fuzzing results are persisted per seed; `GET /experiments/{id}/behaviour`
  and `GET /experiments/{id}/fuzzing` expose those toy-model results. Clean-model baseline ASR
  remains an in-memory artifact and is not included in the persisted behavior response.
- Feature extraction and anomaly detectors use only NeuroFence's own toy MLP hidden activations;
  results are not evidence about production models. Detector quality varies by seed.
- Detector hyperparameters (Isolation Forest tree count, One-Class SVM `nu`, and LOF neighbour
  count) are fixed design choices, not tuned to experiment results. With only one detector selected,
  detector disagreement is always 0.
- Risk-score weights are design choices, not a validated standard. A missing component input is
  reported as undefined and contributes 0 points.
- Mutation-fuzzing examples are not persisted; the metrics response currently returns an empty
  `fuzz_examples` list.
- The event stream polls the database (0.5 s); it is not a push channel.