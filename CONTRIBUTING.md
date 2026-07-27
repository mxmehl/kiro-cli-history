<!--
SPDX-License-Identifier: MIT
SPDX-FileCopyrightText: 2026 Max Mehl <https://mehl.mx>
-->

# Contributing to kiro-cli-history

Thank you for your interest in contributing! This guide covers the development setup and quality checks.

## Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency management
- [mise](https://mise.jdx.dev) (optional) to run the predefined `mise run <task>` commands used throughout this guide. Also installs the required tools above for you.

## Development setup

Clone the repository and install all dependencies (including dev tools):

```sh
git clone https://github.com/mxmehl/kiro-cli-history.git
cd kiro-cli-history
uv sync
```

This creates a virtual environment in `.venv/` and installs all runtime and development dependencies.

## Running the app locally

```sh
uv run kiro-cli-history
```

## Quality checks

The project uses the following tools for code quality:

| Tool                                  | Purpose                                                |
| -------------------------------------- | ------------------------------------------------------- |
| [ruff](https://docs.astral.sh/ruff/)   | Linting and formatting (replaces pylint, black, isort)  |
| [ty](https://docs.astral.sh/ty/)       | Type checking (replaces mypy)                           |
| [pytest](https://docs.pytest.org/)     | Unit tests                                              |
| [REUSE](https://reuse.software/)       | License and copyright compliance                        |

### Running checks individually

```sh
uv run pytest              # Tests
uv run ruff check          # Linting
uv run ruff format --check # Formatting check
uv run ty check             # Type checking
uv run reuse lint          # License compliance
```

### Running all checks at once

With mise:

```sh
mise run test-all
```

### Auto-fixing issues

With mise:

```sh
mise run fix-all
```

### Code style notes

- Line length: 100 characters
- Docstrings: Google style, enforced by ruff
- All public functions and classes need docstrings
- Type annotations are expected and checked by ty

## Commit messages

Commits to the default branch should follow [Conventional Commits](https://www.conventionalcommits.org/) (`type: subject`, e.g. `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`). Releases are automated with [release-please](https://github.com/googleapis/release-please) based on these commit types, so following the convention ensures the changelog and version bumps are generated correctly. Since pull requests are squash-merged, the PR title must also follow this format.

## Submitting changes

1. Create a branch for your changes
2. Ensure all checks pass: `mise run test-all` (or run them individually)
3. Open a pull request with a Conventional Commits-style title — CI will run the same checks automatically
