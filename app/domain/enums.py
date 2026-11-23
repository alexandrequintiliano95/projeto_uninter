# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from enum import StrEnum


class Perfil(StrEnum):
    CLIENTE = "CLIENTE"
    ATENDENTE = "ATENDENTE"
    COZINHA = "COZINHA"
    GERENTE = "GERENTE"


class CanalPedido(StrEnum):
    APP = "APP"
    WEB = "WEB"
    PICKUP = "PICKUP"
    BALCAO = "BALCAO"
    TOTEM = "TOTEM"


class StatusPedido(StrEnum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    CONFIRMADO = "CONFIRMADO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class ResultadoPagamento(StrEnum):
    """Resultado gravado no pagamento."""

    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"


class CenarioPagamento(StrEnum):
    """Cenário pedido ao simulador de pagamento. FALHA simula o provedor fora do ar e não grava pagamento."""

    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    FALHA = "FALHA"


class FinalidadeConsentimento(StrEnum):
    FIDELIDADE = "FIDELIDADE"
    MARKETING = "MARKETING"


class TipoMovimentacao(StrEnum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class TipoMovimentoFidelidade(StrEnum):
    """CREDITO: pontos ganhos em pedido pago. DEBITO: pontos usados como desconto. ESTORNO: pontos devolvidos quando o pedido com desconto é cancelado."""

    CREDITO = "CREDITO"
    DEBITO = "DEBITO"
    ESTORNO = "ESTORNO"


class MotivoCancelamento(StrEnum):
    SOLICITADO = "SOLICITADO"
    PAGAMENTO_RECUSADO = "PAGAMENTO_RECUSADO"
    PRAZO_EXPIRADO = "PRAZO_EXPIRADO"
