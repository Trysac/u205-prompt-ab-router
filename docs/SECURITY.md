# Security notes

## Threat model

`prompt_ab_router` is an in-process library with no network, filesystem, subprocess, `eval`, `exec`, or deserialization code. It validates its own inputs and keeps exposure records in memory; everything else is the caller's responsibility.

### Defended

- Experiment and variant names are checked against `^[A-Za-z0-9_.-]+$` with length 1-64; experiments require 1-20 variants with unique names; weights must be positive integers and booleans are rejected.
- `assign` accepts only string unit ids of 1-256 characters and raises `RouterError(code="invalid_unit")` otherwise. `RouterError` messages are generic and do not include unit ids.
- The exposure log stores `unit_hash = sha256(unit_id.encode("utf-8")).hexdigest()[:16]`, not the raw unit id. Exposure events contain `event`, `experiment`, and `variant`; dropped events contain `event` and `experiment`; neither carries the unit id or prompt text.
- The log has a hard capacity: `max_entries` must be a positive integer and defaults to 100,000. At capacity, new `(experiment, unit)` pairs are refused, `dropped` increments, and existing counts are not double-counted.
- `srm_check` requires matching keys, non-negative integer counts, positive integer weights, 1-20 variants, and only `alpha=0.001`; if total observed count is zero it returns `chi2=0.0` and `flagged=False`. Critical values are bundled for `df` 1-19.

### Not defended

- The 16-hex-character unit hash is pseudonymous, not anonymous. Low-entropy unit ids can be brute-forced, and truncation permits collisions.
- There is no encryption, access control, audit logging, rate limiting, persistence, or secure erasure. `entries()` exposes stored records to any caller with the `ExposureLog` object.
- Prompts, variant names, and weights are stored as plain Python values.
- `clock` and `on_event` are caller-supplied callables; the library does not sanitise what the caller does with payloads or timestamps.
- `srm_check` is not a test of outcome significance and does not support arbitrary alpha values or more than 20 variants.

## Publishing

The package contains no publishing code or credentials. Release handling is outside this module.
