"""Entrada e saída manual de estoque pelo gerente, com motivo e histórico."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.application.pedidos import expirar_pedidos
from app.domain.enums import TipoMovimentacao
from app.domain.errors import NaoEncontrado
from app.domain.regras import exigir_gerente_da_unidade, saldo_livre_apos_movimentacao
from app.infrastructure.models import MovimentacaoEstoque, ProdutoUnidade, Usuario
from app.infrastructure.repositorios import AuditoriaRepositorio, MovimentacaoRepositorio, OfertaRepositorio


@dataclass(frozen=True)
class MovimentacaoDetalhada:
    id: int
    unidade_id: int
    produto_id: int
    tipo: str
    quantidade: int
    motivo: str
    saldo_livre_anterior: int
    saldo_livre_novo: int
    usuario_id: int
    criado_em: datetime


def _detalhar(movimentacao: MovimentacaoEstoque, oferta: ProdutoUnidade) -> MovimentacaoDetalhada:
    return MovimentacaoDetalhada(
        id=movimentacao.id,
        unidade_id=oferta.unidade_id,
        produto_id=oferta.produto_id,
        tipo=movimentacao.tipo,
        quantidade=movimentacao.quantidade,
        motivo=movimentacao.motivo,
        saldo_livre_anterior=movimentacao.saldo_livre_anterior,
        saldo_livre_novo=movimentacao.saldo_livre_novo,
        usuario_id=movimentacao.usuario_id,
        criado_em=movimentacao.criado_em,
    )


def registrar_movimentacao(session: Session, usuario: Usuario, unidade_id: int, produto_id: int, tipo: TipoMovimentacao, quantidade: int, motivo: str) -> MovimentacaoDetalhada:
    """Soma (entrada) ou subtrai (saída) do saldo livre da oferta. Itens reservados em pedidos nunca são retirados."""
    exigir_gerente_da_unidade(usuario.perfil, usuario.unidade_id, unidade_id)
    # Reservas vencidas voltam ao saldo livre antes do ajuste; a expiração é gravada mesmo que o ajuste seja recusado.
    expirar_pedidos(session, unidade_id)
    session.commit()
    oferta = OfertaRepositorio(session).da_unidade(unidade_id, produto_id)
    if not oferta:
        raise NaoEncontrado("PRODUTO_INDISPONIVEL", "Produto sem oferta nesta unidade.")
    anterior = oferta.saldo_livre
    novo = saldo_livre_apos_movimentacao(anterior, tipo, quantidade)
    movimentacao = MovimentacaoEstoque(
        produto_unidade_id=oferta.id,
        usuario_id=usuario.id,
        tipo=tipo.value,
        quantidade=quantidade,
        motivo=motivo,
        saldo_livre_anterior=anterior,
        saldo_livre_novo=novo,
        criado_em=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    oferta.saldo_livre = novo
    MovimentacaoRepositorio(session).adicionar(movimentacao)
    detalhes = f"{tipo.value} de {quantidade} do produto {produto_id}: saldo livre {anterior} -> {novo}"
    AuditoriaRepositorio(session).registrar(usuario.id, unidade_id, "ESTOQUE_AJUSTADO", "MOVIMENTACAO_ESTOQUE", movimentacao.id, detalhes)
    session.commit()
    return _detalhar(movimentacao, oferta)


def listar_movimentacoes(session: Session, usuario: Usuario, unidade_id: int, produto_id: int | None, page: int, limit: int) -> list[MovimentacaoDetalhada]:
    exigir_gerente_da_unidade(usuario.perfil, usuario.unidade_id, unidade_id)
    return [_detalhar(movimentacao, oferta) for movimentacao, oferta in MovimentacaoRepositorio(session).da_unidade(unidade_id, produto_id, page, limit)]
