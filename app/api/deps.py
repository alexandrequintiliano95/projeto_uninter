# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application import auth
from app.infrastructure.db import SessionLocal
from app.infrastructure.models import Usuario

bearer_scheme = HTTPBearer(auto_error=False, bearerFormat="JWT", description="Cole o access_token devolvido por POST /auth/login.")


def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


Sessao = Annotated[Session, Depends(db_session)]


def usuario_atual(session: Sessao, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]) -> Usuario:
    return auth.usuario_do_token(session, credentials.credentials if credentials else None)


UsuarioAtual = Annotated[Usuario, Depends(usuario_atual)]
