# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter, Query, status

from app.api.deps import Sessao, UsuarioAtual
from app.api.schemas import PagamentoRequest, PagamentoResponse, PedidoRequest, PedidoResponse, StatusRequest
from app.application import pedidos
from app.domain.enums import CanalPedido, StatusPedido

router = APIRouter(tags=["Pedidos"])


@router.post("/pedidos", status_code=status.HTTP_201_CREATED, response_model=PedidoResponse)
def create_order(data: PedidoRequest, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    itens = [(item.produto_id, item.quantidade) for item in data.itens]
    return PedidoResponse.de(pedidos.criar_pedido(session, user, data.unidade_id, data.canal_pedido, itens, data.pontos_resgatados))


@router.get("/pedidos/{pedido_id}", response_model=PedidoResponse)
def get_order(pedido_id: int, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    return PedidoResponse.de(pedidos.consultar_pedido(session, user, pedido_id))


@router.get("/pedidos", response_model=list[PedidoResponse])
def list_orders(
    user: UsuarioAtual,
    session: Sessao,
    canal_pedido: CanalPedido | None = Query(None, alias="canalPedido"),
    pedido_status: StatusPedido | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[PedidoResponse]:
    return [PedidoResponse.de(pedido) for pedido in pedidos.listar_pedidos(session, user, canal_pedido, pedido_status, page, limit)]


@router.post("/pedidos/{pedido_id}/pagamentos/mock", response_model=PagamentoResponse)
def mock_payment(pedido_id: int, data: PagamentoRequest, user: UsuarioAtual, session: Sessao) -> PagamentoResponse:
    return PagamentoResponse.model_validate(pedidos.pagar_mock(session, user, pedido_id, data.resultado))


@router.patch("/pedidos/{pedido_id}/status", response_model=PedidoResponse)
def update_order_status(pedido_id: int, data: StatusRequest, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    return PedidoResponse.de(pedidos.atualizar_status(session, user, pedido_id, data.status))


@router.post("/pedidos/{pedido_id}/cancelamento", response_model=PedidoResponse)
def cancel_order(pedido_id: int, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    """Cancela o pedido antes do pagamento e devolve a reserva. Repetir devolve o pedido já cancelado."""
    return PedidoResponse.de(pedidos.cancelar_pedido(session, user, pedido_id))
