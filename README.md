# prompt-ab-router

[![PyPI version](https://img.shields.io/pypi/v/trysac-prompt-ab-router)](https://pypi.org/project/trysac-prompt-ab-router/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-prompt-ab-router)](LICENSE)
[![CI](https://github.com/Trysac/u205-prompt-ab-router/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u205-prompt-ab-router/actions/workflows/ci.yml)

Assign prompt variants to users with a stable salted SHA-256 hash, log first exposures with bounded memory and check the sample ratio mismatch of an experiment

## Problem

Random per-request routing makes the same user see multiple prompt variants and pollutes results; ad hoc hashing without exposure records leaves no audit of who saw which prompt. Without an exposure log and a sample-ratio check, a broken assignment can silently invalidate an experiment. `prompt_ab_router` assigns variants deterministically with a salted SHA-256 bucket, stores first exposures in a bounded in-memory log using a truncated unit hash, and computes a Pearson chi-square sample ratio mismatch check at alpha 0.001.

## Install

```sh
pip install trysac-prompt-ab-router
# or
uv add trysac-prompt-ab-router
```

The import package is `prompt_ab_router`. Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
from prompt_ab_router import Experiment, ExposureLog, Variant, assign, srm_check

exp = Experiment(
    "exp1", [Variant("control", "Brief.", 1), Variant("treatment", "Brief with sources.", 1)]
)
print(assign(exp, "user-1").name)  # treatment
log = ExposureLog()
log.record(exp, "user-1")
log.record(exp, "user-1")
print(log.counts("exp1"))  # {'control': 0, 'treatment': 1}
print(
    srm_check({"control": 5100, "treatment": 4900}, {"control": 1, "treatment": 1})
)  # SrmResult(chi2=4.0, df=1, flagged=False)
```

## Public API

- `Variant(name: str, prompt: str, weight: int)` is a frozen dataclass; `weight` must be a positive integer and booleans are rejected.
- `Experiment(name: str, variants: Sequence[Variant], salt: str = "")` is a frozen dataclass. `name` must be 1-64 characters of `[A-Za-z0-9_.-]`; there must be 1-20 unique variants with names in the same format; variant weights must be integers `>= 1`; the variant sequence is stored as a tuple.
- `assign(exp: Experiment, unit_id: str) -> Variant` requires a string unit id of 1-256 characters. The key is `(exp.salt or exp.name) + ":" + unit_id`; the bucket is the first 8 bytes of SHA-256 of the key as a big-endian integer modulo 10,000. Variant buckets are contiguous weighted ranges in list order.
- `ExposureLog(*, max_entries: int = 100_000, clock: Callable[[], float] = time.time, on_event: Callable[[dict[str, str]], None] | None = None)` stores the first `(experiment, unit_hash)` pair. `record(exp, unit_id)` returns the assigned variant. Repeats return the same variant without counting. When the log is full, new pairs are not stored or counted; `stats().dropped` increments and `on_event` receives a `dropped` payload.
- `ExposureLog.counts(experiment_name)` returns every variant of a recorded experiment, including zero counts, in definition order, or `{}` for an unknown experiment. `entries()` returns a copy of stored `Exposure(experiment, unit_hash, variant, at)` records. `stats()` returns `LogStats(stored, dropped)`.
- `srm_check(counts: Mapping[str, int], weights: Mapping[str, int], *, alpha: float = 0.001) -> SrmResult(chi2: float, df: int, flagged: bool)` requires matching keys, non-negative integer counts, positive integer weights, and 1-20 variants. `chi2` is rounded to six decimals; `df` is `k - 1`; `flagged` is true when `chi2` exceeds the bundled upper-tail critical value. Only `alpha=0.001` is supported; critical values are bundled for `df` 1-19. If total observed count is zero, the result is `chi2=0.0` and `flagged=False`.

## Errors and limits

`RouterError` carries a machine-readable `code` in `invalid_experiment`, `invalid_weights`, `invalid_unit`, `invalid_counts`, or `invalid_alpha`. Messages are generic and do not include unit ids. Unit hashes are the first 16 hex characters of SHA-256 of the unit id; raw unit ids and prompt text are not placed in the exposure events raised by the library. The exposure log is in memory only; `max_entries` must be a positive integer and defaults to 100,000.

## Why not feature-flag percentage rollouts

Feature-flag percentage rollouts are general-purpose release controls; this library is prompt-centred. It records first exposures with hashed unit ids and checks sample ratio mismatch, which flag tools leave to analytics.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
