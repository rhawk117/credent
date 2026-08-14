"""Shared pytest fixtures."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `CREDENT_DB` at an isolated SQLite file for the test."""
    monkeypatch.setenv('CREDENT_DB', str(tmp_path / 'test.sqlite'))
