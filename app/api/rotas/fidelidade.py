# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter

from app.api.deps import Sessao, UsuarioAtual
from app.api.schemas import FidelidadeResponse, MovimentoFidelidadeResponse, RegrasFidelidadeResponse, utc_iso
from app.application import fidelidade
from app.domain import regras

router = APIRouter(tags=["Fidelidade"])


@router.get("/me/fidelidade", response_model=FidelidadeResponse)
def loyalty_statement(user: UsuarioAtual, session: Sessao) -> FidelidadeResponse:
    """Saldo, situação do consentimento e últimos 100 movimentos de pontos do cliente autenticado."""
    dados = fidelidade.consultar(session, user)
    return FidelidadeResponse(
        saldo_pontos=dados.saldo_pontos,
        consentimento_ativo=dados.consentimento_ativo,
        regras=RegrasFidelidadeResponse(
            pontos_por_real_pago=1,
            pontos_por_resgate=regras.PONTOS_POR_RESGATE,
            desconto_por_resgate_centavos=regras.CENTAVOS_POR_RESGATE,
            desconto_maximo_percentual=regras.DESCONTO_MAXIMO_PERCENTUAL,
        ),
        extrato=[MovimentoFidelidadeResponse(id=m.id, pedido_id=m.pedido_id, tipo=m.tipo, pontos=m.pontos, criado_em=utc_iso(m.criado_em)) for m in dados.extrato],
    )
