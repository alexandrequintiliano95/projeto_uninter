# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter

from app.api.deps import Sessao, UsuarioAtual
from app.api.schemas import AuditoriaResponse, respostas_de_erro, utc_iso
from app.application import auditoria

router = APIRouter(tags=["Auditoria"])


@router.get("/auditoria", response_model=list[AuditoriaResponse], responses=respostas_de_erro(401, 403, caminho="/auditoria", exemplos={403: ("PERFIL_SEM_PERMISSAO", "Somente gerentes consultam auditoria.")}), summary="Consultar auditoria da unidade")
def list_audit(user: UsuarioAtual, session: Sessao) -> list[AuditoriaResponse]:
    return [
        AuditoriaResponse(id=evento.id, acao=evento.acao, tipo_entidade=evento.tipo_entidade, entidade_id=evento.entidade_id, detalhes=evento.detalhes, criado_em=utc_iso(evento.criado_em))
        for evento in auditoria.listar(session, user)
    ]
