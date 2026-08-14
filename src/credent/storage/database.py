"""Engine, schema, and session-factory setup for the SQLite store.

DB path contract: the `CREDENT_DB` env var, defaulting to
`artifacts/credent.sqlite` (parent directory created on resolve).
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from credent.storage.models import Base

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

_DEFAULT_DB_PATH = Path('artifacts/credent.sqlite')


def resolve_db_path() -> Path:
    """Resolve the SQLite database path from the `CREDENT_DB` env var.

    Returns
    -------
    Path
        `CREDENT_DB` if set, otherwise `artifacts/credent.sqlite`. The
        parent directory is created if it does not already exist.
    """
    raw_path = os.environ.get('CREDENT_DB')
    db_path = Path(raw_path) if raw_path else _DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def create_engine_and_schema(db_path: Path) -> Engine:
    """Create a SQLite engine and materialize the storage schema.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    Engine
        An engine with every storage table already created.
    """
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to `engine`.

    Parameters
    ----------
    engine : Engine
        The engine sessions should bind to.

    Returns
    -------
    sessionmaker[Session]
        A callable that creates new `Session` instances against `engine`.
    """
    return sessionmaker(engine)
