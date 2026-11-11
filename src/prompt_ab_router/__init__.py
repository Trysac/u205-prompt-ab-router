"""Deterministic prompt A/B routing with exposure logging and SRM checks.

``prompt_ab_router`` assigns prompt variants to units (users, sessions, etc.)
using a stable salted SHA-256 hash, records first exposures in a bounded
in-memory log, and detects sample ratio mismatch with a chi-square test.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple

__all__ = [
    "Experiment",
    "Exposure",
    "ExposureLog",
    "LogStats",
    "RouterError",
    "SrmResult",
    "Variant",
    "__version__",
    "assign",
    "srm_check",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# Upper-tail critical values for the chi-square distribution at alpha = 0.001,
# degrees of freedom 1 through 19.  Source: NIST/SEMATECH e-Handbook of
# Statistical Methods, section 1.3.6.7.4, checked 2026-11-09.
_CHI2_CRITICAL_001 = {
    1: 10.828,
    2: 13.816,
    3: 16.266,
    4: 18.467,
    5: 20.515,
    6: 22.458,
    7: 24.322,
    8: 26.124,
    9: 27.877,
    10: 29.588,
    11: 31.264,
    12: 32.909,
    13: 34.528,
    14: 36.123,
    15: 37.697,
    16: 39.252,
    17: 40.790,
    18: 42.312,
    19: 43.820,
}


class RouterError(Exception):
    """Base error for the prompt A/B router.

    Attributes:
        code: Machine-readable error code.  One of ``"invalid_experiment"``,
            ``"invalid_weights"``, ``"invalid_unit"``, ``"invalid_counts"``,
            or ``"invalid_alpha"``.
    """

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True)
class Variant:
    """A named prompt variant with an integer weight."""

    name: str
    prompt: str
    weight: int


@dataclass(frozen=True)
class Experiment:
    """An experiment definition: a set of variants and an optional salt.

    Validation rules:
        - ``name`` must be 1-64 characters of ``[A-Za-z0-9_.-]``.
        - ``variants`` must contain between 1 and 20 variants.
        - Variant names must be 1-64 characters of ``[A-Za-z0-9_.-]`` and
          must be unique within the experiment.
        - Variant weights must be integers ``>= 1``; booleans are rejected.
    """

    name: str
    variants: Sequence[Variant]
    salt: str = ""

    def __post_init__(self) -> None:
        if not (1 <= len(self.name) <= 64) or not _NAME_RE.fullmatch(self.name):
            raise RouterError("invalid_experiment", "invalid experiment name")
        if not 1 <= len(self.variants) <= 20:
            raise RouterError("invalid_experiment", "must have 1 to 20 variants")

        seen_names: set[str] = set()
        tuple_variants = tuple(self.variants)
        for variant in tuple_variants:
            if not (1 <= len(variant.name) <= 64) or not _NAME_RE.fullmatch(variant.name):
                raise RouterError("invalid_weights", "invalid variant name")
            if variant.name in seen_names:
                raise RouterError("invalid_weights", "duplicate variant name")
            if (
                not isinstance(variant.weight, int)
                or isinstance(variant.weight, bool)
                or variant.weight < 1
            ):
                raise RouterError("invalid_weights", "variant weight must be a positive integer")
            seen_names.add(variant.name)

        # Replace the mutable sequence with an immutable tuple.
        object.__setattr__(self, "variants", tuple_variants)


class Exposure(NamedTuple):
    """A stored exposure record.

    Attributes:
        experiment: Experiment name.
        unit_hash: First 16 hex characters of SHA-256(unit_id).
        variant: Variant name assigned to the unit.
        at: Timestamp from the configured clock.
    """

    experiment: str
    unit_hash: str
    variant: str
    at: float


class LogStats(NamedTuple):
    """Statistics about the exposure log."""

    stored: int
    dropped: int


class ExposureLog:
    """In-memory first-exposure log with bounded capacity.

    The first record for each ``(experiment, unit)`` pair is stored and
    counted.  Repeated calls for the same pair return the same variant without
    counting.  When the number of stored unique pairs reaches ``max_entries``,
    new pairs are not stored or counted; ``stats().dropped`` is incremented and
    ``on_event`` is called with a ``"dropped"`` payload.
    """

    def __init__(
        self,
        *,
        max_entries: int = 100_000,
        clock: Callable[[], float] = time.time,
        on_event: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        if not isinstance(max_entries, int) or isinstance(max_entries, bool) or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self._max_entries = max_entries
        self._clock = clock
        self._on_event = on_event
        self._entries: list[Exposure] = []
        self._seen: set[tuple[str, str]] = set()
        self._stored = 0
        self._dropped = 0
        # experiment name -> list of variant names in definition order
        self._experiments: dict[str, list[str]] = {}
        # experiment name -> variant name -> count
        self._counts: dict[str, dict[str, int]] = {}

    def record(self, exp: Experiment, unit_id: str) -> Variant:
        """Assign ``unit_id`` to a variant and log the first exposure.

        Returns the assigned variant.  If the unit has already been seen for
        this experiment, the same variant is returned without any logging or
        counting.  If the log is full, the variant is still returned but no
        storage or counting occurs and ``on_event`` receives a ``"dropped"``
        payload.
        """
        variant = assign(exp, unit_id)
        unit_hash = hashlib.sha256(unit_id.encode("utf-8")).hexdigest()[:16]
        pair_key = (exp.name, unit_hash)

        if pair_key in self._seen:
            return variant

        if self._stored >= self._max_entries:
            self._dropped += 1
            if self._on_event is not None:
                self._on_event({"event": "dropped", "experiment": exp.name})
            return variant

        at = self._clock()
        exposure = Exposure(exp.name, unit_hash, variant.name, at)
        self._entries.append(exposure)
        self._seen.add(pair_key)
        self._stored += 1

        if exp.name not in self._experiments:
            self._experiments[exp.name] = [v.name for v in exp.variants]
            self._counts[exp.name] = {v.name: 0 for v in exp.variants}
        self._counts[exp.name][variant.name] += 1

        if self._on_event is not None:
            self._on_event({"event": "exposure", "experiment": exp.name, "variant": variant.name})
        return variant

    def counts(self, experiment_name: str) -> dict[str, int]:
        """Return counts for a recorded experiment.

        Every variant of the recorded experiment is present, including zero
        counts, in the order the variants were defined.  Returns an empty dict
        if ``experiment_name`` has never been recorded.
        """
        counts = self._counts.get(experiment_name)
        return dict(counts) if counts is not None else {}

    def entries(self) -> list[Exposure]:
        """Return a copy of the stored exposure records in insertion order."""
        return list(self._entries)

    def stats(self) -> LogStats:
        """Return stored and dropped pair counts."""
        return LogStats(stored=self._stored, dropped=self._dropped)


def assign(exp: Experiment, unit_id: str) -> Variant:
    """Deterministically assign ``unit_id`` to a variant of ``exp``.

    The assignment key is ``(exp.salt or exp.name) + ':' + unit_id``.  The key
    is hashed with SHA-256; the first 8 bytes are interpreted as a big-endian
    integer and reduced modulo 10,000.  Variant ``i`` owns buckets
    ``floor(10_000 * cumulative_before_i / total_weight)`` (inclusive) through
    ``floor(10_000 * cumulative_after_i / total_weight)`` (exclusive), where
    cumulative weights run in list order.
    """
    if not isinstance(unit_id, str) or not 1 <= len(unit_id) <= 256:
        raise RouterError("invalid_unit", "unit_id must be a string of 1-256 characters")

    key = (exp.salt or exp.name) + ":" + unit_id
    bucket = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") % 10_000

    total_weight = sum(v.weight for v in exp.variants)
    cumulative_before = 0
    for variant in exp.variants:
        cumulative_after = cumulative_before + variant.weight
        lower = (10_000 * cumulative_before) // total_weight
        upper = (10_000 * cumulative_after) // total_weight
        if lower <= bucket < upper:
            return variant
        cumulative_before = cumulative_after

    # Should never be reached; all buckets from 0 to 9999 are covered.
    raise RuntimeError("bucket assignment failed")


class SrmResult(NamedTuple):
    """Result of a sample ratio mismatch check."""

    chi2: float
    df: int
    flagged: bool


def srm_check(
    counts: Mapping[str, int],
    weights: Mapping[str, int],
    *,
    alpha: float = 0.001,
) -> SrmResult:
    """Check whether observed variant counts match the expected weights.

    Computes the Pearson chi-square statistic for the observed counts against
    the expected counts derived from ``weights``.  The statistic is rounded to
    six decimal places.  ``df`` is ``k - 1`` where ``k`` is the number of
    variants.  ``flagged`` is ``True`` when ``chi2`` exceeds the upper-tail
    critical value for ``alpha``.

    Only ``alpha=0.001`` is supported; any other value raises
    :class:`RouterError` with code ``"invalid_alpha"``.  The keys of ``counts``
    and ``weights`` must match exactly; mismatched keys raise
    :class:`RouterError` with code ``"invalid_counts"``.
    """
    if alpha != 0.001:
        raise RouterError("invalid_alpha", "only alpha=0.001 is supported")

    if set(counts.keys()) != set(weights.keys()):
        raise RouterError("invalid_counts", "counts and weights must have the same keys")

    # Validate value types and ranges.
    for value in counts.values():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RouterError("invalid_counts", "counts must be non-negative integers")
    for value in weights.values():
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise RouterError("invalid_counts", "weights must be positive integers")

    k = len(counts)
    if k < 1 or k > 20:
        if k < 1:
            raise RouterError("invalid_counts", "at least one variant is required")
        raise RouterError("invalid_counts", "unsupported number of variants (max 20)")

    df = k - 1
    total_observed = sum(counts.values())
    if total_observed == 0:
        return SrmResult(chi2=0.0, df=df, flagged=False)

    total_weight = sum(weights.values())
    chi2 = 0.0
    for key in weights:
        observed = counts[key]
        expected = total_observed * weights[key] / total_weight
        chi2 += ((observed - expected) ** 2) / expected

    chi2 = round(chi2, 6)
    # With one variant, chi2 is always 0, so never flagged.
    critical = 0.0 if df == 0 else _CHI2_CRITICAL_001[df]
    flagged = chi2 > critical
    return SrmResult(chi2=chi2, df=df, flagged=flagged)
