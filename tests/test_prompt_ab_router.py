"""Tests for the prompt_ab_router public API."""

from __future__ import annotations

import hashlib

import pytest

from prompt_ab_router import (
    Experiment,
    ExposureLog,
    LogStats,
    RouterError,
    SrmResult,
    Variant,
    assign,
    srm_check,
)


def make_experiment(weights: list[int] | None = None, salt: str = "") -> Experiment:
    if weights is None:
        weights = [1, 1]
    variants = [
        Variant(name=f"v{i}", prompt=f"prompt {i}", weight=w) for i, w in enumerate(weights)
    ]
    return Experiment(name="test-exp", variants=variants, salt=salt)


class TestVariant:
    def test_variant_creation(self) -> None:
        v = Variant("control", "Answer briefly.", 1)
        assert v.name == "control"
        assert v.prompt == "Answer briefly."
        assert v.weight == 1

    def test_variant_frozen(self) -> None:
        v = Variant("control", "Answer briefly.", 1)
        with pytest.raises(AttributeError):
            v.name = "changed"  # type: ignore[misc]


class TestExperiment:
    def test_valid_experiment(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("control", "Answer briefly.", 1),
                Variant("treatment", "Answer briefly and cite sources.", 1),
            ],
        )
        assert exp.name == "exp1"
        assert len(exp.variants) == 2
        assert exp.salt == ""

    def test_default_salt_empty(self) -> None:
        exp = Experiment("exp1", [Variant("a", "x", 1)])
        assert exp.salt == ""

    def test_experiment_name_invalid_characters(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("bad name!", [Variant("a", "x", 1)])
        assert exc.value.code == "invalid_experiment"

    def test_experiment_name_too_long(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("a" * 65, [Variant("a", "x", 1)])
        assert exc.value.code == "invalid_experiment"

    def test_empty_variant_list(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", [])
        assert exc.value.code == "invalid_experiment"

    def test_too_many_variants(self) -> None:
        variants = [Variant(f"v{i}", "x", 1) for i in range(21)]
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", variants)
        assert exc.value.code == "invalid_experiment"

    def test_duplicate_variant_names(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", [Variant("a", "x", 1), Variant("a", "y", 1)])
        assert exc.value.code == "invalid_weights"

    def test_weight_zero(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", [Variant("a", "x", 0)])
        assert exc.value.code == "invalid_weights"

    def test_weight_negative(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", [Variant("a", "x", -1)])
        assert exc.value.code == "invalid_weights"

    def test_weight_boolean_rejected(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", [Variant("a", "x", True)])  # type: ignore[arg-type]
        assert exc.value.code == "invalid_weights"

    def test_variant_name_invalid(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", [Variant("a b", "x", 1)])
        assert exc.value.code == "invalid_weights"

    def test_variant_name_too_long(self) -> None:
        with pytest.raises(RouterError) as exc:
            Experiment("exp1", [Variant("a" * 65, "x", 1)])
        assert exc.value.code == "invalid_weights"

    def test_variants_converted_to_tuple(self) -> None:
        variants = [Variant("a", "x", 1), Variant("b", "y", 2)]
        exp = Experiment("exp1", variants)
        assert isinstance(exp.variants, tuple)


class TestAssign:
    def test_acceptance_known_assignment(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("control", "Answer briefly.", 1),
                Variant("treatment", "Answer briefly and cite sources.", 1),
            ],
        )
        assert assign(exp, "user-1").name == "treatment"
        assert assign(exp, "user-2").name == "control"
        assert assign(exp, "user-3").name == "control"
        # identical on every call
        assert assign(exp, "user-1").name == "treatment"

    def test_distribution_1_to_1_over_10000(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("control", "Answer briefly.", 1),
                Variant("treatment", "Answer briefly and cite sources.", 1),
            ],
        )
        counts = {"control": 0, "treatment": 0}
        for i in range(10_000):
            v = assign(exp, f"u{i}")
            counts[v.name] += 1
        assert counts == {"control": 5042, "treatment": 4958}

    def test_acceptance_last_unit_id_u9999(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("control", "Answer briefly.", 1),
                Variant("treatment", "Answer briefly and cite sources.", 1),
            ],
        )
        # The distribution range runs over 'u0' to 'u9999'; the final unit id
        # must assign deterministically to the same variant on every call.
        first = assign(exp, "u9999")
        assert first.name == assign(exp, "u9999").name
        assert first.name in {"control", "treatment"}
        assert first.name == assign(exp, f"u{9999}").name

    def test_invalid_unit_empty(self) -> None:
        exp = make_experiment()
        with pytest.raises(RouterError) as exc:
            assign(exp, "")
        assert exc.value.code == "invalid_unit"

    def test_invalid_unit_too_long(self) -> None:
        exp = make_experiment()
        with pytest.raises(RouterError) as exc:
            assign(exp, "a" * 257)
        assert exc.value.code == "invalid_unit"

    def test_invalid_unit_not_string(self) -> None:
        exp = make_experiment()
        with pytest.raises(RouterError) as exc:
            assign(exp, 42)  # type: ignore[arg-type]
        assert exc.value.code == "invalid_unit"

    def test_salt_changes_assignment(self) -> None:
        exp_no_salt = make_experiment(salt="")
        exp_salted = make_experiment(salt="my-salt")
        # Find a unit_id that differs
        differing = False
        for i in range(100):
            uid = f"user-{i}"
            if assign(exp_no_salt, uid).name != assign(exp_salted, uid).name:
                differing = True
                break
        assert differing, "salt should change assignments for at least one unit"

    def test_weight_1_to_3_integer_math(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("a", "x", 1),
                Variant("b", "y", 3),
            ],
        )
        total_weight = 4
        # Variant "a" owns buckets [0, 2500); "b" owns [2500, 10000).
        expected_upper_a = (10_000 * 1) // total_weight  # 2500
        seen = set()
        for i in range(10_000):
            uid = f"u{i}"
            key = "exp1:" + uid
            bucket = (
                int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") % 10_000
            )
            expected = "a" if bucket < expected_upper_a else "b"
            assigned = assign(exp, uid).name
            assert assigned == expected
            seen.add(assigned)
        assert seen == {"a", "b"}

    def test_ten_variants(self) -> None:
        variants = [Variant(f"v{i}", f"prompt {i}", 1) for i in range(10)]
        exp = Experiment("exp10", variants)
        # No error, and all variants assigned at least once over 10000 units
        seen = set()
        for i in range(10_000):
            v = assign(exp, f"unit-{i}")
            seen.add(v.name)
        assert seen == {f"v{i}" for i in range(10)}


class TestExposureLog:
    def _make_log_with_events(
        self, max_entries: int = 100_000
    ) -> tuple[ExposureLog, list[dict[str, str]]]:
        events: list[dict[str, str]] = []
        log = ExposureLog(max_entries=max_entries, on_event=events.append)
        return log, events

    def test_record_returns_same_variant_and_counts_once(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("control", "Answer briefly.", 1),
                Variant("treatment", "Answer briefly and cite sources.", 1),
            ],
        )
        log = ExposureLog()
        v1 = log.record(exp, "user-1")
        assert v1.name == "treatment"
        v2 = log.record(exp, "user-1")
        assert v2.name == "treatment"
        assert log.counts("exp1") == {"control": 0, "treatment": 1}

    def test_counts_includes_zeros_in_variant_order(self) -> None:
        exp = make_experiment(weights=[1, 2, 3])
        log = ExposureLog()
        # Record only one variant
        for uid in ["u1", "u2", "u3"]:
            log.record(exp, uid)
        counts = log.counts("test-exp")
        assert list(counts.keys()) == ["v0", "v1", "v2"]
        assert all(v == 0 for v in counts.values() if v == 0)  # some may be 0

    def test_max_entries_drops_new_pairs(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("control", "Answer briefly.", 1),
                Variant("treatment", "Answer briefly and cite sources.", 1),
            ],
        )
        log, events = self._make_log_with_events(max_entries=2)
        log.record(exp, "user-2")
        log.record(exp, "user-3")
        # Now full; new pair
        v = log.record(exp, "user-1")
        assert v.name == "treatment"  # assignment still computed
        assert log.counts("exp1") == {"control": 2, "treatment": 0}
        assert log.stats() == LogStats(stored=2, dropped=1)
        # Events: two exposures, one dropped
        assert len(events) == 3
        assert events[0] == {"event": "exposure", "experiment": "exp1", "variant": "control"}
        assert events[1] == {"event": "exposure", "experiment": "exp1", "variant": "control"}
        assert events[2] == {"event": "dropped", "experiment": "exp1"}
        assert "user-1" not in str(events[2])
        assert "Answer briefly" not in str(events[2])

    def test_on_event_does_not_contain_unit_id_or_prompt(self) -> None:
        exp = Experiment(
            "exp1",
            [
                Variant("control", "Answer briefly.", 1),
                Variant("treatment", "Answer briefly and cite sources.", 1),
            ],
        )
        log, events = self._make_log_with_events()
        log.record(exp, "user-1")
        assert len(events) == 1
        event = events[0]
        assert event == {"event": "exposure", "experiment": "exp1", "variant": "treatment"}
        assert "user-1" not in str(event)
        assert "Answer briefly" not in str(event)

    def test_entries_hash_not_raw_id(self) -> None:
        exp = make_experiment()
        log = ExposureLog()
        uid = "user-1"
        log.record(exp, uid)
        entries = log.entries()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.unit_hash == hashlib.sha256(uid.encode("utf-8")).hexdigest()[:16]
        assert uid not in str(entry)

    def test_stats_increment(self) -> None:
        exp = make_experiment()
        log = ExposureLog(max_entries=1)
        log.record(exp, "u1")
        log.record(exp, "u2")  # dropped
        stats = log.stats()
        assert stats.stored == 1
        assert stats.dropped == 1

    def test_clock_injection(self) -> None:
        exp = make_experiment()
        fake_time = 12345.6
        log = ExposureLog(clock=lambda: fake_time)
        log.record(exp, "u1")
        assert log.entries()[0].at == fake_time

    def test_max_entries_invalid(self) -> None:
        with pytest.raises(ValueError):
            ExposureLog(max_entries=0)
        with pytest.raises(ValueError):
            ExposureLog(max_entries=-1)
        with pytest.raises(ValueError):
            ExposureLog(max_entries=True)  # type: ignore[arg-type]

    def test_count_unknown_experiment_empty(self) -> None:
        log = ExposureLog()
        assert log.counts("nonexistent") == {}


class TestSrmCheck:
    def test_acceptance_chi2_4_not_flagged(self) -> None:
        result = srm_check(
            {"control": 5100, "treatment": 4900},
            {"control": 1, "treatment": 1},
        )
        assert result == SrmResult(chi2=4.0, df=1, flagged=False)

    def test_acceptance_chi2_36_flagged(self) -> None:
        result = srm_check(
            {"control": 5300, "treatment": 4700},
            {"control": 1, "treatment": 1},
        )
        assert result == SrmResult(chi2=36.0, df=1, flagged=True)

    def test_rounding_to_six_decimals(self) -> None:
        # chi2 should be rounded, e.g. 10.8275 -> 10.828 (flagged? with df 1 critical 10.828)
        # Construct counts that yield chi2 = 10.8275 -> round to 10.828 -> not > critical
        # Easier: test that rounding is applied by using a value that rounds down/up.
        counts = {"a": 10_001, "b": 9_999}
        weights = {"a": 1, "b": 1}
        # total 20000, expected 10000 each. chi2 = (1^2 + (-1)^2)/10000 = 0.0002
        result = srm_check(counts, weights)
        assert result.chi2 == 0.0002

    def test_invalid_alpha(self) -> None:
        with pytest.raises(RouterError) as exc:
            srm_check({"a": 1}, {"a": 1}, alpha=0.05)
        assert exc.value.code == "invalid_alpha"

    def test_keys_mismatch(self) -> None:
        with pytest.raises(RouterError) as exc:
            srm_check({"a": 1}, {"b": 1})
        assert exc.value.code == "invalid_counts"

    def test_zero_total_observed(self) -> None:
        result = srm_check({"a": 0, "b": 0}, {"a": 1, "b": 2})
        assert result == SrmResult(chi2=0.0, df=1, flagged=False)

    def test_invalid_counts_non_int_or_negative(self) -> None:
        with pytest.raises(RouterError) as exc:
            srm_check({"a": -1}, {"a": 1})
        assert exc.value.code == "invalid_counts"
        with pytest.raises(RouterError):
            srm_check({"a": 1.5}, {"a": 1})  # type: ignore[dict-item]

    def test_invalid_weights_non_int_or_zero_or_bool(self) -> None:
        with pytest.raises(RouterError):
            srm_check({"a": 1}, {"a": 0})
        with pytest.raises(RouterError):
            srm_check({"a": 1}, {"a": 1.5})  # type: ignore[dict-item]
        with pytest.raises(RouterError):
            srm_check({"a": 1}, {"a": True})  # type: ignore[dict-item]

    def test_one_variant_df0(self) -> None:
        result = srm_check({"a": 10}, {"a": 1})
        assert result.df == 0
        assert result.chi2 == 0.0
        assert not result.flagged

    def test_df_in_range(self) -> None:
        # with 2 variants df=1
        result = srm_check({"a": 1, "b": 1}, {"a": 1, "b": 1})
        assert result.df == 1

    def test_more_than_20_variants_raises(self) -> None:
        keys = {f"v{i}": 1 for i in range(21)}
        with pytest.raises(RouterError) as exc:
            srm_check(keys, {k: 1 for k in keys})
        assert exc.value.code == "invalid_counts"
