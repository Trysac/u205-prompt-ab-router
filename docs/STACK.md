# Stack

## Used

| Tool or module | Why |
|---|---|
| Python >= 3.10 | The code uses `from __future__ import annotations`, built-in generics, and the `|` union syntax. |
| `hashlib` | SHA-256 assignment buckets and truncated unit hashes. |
| `logging` | Creates `logging.getLogger(__name__)` with a `NullHandler`. |
| `re` | Validates experiment and variant names. |
| `time` | Default clock for exposure timestamps. |
| `collections.abc`, `dataclasses`, `typing` | Public types and frozen data records. |
| `pytest` | The visible tests in `tests/test_prompt_ab_router.py` use `pytest.raises`. |

## Discarded

No third-party runtime dependencies are used; the implementation imports only the standard library.
