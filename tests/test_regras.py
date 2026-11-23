# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Testes unitários das regras de domínio: não usam banco nem HTTP."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.enums import CanalPedido, Perfil, StatusPedido, TipoMovimentacao
from app.domain.errors import Conflito, NaoEncontrado, PermissaoNegada
from app.domain.regras import (
    exigir_acesso_ao_pedido,
    exigir_gerente_da_unidade,
    exigir_pode_cancelar,
    exigir_pode_criar_pedido,
    exigir_pode_pagar,
    precisa_cancelar,
    saldo_livre_apos_movimentacao,
    validar_mudanca_status,
)


def test_cliente_so_usa_canais_de_cliente():
    with pytest.raises(PermissaoNegada) as erro:
        exigir_pode_criar_pedido(Perfil.CLIENTE, CanalPedido.BALCAO, None, 1)
    assert erro.value.codigo == "CANAL_NAO_PERMITIDO"
    assert exigir_pode_criar_pedido(Perfil.CLIENTE, CanalPedido.APP, None, 1) is None


def test_cozinha_nao_cria_pedido():
    with pytest.raises(PermissaoNegada) as erro:
        exigir_pode_criar_pedido(Perfil.COZINHA, CanalPedido.BALCAO, 1, 1)
    assert erro.value.codigo == "PERFIL_SEM_PERMISSAO"


def test_funcionario_so_cria_na_propria_unidade():
    with pytest.raises(PermissaoNegada) as erro:
        exigir_pode_criar_pedido(Perfil.ATENDENTE, CanalPedido.BALCAO, 1, 2)
    assert erro.value.codigo == "UNIDADE_NAO_PERMITIDA"


def test_cozinha_nao_paga():
    with pytest.raises(PermissaoNegada) as erro:
        exigir_pode_pagar(Perfil.COZINHA)
    assert erro.value.codigo == "PERFIL_SEM_PERMISSAO"
    for perfil in (Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE):
        assert exigir_pode_pagar(perfil) is None


def test_acesso_ao_pedido():
    with pytest.raises(NaoEncontrado) as erro:
        exigir_acesso_ao_pedido(Perfil.CLIENTE, usuario_id=1, unidade_usuario=None, pedido_cliente_id=2, pedido_unidade_id=1)
    assert erro.value.codigo == "PEDIDO_NAO_ENCONTRADO"
    with pytest.raises(NaoEncontrado):
        exigir_acesso_ao_pedido(Perfil.GERENTE, usuario_id=4, unidade_usuario=1, pedido_cliente_id=1, pedido_unidade_id=2)
    assert exigir_acesso_ao_pedido(Perfil.CLIENTE, usuario_id=1, unidade_usuario=None, pedido_cliente_id=1, pedido_unidade_id=2) is None


@pytest.mark.parametrize(
    ("perfil", "atual", "destino", "esperado"),
    [
        (Perfil.COZINHA, "CONFIRMADO", StatusPedido.EM_PREPARO, True),
        (Perfil.COZINHA, "EM_PREPARO", StatusPedido.EM_PREPARO, False),
        (Perfil.ATENDENTE, "PRONTO", StatusPedido.ENTREGUE, True),
        (Perfil.COZINHA, "PRONTO", StatusPedido.ENTREGUE, "PERFIL_SEM_PERMISSAO"),
        (Perfil.CLIENTE, "CONFIRMADO", StatusPedido.EM_PREPARO, "PERFIL_SEM_PERMISSAO"),
        (Perfil.GERENTE, "CONFIRMADO", StatusPedido.PRONTO, "TRANSICAO_INVALIDA"),
        (Perfil.GERENTE, "AGUARDANDO_PAGAMENTO", StatusPedido.CONFIRMADO, "TRANSICAO_INVALIDA"),
    ],
)
def test_mudanca_de_status(perfil, atual, destino, esperado):
    if isinstance(esperado, bool):
        assert validar_mudanca_status(perfil, atual, destino) is esperado
        return
    with pytest.raises((PermissaoNegada, Conflito)) as erro:
        validar_mudanca_status(perfil, atual, destino)
    assert erro.value.codigo == esperado


def test_dominio_nao_depende_de_frameworks():
    codigo = (
        "import sys, app.domain.enums, app.domain.errors, app.domain.regras; "
        "print(sorted(m for m in ('fastapi', 'pydantic', 'starlette', 'sqlalchemy') if m in sys.modules))"
    )
    raiz_do_projeto = Path(__file__).resolve().parents[1]
    resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True, cwd=raiz_do_projeto)
    assert resultado.stdout.strip() == "[]"


def test_cozinha_nao_cancela_pedido():
    with pytest.raises(PermissaoNegada) as erro:
        exigir_pode_cancelar(Perfil.COZINHA)
    assert erro.value.codigo == "PERFIL_SEM_PERMISSAO"
    for perfil in (Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE):
        assert exigir_pode_cancelar(perfil) is None


@pytest.mark.parametrize(
    ("atual", "esperado"),
    [
        ("AGUARDANDO_PAGAMENTO", True),
        ("CANCELADO", False),
        ("CONFIRMADO", "PEDIDO_NAO_CANCELAVEL"),
        ("EM_PREPARO", "PEDIDO_NAO_CANCELAVEL"),
        ("PRONTO", "PEDIDO_NAO_CANCELAVEL"),
        ("ENTREGUE", "PEDIDO_NAO_CANCELAVEL"),
    ],
)
def test_so_cancela_pedido_aguardando_pagamento(atual, esperado):
    if isinstance(esperado, bool):
        assert precisa_cancelar(atual) is esperado
        return
    with pytest.raises(Conflito) as erro:
        precisa_cancelar(atual)
    assert erro.value.codigo == esperado


def test_so_gerente_da_propria_unidade_ajusta_estoque():
    with pytest.raises(PermissaoNegada) as erro:
        exigir_gerente_da_unidade(Perfil.ATENDENTE, unidade_usuario=1, unidade_alvo=1)
    assert erro.value.codigo == "PERFIL_SEM_PERMISSAO"
    with pytest.raises(PermissaoNegada) as erro:
        exigir_gerente_da_unidade(Perfil.GERENTE, unidade_usuario=2, unidade_alvo=1)
    assert erro.value.codigo == "UNIDADE_NAO_PERMITIDA"
    assert exigir_gerente_da_unidade(Perfil.GERENTE, unidade_usuario=1, unidade_alvo=1) is None


@pytest.mark.parametrize(
    ("saldo", "tipo", "quantidade", "esperado"),
    [
        (20, TipoMovimentacao.ENTRADA, 10, 30),
        (20, TipoMovimentacao.SAIDA, 5, 15),
        (20, TipoMovimentacao.SAIDA, 20, 0),
        (20, TipoMovimentacao.SAIDA, 21, "ESTOQUE_INSUFICIENTE"),
    ],
)
def test_saldo_livre_apos_movimentacao(saldo, tipo, quantidade, esperado):
    if isinstance(esperado, int):
        assert saldo_livre_apos_movimentacao(saldo, tipo, quantidade) == esperado
        return
    with pytest.raises(Conflito) as erro:
        saldo_livre_apos_movimentacao(saldo, tipo, quantidade)
    assert erro.value.codigo == esperado
