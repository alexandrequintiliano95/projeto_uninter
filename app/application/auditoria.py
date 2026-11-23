# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from sqlalchemy.orm import Session

from app.domain.enums import Perfil
from app.domain.regras import exigir_perfil
from app.infrastructure.models import Auditoria, Usuario
from app.infrastructure.repositorios import AuditoriaRepositorio


def listar(session: Session, usuario: Usuario) -> list[Auditoria]:
    """Até 100 eventos mais recentes da unidade do gerente."""
    exigir_perfil(usuario.perfil, frozenset({Perfil.GERENTE}), "Somente gerentes consultam auditoria.")
    return AuditoriaRepositorio(session).da_unidade(usuario.unidade_id)
