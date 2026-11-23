from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./raizes.db")


class Base(DeclarativeBase):
    """Base das tabelas da aplicação."""


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
