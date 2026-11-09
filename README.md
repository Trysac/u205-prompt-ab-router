# prompt-ab-router

[![PyPI version](https://img.shields.io/pypi/v/trysac-prompt-ab-router)](https://pypi.org/project/trysac-prompt-ab-router/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-prompt-ab-router)](LICENSE)
[![CI](https://github.com/Trysac/u205-prompt-ab-router/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u205-prompt-ab-router/actions/workflows/ci.yml)

Assign prompt variants to users with a stable salted SHA-256 hash, log first exposures with bounded memory and check the sample ratio mismatch of an experiment

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-prompt-ab-router
# or
uv add trysac-prompt-ab-router
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import prompt_ab_router

# normalize() trims surrounding whitespace and lower-cases the text.
print(prompt_ab_router.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    prompt_ab_router.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
