"""Modelos Pydantic de entrada e saída. Datas saem em UTC no formato ISO 8601 com sufixo Z."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.application.pedidos import PedidoDetalhado
from app.domain.enums import CanalPedido, CenarioPagamento, FinalidadeConsentimento, ResultadoPagamento, StatusPedido


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
