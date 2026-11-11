# Architecture

## Purpose

`prompt-ab-router` (import `prompt_ab_router`) assigns prompt variants to units with a stable salted SHA-256 hash, records first exposures in a bounded in-memory log, and checks sample ratio mismatch with a Pearson chi-square test. It is a standard-library-only Python module.

## Shape

```text
caller code --> prompt_ab_router (public API in __init__.py)
                    |
                    +-- assign: SHA-256 bucket assignment
                    +-- ExposureLog: bounded first-exposure memory
                    +-- srm_check: chi-square check at alpha 0.001
```

- **Public API**: the names in `__all__` of `src/prompt_ab_router/__init__.py`. Internal helpers are not exported.
- **Errors**: invalid input raises `RouterError` with one of the documented codes.
- **State and side effects**: `assign` and `srm_check` are pure. `ExposureLog` holds in-memory entries, counters, and an optional caller-supplied `on_event` callback; it does no network or filesystem I/O. The module configures `logging.getLogger(__name__)` with a `NullHandler`.

## Quality contract

No `scripts/check.py` or CI definition is present in the provided repository. The visible test module is `tests/test_prompt_ab_router.py`, which imports `pytest` and exercises the public API.

## Decisions

The implementation uses deterministic SHA-256 bucket assignment, a bounded first-exposure log that refuses new pairs when full rather than double-counting, and a fixed `alpha=0.001` chi-square table for `df` 1-19.
