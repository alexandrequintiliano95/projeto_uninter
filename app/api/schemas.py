# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Modelos Pydantic de entrada e saída. Datas saem em UTC no formato ISO 8601 com sufixo Z."""

from datetime import datetime
from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints

from app.application.estoque import MovimentacaoDetalhada
from app.application.pedidos import PedidoDetalhado
from app.domain.enums import CanalPedido, CenarioPagamento, FinalidadeConsentimento, ResultadoPagamento, StatusPedido, TipoMovimentacao, TipoMovimentoFidelidade


def utc_iso(valor: datetime) -> str:
    return valor.isoformat() + "Z"


class ErroDetalhe(BaseModel):
    field: str = Field(description="Campo com problema, no formato do corpo ou da query (ex.: itens.0.quantidade).")
    message: str


class ErroResponse(BaseModel):
    """Formato único de todas as respostas de erro da API."""

    error: str = Field(description="Código do erro.", examples=["PERFIL_SEM_PERMISSAO"])
    message: str = Field(description="Mensagem para o usuário.")
    details: list[ErroDetalhe] = Field(description="Um item por campo inválido nos erros 422; vazio nos demais.")
    timestamp: str = Field(description="Data e hora do erro em UTC (ISO 8601).", examples=["2026-11-23T18:16:23Z"])
    path: str = Field(description="Caminho chamado.", examples=["/pedidos"])


DESCRICAO_DOS_ERROS = {
    401: "Não autenticado: token ausente, inválido ou expirado, ou usuário inativo.",
    403: "Perfil ou unidade sem permissão para a operação.",
    404: "Registro inexistente ou fora do escopo do usuário.",
    409: "Conflito com o estado atual (estoque, status, pagamento ou cadastro).",
    422: "Dados inválidos ou fora das regras de negócio.",
    503: "Provedor de pagamento indisponível (falha simulada).",
}


# Exemplos usados quando a rota não informa um próprio. As mensagens são as que a API devolve de verdade.
EXEMPLOS_DE_ERRO_PADRAO = {
    401: ("NAO_AUTENTICADO", "Token não informado."),
    422: ("DADOS_INVALIDOS", "Um ou mais campos da requisição são inválidos."),
    503: ("PAGAMENTO_INDISPONIVEL", "Serviço de pagamento indisponível no momento. O pedido continua aguardando pagamento."),
}
PEDIDO_NAO_ENCONTRADO = ("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
INTEIRO_INVALIDO = "Input should be a valid integer, unable to parse string as an integer"


def respostas_de_erro(*codigos: int, caminho: str, exemplos: dict[int, tuple[str, str]] | None = None, campo_invalido: tuple[str, str] | None = None) -> dict[int, dict]:
    """Documenta no Swagger os erros que a rota pode devolver, no formato ErroResponse, cada um com um exemplo.

    `exemplos` traz o código e a mensagem de erro de cada status; 403, 404 e 409 não têm padrão e precisam ser informados.
    `campo_invalido` (campo, mensagem) preenche `details` no exemplo do 422 de validação.
    """
    exemplos = {**EXEMPLOS_DE_ERRO_PADRAO, **(exemplos or {})}
    respostas = {}
    for codigo in codigos:
        erro, mensagem = exemplos[codigo]
        details = [{"field": campo_invalido[0], "message": campo_invalido[1]}] if erro == "DADOS_INVALIDOS" and campo_invalido else []
        exemplo = {"error": erro, "message": mensagem, "details": details, "timestamp": "2026-11-23T18:16:23Z", "path": caminho}
        respostas[codigo] = {"model": ErroResponse, "description": DESCRICAO_DOS_ERROS[codigo], "content": {"application/json": {"example": exemplo}}}
    return respostas


def exemplos(*valores: dict, **config) -> ConfigDict:
    """Configuração do modelo com exemplos que o Swagger mostra no lugar dos valores genéricos."""
    return ConfigDict(json_schema_extra={"examples": list(valores)}, **config)


EXPIRA_EM = "2026-11-23T18:31:23Z"
CRIADO_EM = "2026-11-23T18:16:23Z"


class LoginRequest(BaseModel):
    model_config = exemplos({"email": "cliente@raizes.local", "senha": "Cliente@123"})
    email: str
    senha: str


class LoginResponse(BaseModel):
    model_config = exemplos({"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "token_type": "Bearer", "expires_in": 3600, "user_id": 1, "perfil": "CLIENTE"}, from_attributes=True)
    access_token: str
    token_type: str
    expires_in: int
    user_id: int
    perfil: str


class CadastroRequest(BaseModel):
    model_config = exemplos({"nome": "Maria das Dores", "email": "maria@exemplo.com", "senha": "Segura123", "aceite_termos": True, "aceita_fidelidade": True, "aceita_marketing": False})
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=180, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    senha: str = Field(description="De 8 a 128 caracteres, com pelo menos uma letra e um número.")
    aceite_termos: bool = Field(description="Obrigatório: precisa ser true para criar a conta.")
    aceita_fidelidade: bool = Field(False, description="Consentimento opcional para o programa de fidelidade.")
    aceita_marketing: bool = Field(False, description="Consentimento opcional para receber comunicações de marketing.")


class CadastroResponse(BaseModel):
    model_config = exemplos({"id": 6, "nome": "Maria das Dores", "email": "maria@exemplo.com", "perfil": "CLIENTE"}, from_attributes=True)
    id: int
    nome: str
    email: str
    perfil: str


class UnidadeResponse(BaseModel):
    model_config = exemplos({"id": 1, "nome": "Raízes Recife Centro", "cidade": "Recife", "uf": "PE"}, from_attributes=True)
    id: int
    nome: str
    cidade: str
    uf: str


class CardapioItem(BaseModel):
    model_config = exemplos({"produto_id": 1, "nome": "Tapioca de Carne de Sol", "descricao": "Tapioca recheada com carne de sol", "preco_centavos": 1890, "saldo_disponivel": 20}, from_attributes=True)
    produto_id: int
    nome: str
    descricao: str
    preco_centavos: int
    saldo_disponivel: int


# O corpo do pedido usa os nomes do roteiro (unidadeId, canalPedido, produtoId, pontosResgatados).
# Os nomes antigos (unidade_id, canal_pedido, produto_id, pontos_resgatados) continuam aceitos.
class PedidoItemRequest(BaseModel):
    produto_id: int = Field(gt=0, validation_alias=AliasChoices("produtoId", "produto_id"))
    quantidade: int = Field(gt=0)


class PedidoRequest(BaseModel):
    model_config = exemplos({"unidadeId": 1, "canalPedido": "TOTEM", "itens": [{"produtoId": 1, "quantidade": 2}], "pontosResgatados": 0})
    unidade_id: int = Field(gt=0, validation_alias=AliasChoices("unidadeId", "unidade_id"))
    canal_pedido: CanalPedido = Field(validation_alias=AliasChoices("canalPedido", "canal_pedido"), description="Canal de venda: APP, WEB, PICKUP, BALCAO ou TOTEM.")
    itens: list[PedidoItemRequest] = Field(min_length=1)
    pontos_resgatados: int = Field(
        0,
        ge=0,
        multiple_of=100,
        validation_alias=AliasChoices("pontosResgatados", "pontos_resgatados"),
        description="Pontos de fidelidade usados como desconto (múltiplos de 100; cada 100 valem R$ 5,00; até 50% do pedido). Só para clientes com consentimento ativo.",
    )


class ItemPedidoResponse(BaseModel):
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario_centavos: int


class PedidoResponse(BaseModel):
    model_config = exemplos({"id": 42, "unidade_id": 1, "cliente_id": 1, "canal_pedido": "TOTEM", "status": "AGUARDANDO_PAGAMENTO", "total_centavos": 3780, "desconto_centavos": 0, "pontos_resgatados": 0, "motivo_cancelamento": None, "expira_em": EXPIRA_EM, "itens": [{"produto_id": 1, "nome": "Tapioca de Carne de Sol", "quantidade": 2, "preco_unitario_centavos": 1890}]})
    id: int
    unidade_id: int
    cliente_id: int | None
    canal_pedido: CanalPedido
    status: StatusPedido
    total_centavos: int
    desconto_centavos: int
    pontos_resgatados: int
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
            desconto_centavos=pedido.desconto_centavos,
            pontos_resgatados=pedido.pontos_resgatados,
            motivo_cancelamento=pedido.motivo_cancelamento,
            expira_em=utc_iso(pedido.expira_em),
            itens=[ItemPedidoResponse(produto_id=item.produto_id, nome=item.nome, quantidade=item.quantidade, preco_unitario_centavos=item.preco_unitario_centavos) for item in pedido.itens],
        )


class PagamentoRequest(BaseModel):
    model_config = exemplos({"resultado": "APROVADO"})
    resultado: CenarioPagamento = Field(description="APROVADO e RECUSADO gravam o resultado. FALHA simula o provedor fora do ar: responde 503 e o pedido continua aguardando pagamento.")


class PagamentoResponse(BaseModel):
    model_config = exemplos({"pedido_id": 42, "status": "APROVADO", "pedido_status": "CONFIRMADO"}, from_attributes=True)
    pedido_id: int
    status: ResultadoPagamento
    pedido_status: StatusPedido


class StatusRequest(BaseModel):
    model_config = exemplos({"status": "EM_PREPARO"})
    status: StatusPedido = Field(description="Status de destino: EM_PREPARO, PRONTO ou ENTREGUE.")


class ConsentimentoRequest(BaseModel):
    model_config = exemplos({"finalidade": "FIDELIDADE", "concedido": True, "versao_termo": "v1"})
    finalidade: FinalidadeConsentimento
    concedido: bool
    versao_termo: str = "v1"


class ConsentimentoResponse(BaseModel):
    model_config = exemplos({"finalidade": "FIDELIDADE", "concedido": True, "versao_termo": "v1", "criado_em": CRIADO_EM})
    finalidade: FinalidadeConsentimento
    concedido: bool
    versao_termo: str
    criado_em: str


class ConsentimentoCriadoResponse(ConsentimentoResponse):
    model_config = exemplos({"id": 7, "finalidade": "FIDELIDADE", "concedido": True, "versao_termo": "v1", "criado_em": CRIADO_EM})
    id: int


class AuditoriaResponse(BaseModel):
    model_config = exemplos({"id": 120, "acao": "STATUS_ATUALIZADO", "tipo_entidade": "PEDIDO", "entidade_id": 42, "detalhes": "EM_PREPARO", "criado_em": CRIADO_EM})
    id: int
    acao: str
    tipo_entidade: str
    entidade_id: int
    detalhes: str
    criado_em: str


class MovimentacaoRequest(BaseModel):
    model_config = exemplos({"produto_id": 1, "tipo": "ENTRADA", "quantidade": 10, "motivo": "Reposição do fornecedor"})
    produto_id: int = Field(gt=0)
    tipo: TipoMovimentacao = Field(description="ENTRADA soma ao saldo livre; SAIDA subtrai, sem nunca retirar itens reservados.")
    quantidade: int = Field(gt=0)
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)] = Field(description="Obrigatório: por que o estoque mudou (ex.: reposição, perda, avaria).")


class MovimentacaoResponse(BaseModel):
    model_config = exemplos({"id": 3, "unidade_id": 1, "produto_id": 1, "tipo": "ENTRADA", "quantidade": 10, "motivo": "Reposição do fornecedor", "saldo_livre_anterior": 20, "saldo_livre_novo": 30, "usuario_id": 4, "criado_em": CRIADO_EM})
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


class MovimentoFidelidadeResponse(BaseModel):
    id: int
    pedido_id: int
    tipo: TipoMovimentoFidelidade
    pontos: int
    criado_em: str


class RegrasFidelidadeResponse(BaseModel):
    pontos_por_real_pago: int
    pontos_por_resgate: int
    desconto_por_resgate_centavos: int
    desconto_maximo_percentual: int


class FidelidadeResponse(BaseModel):
    model_config = exemplos({"saldo_pontos": 113, "consentimento_ativo": True, "regras": {"pontos_por_real_pago": 1, "pontos_por_resgate": 100, "desconto_por_resgate_centavos": 500, "desconto_maximo_percentual": 50}, "extrato": [{"id": 1, "pedido_id": 42, "tipo": "CREDITO", "pontos": 113, "criado_em": CRIADO_EM}]})
    saldo_pontos: int
    consentimento_ativo: bool
    regras: RegrasFidelidadeResponse
    extrato: list[MovimentoFidelidadeResponse]
