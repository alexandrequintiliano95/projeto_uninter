# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Regras de negócio puras. Recebem valores simples e lançam ErroDominio quando a operação não é permitida."""

from datetime import timedelta

from .enums import CanalPedido, Perfil, StatusPedido, TipoMovimentacao
from .errors import Conflito, DadosInvalidos, NaoEncontrado, PermissaoNegada

PRAZO_RESERVA = timedelta(minutes=15)
VERSAO_TERMOS_DE_USO = "v1"

# Fidelidade: 1 ponto por real pago; cada lote de 100 pontos vale R$ 5,00 de desconto, até 50% do pedido.
CENTAVOS_POR_PONTO_GANHO = 100
PONTOS_POR_RESGATE = 100
CENTAVOS_POR_RESGATE = 500
DESCONTO_MAXIMO_PERCENTUAL = 50

CANAIS_CLIENTE = frozenset({CanalPedido.APP, CanalPedido.WEB, CanalPedido.PICKUP})
CANAIS_EQUIPE = frozenset({CanalPedido.BALCAO, CanalPedido.TOTEM, CanalPedido.PICKUP})
PERFIS_QUE_PAGAM = frozenset({Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE})
PERFIS_QUE_CANCELAM = frozenset({Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE})

# Transições manuais, por status de destino: (status de origem exigido, perfis autorizados).
TRANSICOES = {
    StatusPedido.EM_PREPARO: (StatusPedido.CONFIRMADO, frozenset({Perfil.COZINHA, Perfil.GERENTE})),
    StatusPedido.PRONTO: (StatusPedido.EM_PREPARO, frozenset({Perfil.COZINHA, Perfil.GERENTE})),
    StatusPedido.ENTREGUE: (StatusPedido.PRONTO, frozenset({Perfil.ATENDENTE, Perfil.GERENTE})),
}


def exigir_perfil(perfil: str, permitidos: frozenset[Perfil], mensagem: str) -> None:
    if perfil not in permitidos:
        raise PermissaoNegada("PERFIL_SEM_PERMISSAO", mensagem)


def exigir_pode_criar_pedido(perfil: str, canal: CanalPedido, unidade_usuario: int | None, unidade_pedido: int) -> None:
    if perfil == Perfil.CLIENTE and canal not in CANAIS_CLIENTE:
        raise PermissaoNegada("CANAL_NAO_PERMITIDO", "Canal não permitido para este perfil.")
    if perfil in {Perfil.ATENDENTE, Perfil.GERENTE} and canal not in CANAIS_EQUIPE:
        raise PermissaoNegada("CANAL_NAO_PERMITIDO", "Canal não permitido para este perfil.")
    if perfil == Perfil.COZINHA:
        raise PermissaoNegada("PERFIL_SEM_PERMISSAO", "Perfil não pode criar pedidos.")
    if perfil != Perfil.CLIENTE and unidade_usuario != unidade_pedido:
        raise PermissaoNegada("UNIDADE_NAO_PERMITIDA", "Operação fora da unidade do usuário.")


def exigir_pode_pagar(perfil: str) -> None:
    exigir_perfil(perfil, PERFIS_QUE_PAGAM, "Perfil não pode registrar pagamento.")


def exigir_pode_cancelar(perfil: str) -> None:
    exigir_perfil(perfil, PERFIS_QUE_CANCELAM, "Perfil não pode cancelar pedidos.")


def precisa_cancelar(status_atual: str) -> bool:
    """Só cancela pedido aguardando pagamento. Pedido já cancelado: nada a fazer. Pedido pago: conflito (sem estorno no MVP)."""
    if status_atual == StatusPedido.AGUARDANDO_PAGAMENTO:
        return True
    if status_atual == StatusPedido.CANCELADO:
        return False
    raise Conflito("PEDIDO_NAO_CANCELAVEL", "Somente pedidos aguardando pagamento podem ser cancelados.")


def exigir_acesso_ao_pedido(perfil: str, usuario_id: int, unidade_usuario: int | None, pedido_cliente_id: int | None, pedido_unidade_id: int) -> None:
    """Cliente só vê os próprios pedidos; funcionário só vê os da própria unidade. Fora disso, o pedido "não existe"."""
    if perfil == Perfil.CLIENTE:
        permitido = pedido_cliente_id == usuario_id
    else:
        permitido = pedido_unidade_id == unidade_usuario
    if not permitido:
        raise NaoEncontrado("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")


def validar_mudanca_status(perfil: str, atual: str, destino: StatusPedido) -> bool:
    """Confere permissão e transição. Devolve False quando o pedido já está no destino (nada a fazer)."""
    regra = TRANSICOES.get(destino)
    if perfil == Perfil.CLIENTE or (regra is not None and perfil not in regra[1]):
        raise PermissaoNegada("PERFIL_SEM_PERMISSAO", "Perfil não pode executar esta mudança de status.")
    if regra is None:
        raise Conflito("TRANSICAO_INVALIDA", "Transição de status não permitida.")
    if atual == destino:
        return False
    if atual != regra[0]:
        raise Conflito("TRANSICAO_INVALIDA", "Transição de status não permitida.")
    return True


def exigir_gerente_da_unidade(perfil: str, unidade_usuario: int | None, unidade_alvo: int) -> None:
    """Operações de gestão local (estoque) são do gerente, e só na própria unidade."""
    exigir_perfil(perfil, frozenset({Perfil.GERENTE}), "Somente gerentes ajustam o estoque.")
    if unidade_usuario != unidade_alvo:
        raise PermissaoNegada("UNIDADE_NAO_PERMITIDA", "Operação fora da unidade do usuário.")


def saldo_livre_apos_movimentacao(saldo_livre: int, tipo: TipoMovimentacao, quantidade: int) -> int:
    """Entrada soma ao saldo livre; saída subtrai. A saída nunca retira itens reservados, então não pode passar do saldo livre."""
    novo = saldo_livre + quantidade if tipo == TipoMovimentacao.ENTRADA else saldo_livre - quantidade
    if novo < 0:
        raise Conflito("ESTOQUE_INSUFICIENTE", "A saída é maior que o saldo livre. Itens reservados em pedidos não podem ser retirados.")
    return novo


def exigir_senha_forte(senha: str) -> None:
    """Senha de 8 a 128 caracteres, com pelo menos uma letra e um número."""
    tamanho_ok = 8 <= len(senha) <= 128
    if not (tamanho_ok and any(c.isalpha() for c in senha) and any(c.isdigit() for c in senha)):
        raise DadosInvalidos("SENHA_FRACA", "A senha precisa ter de 8 a 128 caracteres, com pelo menos uma letra e um número.")


def pontos_ganhos(valor_pago_centavos: int) -> int:
    """1 ponto por real efetivamente pago, arredondando para baixo."""
    return valor_pago_centavos // CENTAVOS_POR_PONTO_GANHO


def exigir_pode_resgatar(perfil: str, consentimento_ativo: bool) -> None:
    """Só o cliente resgata, e só com o consentimento de fidelidade ativo (revogado, o saldo fica congelado)."""
    exigir_perfil(perfil, frozenset({Perfil.CLIENTE}), "Somente clientes resgatam pontos de fidelidade.")
    if not consentimento_ativo:
        raise Conflito("FIDELIDADE_INATIVA", "O consentimento do programa de fidelidade não está ativo. Os pontos ficam guardados até um novo consentimento.")


def desconto_do_resgate(pontos: int, saldo: int, total_centavos: int) -> int:
    """Converte pontos em desconto: múltiplos de 100, dentro do saldo e até 50% do valor do pedido."""
    if pontos <= 0 or pontos % PONTOS_POR_RESGATE:
        raise DadosInvalidos("RESGATE_INVALIDO", f"O resgate deve usar múltiplos de {PONTOS_POR_RESGATE} pontos.")
    if pontos > saldo:
        raise Conflito("SALDO_PONTOS_INSUFICIENTE", "Saldo de pontos insuficiente para este resgate.")
    desconto = pontos // PONTOS_POR_RESGATE * CENTAVOS_POR_RESGATE
    if desconto * 100 > total_centavos * DESCONTO_MAXIMO_PERCENTUAL:
        raise DadosInvalidos("DESCONTO_ACIMA_DO_LIMITE", f"O desconto não pode passar de {DESCONTO_MAXIMO_PERCENTUAL}% do valor do pedido.")
    return desconto
