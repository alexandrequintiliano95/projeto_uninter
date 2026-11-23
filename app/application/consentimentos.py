# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.enums import FinalidadeConsentimento, Perfil
from app.domain.regras import exigir_perfil
from app.infrastructure.models import ConsentimentoEvento, Usuario
from app.infrastructure.repositorios import AuditoriaRepositorio, ConsentimentoRepositorio


def listar(session: Session, usuario: Usuario) -> list[ConsentimentoEvento]:
    """Último evento de cada finalidade: concessão e revogação são eventos; o mais recente vale."""
    atuais: dict[str, ConsentimentoEvento] = {}
    for evento in ConsentimentoRepositorio(session).do_usuario(usuario.id):
        atuais.setdefault(evento.finalidade, evento)
    return list(atuais.values())


def adicionar_evento(session: Session, usuario: Usuario, finalidade: FinalidadeConsentimento, concedido: bool, versao_termo: str) -> ConsentimentoEvento:
    """Grava o evento de concessão ou revogação e a auditoria. Não confirma a transação."""
    evento = ConsentimentoEvento(usuario_id=usuario.id, finalidade=finalidade.value, concedido=concedido, versao_termo=versao_termo, criado_em=datetime.now(timezone.utc).replace(tzinfo=None))
    ConsentimentoRepositorio(session).adicionar(evento)
    AuditoriaRepositorio(session).registrar(usuario.id, None, "CONSENTIMENTO_ATUALIZADO", "CONSENTIMENTO", evento.id, evento.finalidade)
    return evento


def registrar(session: Session, usuario: Usuario, finalidade: FinalidadeConsentimento, concedido: bool, versao_termo: str) -> ConsentimentoEvento:
    exigir_perfil(usuario.perfil, frozenset({Perfil.CLIENTE}), "Somente clientes gerenciam seus consentimentos.")
    evento = adicionar_evento(session, usuario, finalidade, concedido, versao_termo)
    session.commit()
    return evento


def consentimento_ativo(session: Session, usuario_id: int, finalidade: FinalidadeConsentimento) -> bool:
    """Vale o evento mais recente da finalidade; sem evento, não há consentimento."""
    ultimo = ConsentimentoRepositorio(session).ultimo(usuario_id, finalidade.value)
    return bool(ultimo and ultimo.concedido)
