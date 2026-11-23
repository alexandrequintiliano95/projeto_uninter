# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Configuração da aplicação, lida de variáveis de ambiente.

O arquivo `.env` na raiz do projeto (copiado de `.env.example`) é carregado automaticamente pela API, pelo seed e
pelo Alembic. Variáveis já definidas no ambiente têm prioridade sobre o `.env`. Sem nenhuma das duas, valem os
padrões de desenvolvimento local abaixo.
"""

from os import getenv
from pathlib import Path

from dotenv import load_dotenv

RAIZ_DO_PROJETO = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ_DO_PROJETO / ".env")

PADRAO_DATABASE_URL = "sqlite:///./raizes.db"
PADRAO_JWT_SECRET = "dev-only-change-me-32-byte-secret-key"


def database_url() -> str:
    return getenv("DATABASE_URL", PADRAO_DATABASE_URL)


def jwt_secret() -> str:
    return getenv("JWT_SECRET", PADRAO_JWT_SECRET)
