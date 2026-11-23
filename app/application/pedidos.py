# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Casos de uso do pedido: criação com reserva, consulta, listagem, pagamento mock, cancelamento, mudança de status e expiração."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.enums import CanalPedido, CenarioPagamento, MotivoCancelamento, Perfil, ResultadoPagamento, StatusPedido
from app.domain.errors import Conflito, DadosInvalidos, NaoEncontrado, ServicoIndisponivel
from app.domain.regras import PRAZO_RESERVA, exigir_acesso_ao_pedido, exigir_pode_cancelar, exigir_pode_criar_pedido, exigir_pode_pagar, precisa_cancelar, validar_mudanca_status
from app.infrastructure.models import ItemPedido, Pagamento, Pedido, Usuario
from app.infrastructure.repositorios import AuditoriaRepositorio, CatalogoRepositorio, OfertaRepositorio, PagamentoRepositorio, PedidoRepositorio


@dataclass(frozen=True)
class ItemDetalhado:
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario_centavos: int


@dataclass(frozen=True)
class PedidoDetalhado:
    id: int
    unidade_id: int
    cliente_id: int | None
    canal_pedido: str
    status: str
    total_centavos: int
    motivo_cancelamento: str | None
    expira_em: datetime
    itens: list[ItemDetalhado]


@dataclass(frozen=True)
class ResultadoPagamentoMock:
    pedido_id: int
    status: str
    pedido_status: str


def _agora() -> datetime:
    """Horário UTC sem fuso, no mesmo formato gravado no banco."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _detalhar(session: Session, pedido: Pedido) -> PedidoDetalhado:
    itens = [
        ItemDetalhado(produto_id=produto_id, nome=item.nome_produto, quantidade=item.quantidade, preco_unitario_centavos=item.preco_unitario_centavos)
        for item, produto_id in PedidoRepositorio(session).itens_com_produto(pedido.id)
    ]
    return PedidoDetalhado(
        id=pedido.id,
        unidade_id=pedido.unidade_id,
        cliente_id=pedido.cliente_id,
        canal_pedido=pedido.canal_pedido,
        status=pedido.status,
        total_centavos=pedido.total_centavos,
        motivo_cancelamento=pedido.motivo_cancelamento,
        expira_em=pedido.expira_em,
        itens=itens,
    )


def _unidade_do_escopo(usuario: Usuario) -> int | None:
    return None if usuario.perfil == Perfil.CLIENTE else usuario.unidade_id


def _pedido_acessivel(session: Session, usuario: Usuario, pedido_id: int) -> Pedido:
    pedido = PedidoRepositorio(session).obter(pedido_id)
    if not pedido:
        raise NaoEncontrado("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
    exigir_acesso_ao_pedido(usuario.perfil, usuario.id, usuario.unidade_id, pedido.cliente_id, pedido.unidade_id)
    return pedido


def _movimentar_reserva(session: Session, pedido: Pedido, *, devolver: bool) -> None:
    """Tira os itens da reserva: devolve ao saldo livre (cancelamento) ou consome (pagamento aprovado)."""
    ofertas = OfertaRepositorio(session)
    for item in PedidoRepositorio(session).itens(pedido.id):
        oferta = ofertas.obter(item.produto_unidade_id)
        oferta.saldo_reservado -= item.quantidade
        if devolver:
            oferta.saldo_livre += item.quantidade


def _cancelar(session: Session, pedido: Pedido, motivo: MotivoCancelamento, agora: datetime) -> None:
    _movimentar_reserva(session, pedido, devolver=True)
    pedido.status = StatusPedido.CANCELADO.value
    pedido.motivo_cancelamento = motivo.value
    pedido.atualizado_em = agora


def expirar_pedidos(session: Session, unidade_id: int | None = None) -> None:
    """Cancela pedidos aguardando pagamento cujo prazo venceu e devolve a reserva. Não confirma a transação."""
    agora = _agora()
    auditoria = AuditoriaRepositorio(session)
    for pedido in PedidoRepositorio(session).vencidos(agora, unidade_id):
        _cancelar(session, pedido, MotivoCancelamento.PRAZO_EXPIRADO, agora)
        auditoria.registrar(None, pedido.unidade_id, "PEDIDO_EXPIRADO", "PEDIDO", pedido.id)


def criar_pedido(session: Session, usuario: Usuario, unidade_id: int, canal: CanalPedido, itens: list[tuple[int, int]]) -> PedidoDetalhado:
    """Cria o pedido e reserva o estoque. `itens` são pares (produto_id, quantidade)."""
    exigir_pode_criar_pedido(usuario.perfil, canal, usuario.unidade_id, unidade_id)
    catalogo = CatalogoRepositorio(session)
    unidade = catalogo.unidade(unidade_id)
    if not unidade or not unidade.ativa:
        raise NaoEncontrado("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.")
    expirar_pedidos(session, unidade_id)
    produto_ids = [produto_id for produto_id, _ in itens]
    if len(produto_ids) != len(set(produto_ids)):
        raise DadosInvalidos("ITENS_DUPLICADOS", "O mesmo produto não pode aparecer duas vezes.")
    ofertas = OfertaRepositorio(session).ativas(unidade_id, produto_ids)
    produtos = catalogo.produtos_ativos(produto_ids)
    if len(ofertas) != len(produto_ids) or len(produtos) != len(produto_ids):
        raise NaoEncontrado("PRODUTO_INDISPONIVEL", "Produto inexistente ou indisponível na unidade.")
    total = 0
    for produto_id, quantidade in itens:
        oferta = ofertas[produto_id]
        if oferta.saldo_livre < quantidade:
            raise Conflito("ESTOQUE_INSUFICIENTE", "Não há quantidade suficiente para um ou mais itens.")
        total += oferta.preco_centavos * quantidade
    agora = _agora()
    pedido = Pedido(
        unidade_id=unidade_id,
        criado_por_id=usuario.id,
        cliente_id=usuario.id if usuario.perfil == Perfil.CLIENTE else None,
        canal_pedido=canal.value,
        status=StatusPedido.AGUARDANDO_PAGAMENTO.value,
        total_centavos=total,
        criado_em=agora,
        atualizado_em=agora,
        expira_em=agora + PRAZO_RESERVA,
    )
    repositorio = PedidoRepositorio(session)
    repositorio.adicionar(pedido)
    for produto_id, quantidade in itens:
        oferta = ofertas[produto_id]
        oferta.saldo_livre -= quantidade
        oferta.saldo_reservado += quantidade
        repositorio.adicionar_item(ItemPedido(pedido_id=pedido.id, produto_unidade_id=oferta.id, nome_produto=produtos[produto_id].nome, quantidade=quantidade, preco_unitario_centavos=oferta.preco_centavos))
    AuditoriaRepositorio(session).registrar(usuario.id, unidade_id, "PEDIDO_CRIADO", "PEDIDO", pedido.id)
    session.commit()
    return _detalhar(session, pedido)


def consultar_pedido(session: Session, usuario: Usuario, pedido_id: int) -> PedidoDetalhado:
    expirar_pedidos(session, _unidade_do_escopo(usuario))
    pedido = _pedido_acessivel(session, usuario, pedido_id)
    session.commit()
    return _detalhar(session, pedido)


def listar_pedidos(session: Session, usuario: Usuario, canal: CanalPedido | None, status: StatusPedido | None, page: int, limit: int) -> list[PedidoDetalhado]:
    expirar_pedidos(session, _unidade_do_escopo(usuario))
    pedidos = PedidoRepositorio(session).listar(
        cliente_id=usuario.id if usuario.perfil == Perfil.CLIENTE else None,
        unidade_id=usuario.unidade_id,
        canal=canal.value if canal else None,
        status=status.value if status else None,
        page=page,
        limit=limit,
    )
    session.commit()
    return [_detalhar(session, pedido) for pedido in pedidos]


def pagar_mock(session: Session, usuario: Usuario, pedido_id: int, cenario: CenarioPagamento) -> ResultadoPagamentoMock:
    """Simula o provedor de pagamento.

    APROVADO e RECUSADO gravam o pagamento uma única vez: repetir o mesmo resultado devolve o existente e trocar é conflito.
    FALHA simula o provedor fora do ar: responde 503, não grava pagamento e o pedido continua aguardando (sujeito ao prazo).
    """
    exigir_pode_pagar(usuario.perfil)
    pedido = _pedido_acessivel(session, usuario, pedido_id)
    expirar_pedidos(session, pedido.unidade_id)
    # A expiração é gravada à parte: vale mesmo que o pagamento seja recusado logo abaixo (ex.: pedido vencido).
    session.commit()
    pagamentos = PagamentoRepositorio(session)
    auditoria = AuditoriaRepositorio(session)
    existente = pagamentos.do_pedido(pedido.id)
    if existente:
        if existente.status != cenario:
            raise Conflito("PAGAMENTO_IMUTAVEL", "O pagamento já possui outro resultado.")
        return ResultadoPagamentoMock(pedido_id=pedido.id, status=existente.status, pedido_status=pedido.status)
    if pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO:
        raise Conflito("PEDIDO_SEM_PAGAMENTO", "Pedido não aguarda pagamento.")
    if cenario == CenarioPagamento.FALHA:
        auditoria.registrar(usuario.id, pedido.unidade_id, "PAGAMENTO_FALHA", "PEDIDO", pedido.id, "Provedor de pagamento indisponível (simulado)")
        session.commit()
        raise ServicoIndisponivel("PAGAMENTO_INDISPONIVEL", "Serviço de pagamento indisponível no momento. O pedido continua aguardando pagamento.")
    resultado = ResultadoPagamento(cenario.value)
    agora = _agora()
    pagamentos.adicionar(Pagamento(pedido_id=pedido.id, status=resultado.value, valor_centavos=pedido.total_centavos, criado_em=agora))
    if resultado == ResultadoPagamento.APROVADO:
        _movimentar_reserva(session, pedido, devolver=False)
        pedido.status = StatusPedido.CONFIRMADO.value
        pedido.motivo_cancelamento = None
        pedido.atualizado_em = agora
    else:
        _cancelar(session, pedido, MotivoCancelamento.PAGAMENTO_RECUSADO, agora)
    auditoria.registrar(usuario.id, pedido.unidade_id, "PAGAMENTO_MOCK", "PEDIDO", pedido.id, resultado.value)
    session.commit()
    return ResultadoPagamentoMock(pedido_id=pedido.id, status=resultado.value, pedido_status=pedido.status)


def cancelar_pedido(session: Session, usuario: Usuario, pedido_id: int) -> PedidoDetalhado:
    """Cancelamento a pedido do usuário, só antes do pagamento. Devolve a reserva; repetir não tem efeito."""
    exigir_pode_cancelar(usuario.perfil)
    pedido = _pedido_acessivel(session, usuario, pedido_id)
    expirar_pedidos(session, pedido.unidade_id)
    session.commit()
    if precisa_cancelar(pedido.status):
        _cancelar(session, pedido, MotivoCancelamento.SOLICITADO, _agora())
        AuditoriaRepositorio(session).registrar(usuario.id, pedido.unidade_id, "PEDIDO_CANCELADO", "PEDIDO", pedido.id, MotivoCancelamento.SOLICITADO.value)
        session.commit()
    return _detalhar(session, pedido)


def atualizar_status(session: Session, usuario: Usuario, pedido_id: int, destino: StatusPedido) -> PedidoDetalhado:
    pedido = _pedido_acessivel(session, usuario, pedido_id)
    if validar_mudanca_status(usuario.perfil, pedido.status, destino):
        pedido.status = destino.value
        pedido.atualizado_em = _agora()
        AuditoriaRepositorio(session).registrar(usuario.id, pedido.unidade_id, "STATUS_ATUALIZADO", "PEDIDO", pedido.id, pedido.status)
        session.commit()
    return _detalhar(session, pedido)
