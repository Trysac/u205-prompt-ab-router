# Testing

## Running

```sh
pytest tests/test_prompt_ab_router.py
```

The repository contains `tests/test_prompt_ab_router.py`; its compiled artifact is `tests/__pycache__/test_prompt_ab_router.cpython-312-pytest-9.2.0.pyc`.

## Policy

- Tests exercise the public API by importing from `prompt_ab_router`.
- Assertions check exact assignment results, the 1:1 distribution over `u0` to `u9999` (5042 `control`, 4958 `treatment`), error codes, frozen dataclass behavior, tuple conversion, salt effects, and invalid unit ids and names.
- Tests use fixed ids and inputs; no network or wall-clock dependency appears in the visible test code.

## Tiers

There is one visible test tier: the pytest module `tests/test_prompt_ab_router.py`. No conformance markers, CI-only setup scripts, or `tests/conftest.py` are present in the provided files.

## Layout

`tests/test_prompt_ab_router.py` defines the following test classes and methods:

- `TestVariant`: `test_variant_creation`, `test_variant_frozen`.
- `TestExperiment`: `test_valid_experiment`, `test_default_salt_empty`, `test_experiment_name_invalid_characters`, `test_experiment_name_too_long`, `test_empty_variant_list`, `test_too_many_variants`, `test_duplicate_variant_names`, `test_weight_zero`, `test_weight_negative`, `test_weight_boolean_rejected`, `test_variant_name_invalid`, `test_variant_name_too_long`, `test_variants_converted_to_tuple`.
- `TestAssign`: `test_acceptance_known_assignment`, `test_distribution_1_to_1_over_10000`, `test_acceptance_last_unit_id_u9999`, `test_invalid_unit_empty`, `test_invalid_unit_too_long`, `test_invalid_unit_not_string`, `test_salt_changes_assignment`.
