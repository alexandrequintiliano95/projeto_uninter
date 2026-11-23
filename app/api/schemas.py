# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Modelos Pydantic de entrada e saída. Datas saem em UTC no formato ISO 8601 com sufixo Z."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.application.estoque import MovimentacaoDetalhada
from app.application.pedidos import PedidoDetalhado
from app.domain.enums import CanalPedido, CenarioPagamento, FinalidadeConsentimento, ResultadoPagamento, StatusPedido, TipoMovimentacao


def utc_iso(valor: datetime) -> str:
    return valor.isoformat() + "Z"


class LoginRequest(BaseModel):
    email: str
    senha: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    access_token: str
    token_type: str
    expires_in: int
    user_id: int
    perfil: str


class CadastroRequest(BaseModel):
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=180, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    senha: str = Field(description="De 8 a 128 caracteres, com pelo menos uma letra e um número.")
    aceite_termos: bool = Field(description="Obrigatório: precisa ser true para criar a conta.")
    aceita_fidelidade: bool = Field(False, description="Consentimento opcional para o programa de fidelidade.")
    aceita_marketing: bool = Field(False, description="Consentimento opcional para receber comunicações de marketing.")


class CadastroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str
    perfil: str


class UnidadeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    cidade: str
    uf: str


class CardapioItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    produto_id: int
    nome: str
    descricao: str
    preco_centavos: int
    saldo_disponivel: int


class PedidoItemRequest(BaseModel):
    produto_id: int = Field(gt=0)
    quantidade: int = Field(gt=0)


class PedidoRequest(BaseModel):
    unidade_id: int = Field(gt=0)
    canal_pedido: CanalPedido
    itens: list[PedidoItemRequest] = Field(min_length=1)


class ItemPedidoResponse(BaseModel):
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario_centavos: int


class PedidoResponse(BaseModel):
    id: int
    unidade_id: int
    cliente_id: int | None
    canal_pedido: CanalPedido
    status: StatusPedido
    total_centavos: int
    motivo_cancelamento: str | None
    expira_em: str
    itens: list[ItemPedidoResponse]

    @classmethod
    def de(cls, pedido: PedidoDetalhado) -> "PedidoResponse":
        return cls(
            id=pedido.id,
            unidade_id=pedido.unidade_id,
            cliente_id=pedido.cliente_id,
            canal_pedido=pedido.canal_pedido,
            status=pedido.status,
            total_centavos=pedido.total_centavos,
            motivo_cancelamento=pedido.motivo_cancelamento,
            expira_em=utc_iso(pedido.expira_em),
            itens=[ItemPedidoResponse(produto_id=item.produto_id, nome=item.nome, quantidade=item.quantidade, preco_unitario_centavos=item.preco_unitario_centavos) for item in pedido.itens],
        )


class PagamentoRequest(BaseModel):
    resultado: CenarioPagamento = Field(description="APROVADO e RECUSADO gravam o resultado. FALHA simula o provedor fora do ar: responde 503 e o pedido continua aguardando pagamento.")


class PagamentoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pedido_id: int
    status: ResultadoPagamento
    pedido_status: StatusPedido


class StatusRequest(BaseModel):
    status: StatusPedido = Field(description="Status de destino: EM_PREPARO, PRONTO ou ENTREGUE.")


class ConsentimentoRequest(BaseModel):
    finalidade: FinalidadeConsentimento
    concedido: bool
    versao_termo: str = "v1"


class ConsentimentoResponse(BaseModel):
    finalidade: FinalidadeConsentimento
    concedido: bool
    versao_termo: str
    criado_em: str


class ConsentimentoCriadoResponse(ConsentimentoResponse):
    id: int


class AuditoriaResponse(BaseModel):
    id: int
    acao: str
    tipo_entidade: str
    entidade_id: int
    detalhes: str
    criado_em: str


class MovimentacaoRequest(BaseModel):
    produto_id: int = Field(gt=0)
    tipo: TipoMovimentacao = Field(description="ENTRADA soma ao saldo livre; SAIDA subtrai, sem nunca retirar itens reservados.")
    quantidade: int = Field(gt=0)
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)] = Field(description="Obrigatório: por que o estoque mudou (ex.: reposição, perda, avaria).")


class MovimentacaoResponse(BaseModel):
    id: int
    unidade_id: int
    produto_id: int
    tipo: TipoMovimentacao
    quantidade: int
    motivo: str
    saldo_livre_anterior: int
    saldo_livre_novo: int
    usuario_id: int
    criado_em: str

    @classmethod
    def de(cls, movimentacao: MovimentacaoDetalhada) -> "MovimentacaoResponse":
        return cls(
            id=movimentacao.id,
            unidade_id=movimentacao.unidade_id,
            produto_id=movimentacao.produto_id,
            tipo=movimentacao.tipo,
            quantidade=movimentacao.quantidade,
            motivo=movimentacao.motivo,
            saldo_livre_anterior=movimentacao.saldo_livre_anterior,
            saldo_livre_novo=movimentacao.saldo_livre_novo,
            usuario_id=movimentacao.usuario_id,
            criado_em=utc_iso(movimentacao.criado_em),
        )
