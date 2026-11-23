from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Unidade(Base):
    __tablename__ = "unidade"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    cidade: Mapped[str] = mapped_column(String(80), nullable=False)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"), nullable=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(String(20), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("perfil IN ('CLIENTE','ATENDENTE','COZINHA','GERENTE')", name="ck_usuario_perfil"),)


class Produto(Base):
    __tablename__ = "produto"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProdutoUnidade(Base):
    __tablename__ = "produto_unidade"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"), nullable=False)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id"), nullable=False)
    preco_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    saldo_livre: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saldo_reservado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint("unidade_id", "produto_id", name="uq_produto_unidade"),
        CheckConstraint("preco_centavos > 0", name="ck_preco_positivo"),
        CheckConstraint("saldo_livre >= 0 AND saldo_reservado >= 0", name="ck_saldos_nao_negativos"),
    )


class Pedido(Base):
    __tablename__ = "pedido"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"), nullable=False)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    canal_pedido: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="AGUARDANDO_PAGAMENTO")
    total_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        CheckConstraint("canal_pedido IN ('APP','TOTEM','BALCAO','PICKUP','WEB')", name="ck_pedido_canal"),
        CheckConstraint("status IN ('AGUARDANDO_PAGAMENTO','CONFIRMADO','EM_PREPARO','PRONTO','ENTREGUE','CANCELADO')", name="ck_pedido_status"),
        CheckConstraint("total_centavos > 0", name="ck_pedido_total_positivo"),
    )


class ItemPedido(Base):
    __tablename__ = "item_pedido"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"), nullable=False)
    produto_unidade_id: Mapped[int] = mapped_column(ForeignKey("produto_unidade.id"), nullable=False)
    nome_produto: Mapped[str] = mapped_column(String(120), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    preco_unitario_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("pedido_id", "produto_unidade_id", name="uq_item_pedido_produto"),
        CheckConstraint("quantidade > 0", name="ck_item_quantidade_positiva"),
        CheckConstraint("preco_unitario_centavos > 0", name="ck_item_preco_positivo"),
    )


class Pagamento(Base):
    __tablename__ = "pagamento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    valor_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('APROVADO','RECUSADO')", name="ck_pagamento_status"),
        CheckConstraint("valor_centavos > 0", name="ck_pagamento_valor_positivo"),
    )


class ConsentimentoEvento(Base):
    __tablename__ = "consentimento_evento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    finalidade: Mapped[str] = mapped_column(String(15), nullable=False)
    concedido: Mapped[bool] = mapped_column(Boolean, nullable=False)
    versao_termo: Mapped[str] = mapped_column(String(30), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (CheckConstraint("finalidade IN ('FIDELIDADE','MARKETING')", name="ck_consentimento_finalidade"),)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"), nullable=True)
    acao: Mapped[str] = mapped_column(String(50), nullable=False)
    tipo_entidade: Mapped[str] = mapped_column(String(30), nullable=False)
    entidade_id: Mapped[int] = mapped_column(Integer, nullable=False)
    detalhes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MovimentacaoEstoque(Base):
    """Histórico de entradas e saídas manuais do saldo livre de uma oferta, com o motivo informado pelo gerente."""

    __tablename__ = "movimentacao_estoque"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    produto_unidade_id: Mapped[int] = mapped_column(ForeignKey("produto_unidade.id"), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(7), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str] = mapped_column(String(200), nullable=False)
    saldo_livre_anterior: Mapped[int] = mapped_column(Integer, nullable=False)
    saldo_livre_novo: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        CheckConstraint("tipo IN ('ENTRADA','SAIDA')", name="ck_movimentacao_tipo"),
        CheckConstraint("quantidade > 0", name="ck_movimentacao_quantidade_positiva"),
        CheckConstraint("saldo_livre_anterior >= 0 AND saldo_livre_novo >= 0", name="ck_movimentacao_saldos_nao_negativos"),
    )
