# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter, Query, status

from app.api.deps import Sessao, UsuarioAtual
from app.api.schemas import MovimentacaoRequest, MovimentacaoResponse
from app.application import estoque

router = APIRouter(tags=["Estoque"])


@router.post("/unidades/{unidade_id}/estoque/movimentacoes", status_code=status.HTTP_201_CREATED, response_model=MovimentacaoResponse)
def register_stock_movement(unidade_id: int, data: MovimentacaoRequest, user: UsuarioAtual, session: Sessao) -> MovimentacaoResponse:
    """Entrada ou saída manual de estoque, feita pelo gerente da unidade, com motivo obrigatório."""
    movimentacao = estoque.registrar_movimentacao(session, user, unidade_id, data.produto_id, data.tipo, data.quantidade, data.motivo)
    return MovimentacaoResponse.de(movimentacao)


@router.get("/unidades/{unidade_id}/estoque/movimentacoes", response_model=list[MovimentacaoResponse])
def list_stock_movements(
    unidade_id: int,
    user: UsuarioAtual,
    session: Sessao,
    produto_id: int | None = Query(None, alias="produtoId", gt=0),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[MovimentacaoResponse]:
    """Histórico de movimentações da unidade, da mais recente para a mais antiga."""
    return [MovimentacaoResponse.de(item) for item in estoque.listar_movimentacoes(session, user, unidade_id, produto_id, page, limit)]
