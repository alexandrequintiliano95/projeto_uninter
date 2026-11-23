# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Hash de senha (Argon2, via pwdlib) e emissão/leitura de JWT."""

from datetime import datetime, timedelta, timezone
from os import getenv

import jwt
from pwdlib import PasswordHash

from app.domain.errors import NaoAutenticado

JWT_SECRET = getenv("JWT_SECRET", "dev-only-change-me-32-byte-secret-key")
JWT_ALGORITHM = "HS256"
TOKEN_MINUTES = 60

_password_hash = PasswordHash.recommended()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return _password_hash.verify(senha, senha_hash)


def criar_token(usuario_id: int, perfil: str) -> str:
    expira_em = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": str(usuario_id), "perfil": perfil, "exp": expira_em}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def ler_token(token: str) -> int:
    """Devolve o ID do usuário contido no token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise NaoAutenticado("TOKEN_INVALIDO", "Token inválido ou expirado.") from None
