# Project record

## Objective

`prompt-ab-router` (import `prompt_ab_router`) assigns prompt variants to users with a stable salted SHA-256 hash, logs first exposures with bounded memory, and checks the sample ratio mismatch of an experiment with a Pearson chi-square test. It is a standard-library-only Python library.

## Scope

- Deterministic `assign(exp, unit_id)` for 1-20 variants with positive integer weights, using `(exp.salt or exp.name) + ':' + unit_id` as the SHA-256 hash key and 10,000 weighted buckets.
- Validation of experiment and variant names (1-64 characters of `[A-Za-z0-9_.-]`), unique variant names, positive integer weights with booleans rejected, and unit ids of 1-256 characters.
- `ExposureLog` with bounded first-exposure storage, hashed unit ids, repeat suppression, dropped-pair counting, optional `clock` and `on_event` callbacks, `counts`, `entries`, and `stats`.
- `srm_check` for observed counts against expected weights with chi-square, `df = k - 1`, bundled critical values for `alpha=0.001` and `df` 1-19, and exact key/type/range validation.
- Public API, errors with machine-readable codes, and no runtime dependencies.

## Out of scope

- Significance of outcome metrics beyond sample ratio mismatch.
- Layered or mutually exclusive experiments.
- Persistence; `entries()` returns records that the caller may write elsewhere.
- Authentication, access control, encryption, or secure erasure of in-memory records.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 1162775 / 63708 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.0923 |

## Factory run u205 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | deepseek-v4-pro | yes | 1824 | 15592 | 0 | 3200 | 0.0321 |
| fix-1 | deepseek-flash | no | 17223 | 6124 | 0 | 159744 | 0.0067 |
| fix-2 | deepseek-flash | no | 7831 | 979 | 0 | 23424 | 0.0018 |
| audit | deepseek-flash | no | 46316 | 28367 | 0 | 722432 | 0.0261 |
| fix-3 | deepseek-flash | no | 10176 | 1526 | 0 | 62720 | 0.0026 |
| docs | deepseek-flash | no | 107629 | 11120 | 0 | 256 | 0.0228 |

Total: $0.0923. Prices: deepseek line, as measured by its adapter.
