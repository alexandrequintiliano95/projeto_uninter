# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Confere que as migrações do Alembic criam exatamente o esquema descrito pelos modelos ORM."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.infrastructure import models  # noqa: F401  (registra as tabelas no metadata)
from app.infrastructure.db import Base

RAIZ = Path(__file__).resolve().parents[1]


def test_migracoes_geram_o_esquema_dos_modelos(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'migrado.db').as_posix()}"
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        with engine.connect() as conexao:
            diferencas = compare_metadata(MigrationContext.configure(conexao), Base.metadata)
        assert {"movimentacao_estoque", "fidelidade_movimento"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert diferencas == []


def test_alembic_usa_o_database_url_do_ambiente(tmp_path: Path, monkeypatch):
    destino = tmp_path / "via_ambiente.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{destino.as_posix()}")
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    # Trava de segurança: se o alembic.ini fixar um banco, o upgrade iria para ele (ex.: o raizes.db local).
    assert config.get_main_option("sqlalchemy.url") is None, "alembic.ini não deve fixar o banco; ele vem de DATABASE_URL"
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{destino.as_posix()}")
    try:
        assert {"pedido", "movimentacao_estoque", "fidelidade_movimento"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
