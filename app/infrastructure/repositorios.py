# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Consultas ao banco. Cada repositório recebe a sessão da requisição; a confirmação (commit) fica na aplicação."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Auditoria, ConsentimentoEvento, ItemPedido, MovimentacaoEstoque, Pagamento, Pedido, Produto, ProdutoUnidade, Unidade, Usuario


class UsuarioRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def por_email(self, email: str) -> Usuario | None:
        return self.session.scalar(select(Usuario).where(Usuario.email == email))

    def obter(self, usuario_id: int) -> Usuario | None:
        return self.session.get(Usuario, usuario_id)

    def adicionar(self, usuario: Usuario) -> None:
        self.session.add(usuario)
        self.session.flush()


class CatalogoRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def unidades_ativas(self) -> list[Unidade]:
        return list(self.session.scalars(select(Unidade).where(Unidade.ativa.is_(True)).order_by(Unidade.id)))

    def unidade(self, unidade_id: int) -> Unidade | None:
        return self.session.get(Unidade, unidade_id)

    def cardapio(self, unidade_id: int, page: int, limit: int) -> list[tuple[ProdutoUnidade, Produto]]:
        rows = self.session.execute(
            select(ProdutoUnidade, Produto)
            .join(Produto, Produto.id == ProdutoUnidade.produto_id)
            .where(ProdutoUnidade.unidade_id == unidade_id, ProdutoUnidade.ativo.is_(True), Produto.ativo.is_(True))
            .order_by(Produto.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [(oferta, produto) for oferta, produto in rows]

    def produtos_ativos(self, produto_ids: list[int]) -> dict[int, Produto]:
        return {produto.id: produto for produto in self.session.scalars(select(Produto).where(Produto.id.in_(produto_ids), Produto.ativo.is_(True)))}


class OfertaRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ativas(self, unidade_id: int, produto_ids: list[int]) -> dict[int, ProdutoUnidade]:
        """Ofertas ativas da unidade, indexadas pelo ID do produto."""
        query = select(ProdutoUnidade).where(ProdutoUnidade.unidade_id == unidade_id, ProdutoUnidade.produto_id.in_(produto_ids), ProdutoUnidade.ativo.is_(True))
        return {oferta.produto_id: oferta for oferta in self.session.scalars(query)}

    def obter(self, oferta_id: int) -> ProdutoUnidade | None:
        return self.session.get(ProdutoUnidade, oferta_id)

    def da_unidade(self, unidade_id: int, produto_id: int) -> ProdutoUnidade | None:
        """Oferta do produto na unidade, ativa ou não (o estoque pode ser ajustado com a oferta pausada)."""
        return self.session.scalar(select(ProdutoUnidade).where(ProdutoUnidade.unidade_id == unidade_id, ProdutoUnidade.produto_id == produto_id))


class PedidoRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def obter(self, pedido_id: int) -> Pedido | None:
        return self.session.get(Pedido, pedido_id)

    def adicionar(self, pedido: Pedido) -> None:
        self.session.add(pedido)
        self.session.flush()

    def adicionar_item(self, item: ItemPedido) -> None:
        self.session.add(item)

    def itens(self, pedido_id: int) -> list[ItemPedido]:
        return list(self.session.scalars(select(ItemPedido).where(ItemPedido.pedido_id == pedido_id)))

    def itens_com_produto(self, pedido_id: int) -> list[tuple[ItemPedido, int]]:
        """Itens do pedido junto com o ID do produto do catálogo (não o ID da oferta)."""
        rows = self.session.execute(
            select(ItemPedido, ProdutoUnidade.produto_id)
            .join(ProdutoUnidade, ProdutoUnidade.id == ItemPedido.produto_unidade_id)
            .where(ItemPedido.pedido_id == pedido_id)
            .order_by(ItemPedido.id)
        )
        return [(item, produto_id) for item, produto_id in rows]

    def vencidos(self, agora: datetime, unidade_id: int | None = None) -> list[Pedido]:
        query = select(Pedido).where(Pedido.status == "AGUARDANDO_PAGAMENTO", Pedido.expira_em <= agora)
        if unidade_id:
            query = query.where(Pedido.unidade_id == unidade_id)
        return list(self.session.scalars(query))

    def listar(self, *, cliente_id: int | None, unidade_id: int | None, canal: str | None, status: str | None, page: int, limit: int) -> list[Pedido]:
        """Sempre filtra por um escopo: pedidos do cliente informado ou, sem cliente, da unidade informada."""
        query = select(Pedido).order_by(Pedido.id.desc()).offset((page - 1) * limit).limit(limit)
        if cliente_id is not None:
            query = query.where(Pedido.cliente_id == cliente_id)
        else:
            query = query.where(Pedido.unidade_id == unidade_id)
        if canal:
            query = query.where(Pedido.canal_pedido == canal)
        if status:
            query = query.where(Pedido.status == status)
        return list(self.session.scalars(query))


class PagamentoRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def do_pedido(self, pedido_id: int) -> Pagamento | None:
        return self.session.scalar(select(Pagamento).where(Pagamento.pedido_id == pedido_id))

    def adicionar(self, pagamento: Pagamento) -> None:
        self.session.add(pagamento)


class ConsentimentoRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def do_usuario(self, usuario_id: int) -> list[ConsentimentoEvento]:
        query = select(ConsentimentoEvento).where(ConsentimentoEvento.usuario_id == usuario_id).order_by(ConsentimentoEvento.finalidade, ConsentimentoEvento.id.desc())
        return list(self.session.scalars(query))

    def adicionar(self, evento: ConsentimentoEvento) -> None:
        self.session.add(evento)
        self.session.flush()


class AuditoriaRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def registrar(self, usuario_id: int | None, unidade_id: int | None, acao: str, entidade: str, entidade_id: int, detalhes: str = "") -> None:
        agora = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(Auditoria(usuario_id=usuario_id, unidade_id=unidade_id, acao=acao, tipo_entidade=entidade, entidade_id=entidade_id, detalhes=detalhes, criado_em=agora))

    def da_unidade(self, unidade_id: int | None, limite: int = 100) -> list[Auditoria]:
        return list(self.session.scalars(select(Auditoria).where(Auditoria.unidade_id == unidade_id).order_by(Auditoria.id.desc()).limit(limite)))


class MovimentacaoRepositorio:
    def __init__(self, session: Session) -> None:
        self.session = session

    def adicionar(self, movimentacao: MovimentacaoEstoque) -> None:
        self.session.add(movimentacao)
        self.session.flush()

    def da_unidade(self, unidade_id: int, produto_id: int | None, page: int, limit: int) -> list[tuple[MovimentacaoEstoque, ProdutoUnidade]]:
        """Movimentações da unidade, da mais recente para a mais antiga, junto com a oferta movimentada."""
        query = (
            select(MovimentacaoEstoque, ProdutoUnidade)
            .join(ProdutoUnidade, ProdutoUnidade.id == MovimentacaoEstoque.produto_unidade_id)
            .where(ProdutoUnidade.unidade_id == unidade_id)
            .order_by(MovimentacaoEstoque.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        if produto_id is not None:
            query = query.where(ProdutoUnidade.produto_id == produto_id)
        return [(movimentacao, oferta) for movimentacao, oferta in self.session.execute(query)]
