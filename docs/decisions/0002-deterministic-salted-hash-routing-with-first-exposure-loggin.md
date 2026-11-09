# Deterministic salted hash routing with first-exposure logging and SRM checks

Status: accepted (generated, pending human review)

## Context

Teams running prompt A/B tests often route users randomly per request, causing the same user to see multiple variants and polluting results. They may also hash identifiers ad hoc without logging exposures, making it impossible to detect broken assignment. This library must provide stable assignment, bounded exposure logging without raw user identifiers, and a sample ratio mismatch (SRM) check.

## Decision

Implement a pure-Python, standard-library-only package with a frozen `Variant` and `Experiment` dataclass, deterministic assignment via SHA-256 over a salted key reduced to 10,000 buckets using integer floor arithmetic, an in-memory `ExposureLog` that stores only first exposures (refusal on overflow) and emits event payloads without unit IDs or prompts, and a `srm_check` function computing Pearson chi-square against precomputed critical values for alpha=0.001.

## Consequences

The library has no runtime dependencies and is deterministic. Exposure logs are bounded and privacy-preserving (only hashed IDs stored). SRM checks are limited to alpha=0.001 and up to 20 variants (df up to 19) because critical values are bundled. The API is stable and covers the essential needs without persistence or multi-layer experiment support, which are out of scope.
