# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter, Query, status

from app.api.deps import Sessao, UsuarioAtual
from app.api.schemas import INTEIRO_INVALIDO, PEDIDO_NAO_ENCONTRADO, PagamentoRequest, PagamentoResponse, PedidoRequest, PedidoResponse, StatusRequest, respostas_de_erro
from app.application import pedidos
from app.domain.enums import CanalPedido, StatusPedido

router = APIRouter(tags=["Pedidos"])


@router.post("/pedidos", status_code=status.HTTP_201_CREATED, response_model=PedidoResponse, responses=respostas_de_erro(401, 403, 404, 409, 422, caminho="/pedidos", exemplos={403: ("CANAL_NAO_PERMITIDO", "Canal não permitido para este perfil."), 404: ("PRODUTO_INDISPONIVEL", "Produto inexistente ou indisponível na unidade."), 409: ("ESTOQUE_INSUFICIENTE", "Não há quantidade suficiente para um ou mais itens.")}, campo_invalido=("canalPedido", "Field required")), summary="Criar pedido")
def create_order(data: PedidoRequest, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    itens = [(item.produto_id, item.quantidade) for item in data.itens]
    return PedidoResponse.de(pedidos.criar_pedido(session, user, data.unidade_id, data.canal_pedido, itens, data.pontos_resgatados))


@router.get("/pedidos/{pedido_id}", response_model=PedidoResponse, responses=respostas_de_erro(401, 404, 422, caminho="/pedidos/42", exemplos={404: PEDIDO_NAO_ENCONTRADO}, campo_invalido=("pedido_id", INTEIRO_INVALIDO)), summary="Consultar pedido")
def get_order(pedido_id: int, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    return PedidoResponse.de(pedidos.consultar_pedido(session, user, pedido_id))


@router.get("/pedidos", response_model=list[PedidoResponse], responses=respostas_de_erro(401, 422, caminho="/pedidos", campo_invalido=("canalPedido", "Input should be 'APP', 'WEB', 'PICKUP', 'BALCAO' or 'TOTEM'")), summary="Listar pedidos")
def list_orders(
    user: UsuarioAtual,
    session: Sessao,
    canal_pedido: CanalPedido | None = Query(None, alias="canalPedido"),
    pedido_status: StatusPedido | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[PedidoResponse]:
    return [PedidoResponse.de(pedido) for pedido in pedidos.listar_pedidos(session, user, canal_pedido, pedido_status, page, limit)]


@router.post("/pedidos/{pedido_id}/pagamentos/mock", response_model=PagamentoResponse, responses=respostas_de_erro(401, 403, 404, 409, 422, 503, caminho="/pedidos/42/pagamentos/mock", exemplos={403: ("PERFIL_SEM_PERMISSAO", "Perfil não pode registrar pagamento."), 404: PEDIDO_NAO_ENCONTRADO, 409: ("PAGAMENTO_IMUTAVEL", "O pagamento já possui outro resultado.")}, campo_invalido=("resultado", "Input should be 'APROVADO', 'RECUSADO' or 'FALHA'")), summary="Pagar pedido (simulado)")
def mock_payment(pedido_id: int, data: PagamentoRequest, user: UsuarioAtual, session: Sessao) -> PagamentoResponse:
    return PagamentoResponse.model_validate(pedidos.pagar_mock(session, user, pedido_id, data.resultado))


@router.patch("/pedidos/{pedido_id}/status", response_model=PedidoResponse, responses=respostas_de_erro(401, 403, 404, 409, 422, caminho="/pedidos/42/status", exemplos={403: ("PERFIL_SEM_PERMISSAO", "Perfil não pode executar esta mudança de status."), 404: PEDIDO_NAO_ENCONTRADO, 409: ("TRANSICAO_INVALIDA", "Transição de status não permitida.")}, campo_invalido=("status", "Input should be 'AGUARDANDO_PAGAMENTO', 'CONFIRMADO', 'EM_PREPARO', 'PRONTO', 'ENTREGUE' or 'CANCELADO'")), summary="Avançar status do pedido")
def update_order_status(pedido_id: int, data: StatusRequest, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    return PedidoResponse.de(pedidos.atualizar_status(session, user, pedido_id, data.status))


@router.post("/pedidos/{pedido_id}/cancelamento", response_model=PedidoResponse, responses=respostas_de_erro(401, 403, 404, 409, 422, caminho="/pedidos/42/cancelamento", exemplos={403: ("PERFIL_SEM_PERMISSAO", "Perfil não pode cancelar pedidos."), 404: PEDIDO_NAO_ENCONTRADO, 409: ("PEDIDO_NAO_CANCELAVEL", "Somente pedidos aguardando pagamento podem ser cancelados.")}, campo_invalido=("pedido_id", INTEIRO_INVALIDO)), summary="Cancelar pedido antes do pagamento")
def cancel_order(pedido_id: int, user: UsuarioAtual, session: Sessao) -> PedidoResponse:
    """Cancela o pedido antes do pagamento e devolve a reserva. Repetir devolve o pedido já cancelado."""
    return PedidoResponse.de(pedidos.cancelar_pedido(session, user, pedido_id))
