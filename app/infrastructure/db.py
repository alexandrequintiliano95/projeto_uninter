# Trechos alterados com apoio de IA (Claude Code) e revisados pelo autor.
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import database_url

DATABASE_URL = database_url()


class Base(DeclarativeBase):
    """Base das tabelas da aplicação."""


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
