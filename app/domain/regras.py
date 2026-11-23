"""Regras de negócio puras. Recebem valores simples e lançam ErroDominio quando a operação não é permitida."""

from datetime import timedelta

from .enums import CanalPedido, Perfil, StatusPedido, TipoMovimentacao
from .errors import Conflito, NaoEncontrado, PermissaoNegada

PRAZO_RESERVA = timedelta(minutes=15)

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
