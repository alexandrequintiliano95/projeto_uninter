# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Programa de fidelidade: crédito de pontos no pagamento aprovado, resgate como desconto no pedido e estorno no cancelamento."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.application.consentimentos import consentimento_ativo
from app.domain.enums import FinalidadeConsentimento, Perfil, TipoMovimentoFidelidade
from app.domain.regras import desconto_do_resgate, exigir_perfil, exigir_pode_resgatar, pontos_ganhos
from app.infrastructure.models import FidelidadeMovimento, Pedido, Usuario
from app.infrastructure.repositorios import FidelidadeRepositorio


@dataclass(frozen=True)
class ExtratoFidelidade:
    saldo_pontos: int
    consentimento_ativo: bool
    extrato: list[FidelidadeMovimento]


def _registrar(session: Session, usuario_id: int, pedido_id: int, tipo: TipoMovimentoFidelidade, pontos: int) -> None:
    movimento = FidelidadeMovimento(usuario_id=usuario_id, pedido_id=pedido_id, tipo=tipo.value, pontos=pontos, criado_em=datetime.now(timezone.utc).replace(tzinfo=None))
    FidelidadeRepositorio(session).adicionar(movimento)


def _ativo(session: Session, usuario_id: int) -> bool:
    return consentimento_ativo(session, usuario_id, FinalidadeConsentimento.FIDELIDADE)


def calcular_desconto(session: Session, usuario: Usuario, pontos: int, total_centavos: int) -> int:
    """Confere quem resgata, o consentimento, o saldo e os limites. Não grava nada."""
    exigir_pode_resgatar(usuario.perfil, _ativo(session, usuario.id))
    return desconto_do_resgate(pontos, FidelidadeRepositorio(session).saldo(usuario.id), total_centavos)


def debitar_resgate(session: Session, pedido: Pedido) -> None:
    if pedido.pontos_resgatados:
        _registrar(session, pedido.cliente_id, pedido.id, TipoMovimentoFidelidade.DEBITO, pedido.pontos_resgatados)


def estornar_resgate(session: Session, pedido: Pedido) -> None:
    """Pedido com desconto por pontos que foi cancelado, recusado ou venceu: os pontos voltam ao saldo."""
    if pedido.pontos_resgatados and pedido.cliente_id:
        _registrar(session, pedido.cliente_id, pedido.id, TipoMovimentoFidelidade.ESTORNO, pedido.pontos_resgatados)


def creditar_pagamento(session: Session, pedido: Pedido) -> None:
    """1 ponto por real efetivamente pago, só para cliente identificado com consentimento ativo no momento do pagamento."""
    if not pedido.cliente_id or not _ativo(session, pedido.cliente_id):
        return
    pontos = pontos_ganhos(pedido.total_centavos)
    if pontos:
        _registrar(session, pedido.cliente_id, pedido.id, TipoMovimentoFidelidade.CREDITO, pontos)


def consultar(session: Session, usuario: Usuario) -> ExtratoFidelidade:
    exigir_perfil(usuario.perfil, frozenset({Perfil.CLIENTE}), "Somente clientes participam do programa de fidelidade.")
    repositorio = FidelidadeRepositorio(session)
    return ExtratoFidelidade(saldo_pontos=repositorio.saldo(usuario.id), consentimento_ativo=_ativo(session, usuario.id), extrato=repositorio.extrato(usuario.id))
