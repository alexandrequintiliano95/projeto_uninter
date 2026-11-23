# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter

from app.api.deps import Sessao, UsuarioAtual
from app.api.schemas import ConsentimentoCriadoResponse, ConsentimentoRequest, ConsentimentoResponse, respostas_de_erro, utc_iso
from app.application import consentimentos

router = APIRouter(tags=["Consentimentos (LGPD)"])


@router.get("/me/consentimentos", response_model=list[ConsentimentoResponse], responses=respostas_de_erro(401), summary="Listar consentimentos")
def list_consents(user: UsuarioAtual, session: Sessao) -> list[ConsentimentoResponse]:
    return [
        ConsentimentoResponse(finalidade=evento.finalidade, concedido=evento.concedido, versao_termo=evento.versao_termo, criado_em=utc_iso(evento.criado_em))
        for evento in consentimentos.listar(session, user)
    ]


@router.post("/me/consentimentos", response_model=ConsentimentoCriadoResponse, responses=respostas_de_erro(401, 403, 422), summary="Registrar consentimento")
def save_consent(data: ConsentimentoRequest, user: UsuarioAtual, session: Sessao) -> ConsentimentoCriadoResponse:
    evento = consentimentos.registrar(session, user, data.finalidade, data.concedido, data.versao_termo)
    return ConsentimentoCriadoResponse(id=evento.id, finalidade=evento.finalidade, concedido=evento.concedido, versao_termo=evento.versao_termo, criado_em=utc_iso(evento.criado_em))
