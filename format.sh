#!/usr/bin/env bash
# Auto-fix lint violations and reformat the codebase.
set -euo pipefail
cd "$(dirname "$0")"

uv run ruff check --fix .
uv run ruff format .
