#!/usr/bin/env bash
# Full verification gate: lint, formatting, types, tests. No writes.
set -euo pipefail
cd "$(dirname "$0")"

uv run ruff check .
uv run ruff format --check .
uv run ty check

if [ -d tests ]; then
    uv run --group test pytest
else
    echo "check.sh: no tests/ directory yet, skipping pytest"
fi

echo "check.sh: all checks passed"
