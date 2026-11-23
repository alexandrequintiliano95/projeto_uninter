# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Fixtures dos testes: cada teste usa uma cópia própria de um banco SQLite temporário.

O banco modelo é criado uma vez por execução (tabelas + seed). Cada teste recebe uma
cópia desse arquivo, então nenhum teste depende da ordem dos outros nem do raizes.db.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure import models  # noqa: F401  (registra as tabelas no metadata)
from app.infrastructure.db import Base
from app.api.deps import db_session
from app.main import app
from seed import seed


def _open_database(db_file: Path) -> tuple[Engine, sessionmaker]:
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session")
def template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_file = tmp_path_factory.mktemp("banco") / "modelo.db"
    engine, factory = _open_database(db_file)
    Base.metadata.create_all(engine)
    seed(factory)
    engine.dispose()
    return db_file


@pytest.fixture
def session_factory(template_db: Path, tmp_path: Path) -> Iterator[sessionmaker]:
    db_file = tmp_path / "teste.db"
    shutil.copyfile(template_db, db_file)
    engine, factory = _open_database(db_file)
    yield factory
    engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker) -> Iterator[TestClient]:
    def isolated_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[db_session] = isolated_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(db_session, None)
