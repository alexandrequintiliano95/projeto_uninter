# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from datetime import datetime

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from app.api.deps import db_session
from app.infrastructure.models import Pedido, Produto, ProdutoUnidade
from app.main import app


CLIENTE = ("cliente@raizes.local", "Cliente@123")
ATENDENTE_RECIFE = ("atendente.recife@raizes.local", "Atendente@123")
COZINHA_RECIFE = ("cozinha.recife@raizes.local", "Cozinha@123")
GERENTE_RECIFE = ("gerente.recife@raizes.local", "Gerente@123")
GERENTE_CARUARU = ("gerente.caruaru@raizes.local", "Gerente@123")


def auth(client: TestClient, credentials: tuple[str, str]) -> dict[str, str]:
    email, senha = credentials
    response = client.post("/auth/login", json={"email": email, "senha": senha})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def order_payload(*, unidade_id: int = 1, canal: str = "APP", produto_id: int = 1, quantidade: int = 1, pontos: int | None = None) -> dict:
    payload = {"unidade_id": unidade_id, "canal_pedido": canal, "itens": [{"produto_id": produto_id, "quantidade": quantidade}]}
    if pontos is not None:
        payload["pontos_resgatados"] = pontos
    return payload


def create_order(client: TestClient, headers: dict[str, str], **options) -> dict:
    response = client.post("/pedidos", headers=headers, json=order_payload(**options))
    assert response.status_code == 201, response.text
    return response.json()


def create_paid_order(client: TestClient) -> int:
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    payment = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "APROVADO"})
    assert payment.status_code == 200, payment.text
    return order_id


def assert_error(response, status_code: int, code: str, path: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"error", "message", "details", "timestamp", "path"}
    assert body["error"] == code
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["details"], list)
    assert datetime.fromisoformat(body["timestamp"]).tzinfo is not None
    assert body["path"] == path
    return body


def resolve_schema(openapi: dict, schema: dict) -> dict:
    while "$ref" in schema:
        schema = openapi["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def test_health_and_public_catalog(client: TestClient):
    assert client.get("/health").status_code == 200
    assert client.get("/unidades").status_code == 200
    assert len(client.get("/unidades/1/cardapio").json()) >= 1


def test_login_and_missing_token(client: TestClient):
    assert auth(client, CLIENTE)
    assert client.get("/pedidos").status_code == 401


def test_client_cannot_create_balcao_order(client: TestClient):
    headers = auth(client, CLIENTE)
    response = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "BALCAO", "itens": [{"produto_id": 1, "quantidade": 1}]})
    assert response.status_code == 403


def test_create_order_and_reject_payment(client: TestClient):
    headers = auth(client, CLIENTE)
    order = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 2, "quantidade": 1}]})
    assert order.status_code == 201
    order_id = order.json()["id"]
    payment = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "RECUSADO"})
    assert payment.status_code == 200
    assert payment.json()["pedido_status"] == "CANCELADO"


def test_invalid_channel_and_invalid_quantity(client: TestClient):
    headers = auth(client, CLIENTE)
    invalid_channel = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "INVALIDO", "itens": [{"produto_id": 1, "quantidade": 1}]})
    invalid_quantity = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 1, "quantidade": 0}]})
    assert invalid_channel.status_code == 422
    assert invalid_quantity.status_code == 422


def test_kitchen_advances_paid_order(client: TestClient):
    client_headers = auth(client, CLIENTE)
    order = client.post("/pedidos", headers=client_headers, json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 3, "quantidade": 1}]})
    assert order.status_code == 201
    order_id = order.json()["id"]
    assert client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=client_headers, json={"resultado": "APROVADO"}).status_code == 200
    kitchen_headers = auth(client, COZINHA_RECIFE)
    response = client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": "EM_PREPARO"})
    assert response.status_code == 200
    assert response.json()["status"] == "EM_PREPARO"


def test_client_consent_and_manager_audit(client: TestClient):
    client_headers = auth(client, CLIENTE)
    consent = client.post("/me/consentimentos", headers=client_headers, json={"finalidade": "FIDELIDADE", "concedido": True, "versao_termo": "v1"})
    assert consent.status_code == 200
    assert client.get("/me/consentimentos", headers=client_headers).json()[0]["concedido"] is True
    manager_headers = auth(client, GERENTE_RECIFE)
    assert client.get("/auditoria", headers=manager_headers).status_code == 200
    assert client.get("/auditoria", headers=client_headers).status_code == 403


# --- Formato único de erro --------------------------------------------------


def test_domain_error_uses_standard_format(client: TestClient):
    body = assert_error(client.get("/pedidos"), 401, "NAO_AUTENTICADO", "/pedidos")
    assert body["details"] == []


def test_validation_error_uses_standard_format(client: TestClient):
    headers = auth(client, CLIENTE)
    response = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 1, "quantidade": 0}]})
    body = assert_error(response, 422, "DADOS_INVALIDOS", "/pedidos")
    assert [detail["field"] for detail in body["details"]] == ["itens.0.quantidade"]
    assert body["details"][0]["message"]


def test_unknown_route_uses_standard_format(client: TestClient):
    assert_error(client.get("/rota-inexistente"), 404, "RECURSO_NAO_ENCONTRADO", "/rota-inexistente")


def test_unexpected_error_uses_standard_format():
    def broken_session():
        raise RuntimeError("falha interna com detalhe sensível")
        yield

    app.dependency_overrides[db_session] = broken_session
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/unidades")
    finally:
        app.dependency_overrides.pop(db_session, None)
    body = assert_error(response, 500, "ERRO_INTERNO", "/unidades")
    assert "sensível" not in body["message"]


# --- Pagamento mock respeita o perfil ----------------------------------------


def test_kitchen_cannot_pay_order(client: TestClient):
    client_headers = auth(client, CLIENTE)
    order_id = create_order(client, client_headers)["id"]
    response = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=auth(client, COZINHA_RECIFE), json={"resultado": "APROVADO"})
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", f"/pedidos/{order_id}/pagamentos/mock")
    assert client.get(f"/pedidos/{order_id}", headers=client_headers).json()["status"] == "AGUARDANDO_PAGAMENTO"


def test_kitchen_cannot_repeat_existing_payment(client: TestClient):
    order_id = create_paid_order(client)
    response = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=auth(client, COZINHA_RECIFE), json={"resultado": "APROVADO"})
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", f"/pedidos/{order_id}/pagamentos/mock")


# --- Mudança de status: 403 para perfil, 409 para transição -------------------


def test_order_goes_from_kitchen_to_delivery(client: TestClient):
    order_id = create_paid_order(client)
    kitchen_headers = auth(client, COZINHA_RECIFE)
    steps = [(kitchen_headers, "EM_PREPARO"), (kitchen_headers, "PRONTO"), (auth(client, ATENDENTE_RECIFE), "ENTREGUE")]
    for headers, target in steps:
        response = client.patch(f"/pedidos/{order_id}/status", headers=headers, json={"status": target})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target


def test_repeating_current_status_is_idempotent(client: TestClient):
    order_id = create_paid_order(client)
    kitchen_headers = auth(client, COZINHA_RECIFE)
    first = client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": "EM_PREPARO"})
    repeated = client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": "EM_PREPARO"})
    assert (first.status_code, repeated.status_code) == (200, 200)
    assert repeated.json()["status"] == "EM_PREPARO"
    audit = client.get("/auditoria", headers=auth(client, GERENTE_RECIFE)).json()
    assert [event["detalhes"] for event in audit if event["acao"] == "STATUS_ATUALIZADO" and event["entidade_id"] == order_id] == ["EM_PREPARO"]


def test_kitchen_cannot_mark_order_delivered(client: TestClient):
    order_id = create_paid_order(client)
    kitchen_headers = auth(client, COZINHA_RECIFE)
    for target in ("EM_PREPARO", "PRONTO"):
        assert client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": target}).status_code == 200
    response = client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": "ENTREGUE"})
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", f"/pedidos/{order_id}/status")
    assert client.get(f"/pedidos/{order_id}", headers=kitchen_headers).json()["status"] == "PRONTO"


def test_client_cannot_change_order_status(client: TestClient):
    order_id = create_paid_order(client)
    response = client.patch(f"/pedidos/{order_id}/status", headers=auth(client, CLIENTE), json={"status": "EM_PREPARO"})
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", f"/pedidos/{order_id}/status")


def test_skipping_a_step_is_conflict(client: TestClient):
    order_id = create_paid_order(client)
    response = client.patch(f"/pedidos/{order_id}/status", headers=auth(client, GERENTE_RECIFE), json={"status": "PRONTO"})
    assert_error(response, 409, "TRANSICAO_INVALIDA", f"/pedidos/{order_id}/status")


def test_status_route_cannot_confirm_or_cancel(client: TestClient):
    headers = auth(client, GERENTE_RECIFE)
    order_id = create_order(client, headers, canal="BALCAO")["id"]
    for target in ("CONFIRMADO", "CANCELADO"):
        response = client.patch(f"/pedidos/{order_id}/status", headers=headers, json={"status": target})
        assert_error(response, 409, "TRANSICAO_INVALIDA", f"/pedidos/{order_id}/status")


def test_status_rejects_unknown_value(client: TestClient):
    order_id = create_paid_order(client)
    response = client.patch(f"/pedidos/{order_id}/status", headers=auth(client, GERENTE_RECIFE), json={"status": "VOANDO"})
    body = assert_error(response, 422, "DADOS_INVALIDOS", f"/pedidos/{order_id}/status")
    assert [detail["field"] for detail in body["details"]] == ["status"]


# --- Itens devolvem o ID do produto do catálogo -------------------------------


def test_order_items_return_catalog_product_id(client: TestClient):
    headers = auth(client, CLIENTE)
    order = create_order(client, headers, unidade_id=2, produto_id=3)
    assert [item["produto_id"] for item in order["itens"]] == [3]
    fetched = client.get(f"/pedidos/{order['id']}", headers=headers).json()
    assert [item["produto_id"] for item in fetched["itens"]] == [3]


# --- Swagger: Authorize com Bearer token --------------------------------------


def test_swagger_authorize_asks_for_bearer_token(client: TestClient):
    openapi = client.get("/openapi.json").json()
    schemes = list(openapi["components"]["securitySchemes"].values())
    assert schemes and all(scheme["type"] == "http" and scheme["scheme"].lower() == "bearer" for scheme in schemes)
    assert openapi["paths"]["/pedidos"]["post"]["security"]


# --- Canal e status: valores fechados e filtros do roteiro --------------------


def test_swagger_lists_canal_pedido_values(client: TestClient):
    openapi = client.get("/openapi.json").json()
    body = openapi["paths"]["/pedidos"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    canal = resolve_schema(openapi, resolve_schema(openapi, body)["properties"]["canalPedido"])
    assert set(canal["enum"]) == {"APP", "WEB", "PICKUP", "BALCAO", "TOTEM"}


def test_list_orders_filters_by_canal_pedido(client: TestClient):
    headers = auth(client, ATENDENTE_RECIFE)
    totem = create_order(client, headers, canal="TOTEM")
    create_order(client, headers, canal="BALCAO")
    response = client.get("/pedidos", headers=headers, params={"canalPedido": "TOTEM"})
    assert response.status_code == 200
    assert [order["id"] for order in response.json()] == [totem["id"]]


def test_list_orders_filters_by_status(client: TestClient):
    headers = auth(client, CLIENTE)
    rejected = create_order(client, headers)
    create_order(client, headers)
    client.post(f"/pedidos/{rejected['id']}/pagamentos/mock", headers=headers, json={"resultado": "RECUSADO"})
    response = client.get("/pedidos", headers=headers, params={"status": "CANCELADO"})
    assert response.status_code == 200
    assert [order["id"] for order in response.json()] == [rejected["id"]]


def test_list_orders_rejects_unknown_filter_values(client: TestClient):
    headers = auth(client, CLIENTE)
    assert_error(client.get("/pedidos", headers=headers, params={"canalPedido": "FAX"}), 422, "DADOS_INVALIDOS", "/pedidos")
    assert_error(client.get("/pedidos", headers=headers, params={"status": "PERDIDO"}), 422, "DADOS_INVALIDOS", "/pedidos")


# --- Valores fechados no Swagger e documentação das respostas -----------------


def test_payment_rejects_unknown_result(client: TestClient):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    response = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "TALVEZ"})
    body = assert_error(response, 422, "DADOS_INVALIDOS", f"/pedidos/{order_id}/pagamentos/mock")
    assert [detail["field"] for detail in body["details"]] == ["resultado"]


def test_consent_rejects_unknown_purpose(client: TestClient):
    response = client.post("/me/consentimentos", headers=auth(client, CLIENTE), json={"finalidade": "SORTEIO", "concedido": True})
    body = assert_error(response, 422, "DADOS_INVALIDOS", "/me/consentimentos")
    assert [detail["field"] for detail in body["details"]] == ["finalidade"]


def test_swagger_describes_order_response(client: TestClient):
    openapi = client.get("/openapi.json").json()
    schema = openapi["paths"]["/pedidos"]["post"]["responses"]["201"]["content"]["application/json"]["schema"]
    properties = resolve_schema(openapi, schema)["properties"]
    assert set(properties) == {"id", "unidade_id", "cliente_id", "canal_pedido", "status", "total_centavos", "desconto_centavos", "pontos_resgatados", "motivo_cancelamento", "expira_em", "itens"}


def test_token_with_invalid_subject_is_rejected(client: TestClient):
    token = jwt.encode({"sub": "abc", "perfil": "CLIENTE"}, "dev-only-change-me-32-byte-secret-key", algorithm="HS256")
    response = client.get("/pedidos", headers={"Authorization": f"Bearer {token}"})
    assert_error(response, 401, "TOKEN_INVALIDO", "/pedidos")


# --- Casos de borda do pedido --------------------------------------------------


def test_expired_order_cannot_be_paid(client: TestClient, session_factory: sessionmaker):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    with session_factory() as session:
        session.execute(update(Pedido).where(Pedido.id == order_id).values(expira_em=datetime(2020, 1, 1)))
        session.commit()
    response = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "APROVADO"})
    assert_error(response, 409, "PEDIDO_SEM_PAGAMENTO", f"/pedidos/{order_id}/pagamentos/mock")
    # Confere o banco antes de qualquer outra leitura pela API, que refaria a expiração.
    with session_factory() as session:
        order = session.get(Pedido, order_id)
        assert (order.status, order.motivo_cancelamento) == ("CANCELADO", "PRAZO_EXPIRADO")
        offer = session.get(ProdutoUnidade, 1)
        assert (offer.saldo_livre, offer.saldo_reservado) == (20, 0)
    audit = client.get("/auditoria", headers=auth(client, GERENTE_RECIFE)).json()
    assert [event["acao"] for event in audit if event["entidade_id"] == order_id] == ["PEDIDO_EXPIRADO", "PEDIDO_CRIADO"]


def test_inactive_product_is_unavailable(client: TestClient, session_factory: sessionmaker):
    with session_factory() as session:
        session.execute(update(Produto).where(Produto.id == 2).values(ativo=False))
        session.commit()
    response = client.post("/pedidos", headers=auth(client, CLIENTE), json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 2, "quantidade": 1}]})
    assert_error(response, 404, "PRODUTO_INDISPONIVEL", "/pedidos")


# --- Cancelamento antes do pagamento ------------------------------------------


def free_stock(client: TestClient, unidade_id: int, produto_id: int) -> int:
    return next(item["saldo_disponivel"] for item in client.get(f"/unidades/{unidade_id}/cardapio").json() if item["produto_id"] == produto_id)


def audited_actions(client: TestClient, order_id: int) -> list[str]:
    audit = client.get("/auditoria", headers=auth(client, GERENTE_RECIFE)).json()
    return [event["acao"] for event in audit if event["tipo_entidade"] == "PEDIDO" and event["entidade_id"] == order_id]


def test_client_cancels_own_pending_order(client: TestClient):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    assert free_stock(client, 1, 1) == 19
    response = client.post(f"/pedidos/{order_id}/cancelamento", headers=headers)
    assert response.status_code == 200, response.text
    assert (response.json()["status"], response.json()["motivo_cancelamento"]) == ("CANCELADO", "SOLICITADO")
    assert free_stock(client, 1, 1) == 20
    assert audited_actions(client, order_id) == ["PEDIDO_CANCELADO", "PEDIDO_CRIADO"]


def test_repeating_cancel_is_idempotent(client: TestClient):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    responses = [client.post(f"/pedidos/{order_id}/cancelamento", headers=headers) for _ in range(2)]
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[1].json()["status"] == "CANCELADO"
    assert free_stock(client, 1, 1) == 20
    assert audited_actions(client, order_id) == ["PEDIDO_CANCELADO", "PEDIDO_CRIADO"]


def test_staff_cancels_only_orders_of_own_unit(client: TestClient):
    order_id = create_order(client, auth(client, CLIENTE))["id"]
    other_unit = client.post(f"/pedidos/{order_id}/cancelamento", headers=auth(client, GERENTE_CARUARU))
    assert_error(other_unit, 404, "PEDIDO_NAO_ENCONTRADO", f"/pedidos/{order_id}/cancelamento")
    same_unit = client.post(f"/pedidos/{order_id}/cancelamento", headers=auth(client, ATENDENTE_RECIFE))
    assert same_unit.status_code == 200, same_unit.text


def test_kitchen_cannot_cancel_order(client: TestClient):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    response = client.post(f"/pedidos/{order_id}/cancelamento", headers=auth(client, COZINHA_RECIFE))
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", f"/pedidos/{order_id}/cancelamento")
    assert client.get(f"/pedidos/{order_id}", headers=headers).json()["status"] == "AGUARDANDO_PAGAMENTO"


def test_paid_order_cannot_be_cancelled(client: TestClient):
    order_id = create_paid_order(client)
    response = client.post(f"/pedidos/{order_id}/cancelamento", headers=auth(client, CLIENTE))
    assert_error(response, 409, "PEDIDO_NAO_CANCELAVEL", f"/pedidos/{order_id}/cancelamento")
    assert client.get(f"/pedidos/{order_id}", headers=auth(client, CLIENTE)).json()["status"] == "CONFIRMADO"


def test_cancelled_order_cannot_be_paid(client: TestClient):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    assert client.post(f"/pedidos/{order_id}/cancelamento", headers=headers).status_code == 200
    response = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "APROVADO"})
    assert_error(response, 409, "PEDIDO_SEM_PAGAMENTO", f"/pedidos/{order_id}/pagamentos/mock")


# --- Falha técnica simulada no pagamento mock ---------------------------------


def test_payment_failure_returns_503_and_keeps_order_waiting(client: TestClient):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    failure = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "FALHA"})
    assert_error(failure, 503, "PAGAMENTO_INDISPONIVEL", f"/pedidos/{order_id}/pagamentos/mock")
    assert client.get(f"/pedidos/{order_id}", headers=headers).json()["status"] == "AGUARDANDO_PAGAMENTO"
    assert free_stock(client, 1, 1) == 19
    retry = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "APROVADO"})
    assert (retry.status_code, retry.json()["pedido_status"]) == (200, "CONFIRMADO")
    assert audited_actions(client, order_id) == ["PAGAMENTO_MOCK", "PAGAMENTO_FALHA", "PEDIDO_CRIADO"]


def test_swagger_lists_payment_scenarios(client: TestClient):
    openapi = client.get("/openapi.json").json()
    body = openapi["paths"]["/pedidos/{pedido_id}/pagamentos/mock"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    resultado = resolve_schema(openapi, resolve_schema(openapi, body)["properties"]["resultado"])
    assert set(resultado["enum"]) == {"APROVADO", "RECUSADO", "FALHA"}


# --- Entrada e saída de estoque ------------------------------------------------


def move_stock(client: TestClient, credentials: tuple[str, str], *, unidade_id: int = 1, produto_id: int = 1, tipo: str = "ENTRADA", quantidade: int = 10, motivo: str = "Reposição do fornecedor"):
    payload = {"produto_id": produto_id, "tipo": tipo, "quantidade": quantidade, "motivo": motivo}
    return client.post(f"/unidades/{unidade_id}/estoque/movimentacoes", headers=auth(client, credentials), json=payload)


def test_manager_registers_stock_entry(client: TestClient):
    response = move_stock(client, GERENTE_RECIFE, quantidade=10)
    assert response.status_code == 201, response.text
    body = response.json()
    assert {key: body[key] for key in ("unidade_id", "produto_id", "tipo", "quantidade", "motivo", "saldo_livre_anterior", "saldo_livre_novo")} == {
        "unidade_id": 1, "produto_id": 1, "tipo": "ENTRADA", "quantidade": 10, "motivo": "Reposição do fornecedor", "saldo_livre_anterior": 20, "saldo_livre_novo": 30,
    }
    assert free_stock(client, 1, 1) == 30
    audit = client.get("/auditoria", headers=auth(client, GERENTE_RECIFE)).json()
    assert [event["acao"] for event in audit if event["tipo_entidade"] == "MOVIMENTACAO_ESTOQUE"] == ["ESTOQUE_AJUSTADO"]


def test_stock_exit_never_takes_reserved_items(client: TestClient, session_factory: sessionmaker):
    create_order(client, auth(client, CLIENTE), produto_id=2)
    too_much = move_stock(client, GERENTE_RECIFE, produto_id=2, tipo="SAIDA", quantidade=15, motivo="Perda")
    assert_error(too_much, 409, "ESTOQUE_INSUFICIENTE", "/unidades/1/estoque/movimentacoes")
    all_free = move_stock(client, GERENTE_RECIFE, produto_id=2, tipo="SAIDA", quantidade=14, motivo="Perda")
    assert (all_free.status_code, all_free.json()["saldo_livre_novo"]) == (201, 0)
    with session_factory() as session:
        offer = session.get(ProdutoUnidade, 2)
        assert (offer.saldo_livre, offer.saldo_reservado) == (0, 1)


def test_only_manager_of_the_unit_moves_stock(client: TestClient):
    assert_error(move_stock(client, ATENDENTE_RECIFE), 403, "PERFIL_SEM_PERMISSAO", "/unidades/1/estoque/movimentacoes")
    assert_error(move_stock(client, GERENTE_CARUARU), 403, "UNIDADE_NAO_PERMITIDA", "/unidades/1/estoque/movimentacoes")
    assert free_stock(client, 1, 1) == 20


def test_stock_movement_validates_reason_and_quantity(client: TestClient):
    no_reason = assert_error(move_stock(client, GERENTE_RECIFE, motivo="  "), 422, "DADOS_INVALIDOS", "/unidades/1/estoque/movimentacoes")
    assert [detail["field"] for detail in no_reason["details"]] == ["motivo"]
    zero = assert_error(move_stock(client, GERENTE_RECIFE, quantidade=0), 422, "DADOS_INVALIDOS", "/unidades/1/estoque/movimentacoes")
    assert [detail["field"] for detail in zero["details"]] == ["quantidade"]


def test_stock_movement_needs_an_offer_in_the_unit(client: TestClient):
    response = move_stock(client, GERENTE_CARUARU, unidade_id=2, produto_id=2)
    assert_error(response, 404, "PRODUTO_INDISPONIVEL", "/unidades/2/estoque/movimentacoes")


def test_stock_history_is_newest_first_and_filters_by_product(client: TestClient):
    first = move_stock(client, GERENTE_RECIFE, produto_id=1, quantidade=5).json()["id"]
    second = move_stock(client, GERENTE_RECIFE, produto_id=3, quantidade=5).json()["id"]
    third = move_stock(client, GERENTE_RECIFE, produto_id=1, tipo="SAIDA", quantidade=2, motivo="Avaria").json()["id"]
    headers = auth(client, GERENTE_RECIFE)
    history = client.get("/unidades/1/estoque/movimentacoes", headers=headers)
    assert [item["id"] for item in history.json()] == [third, second, first]
    only_tapioca = client.get("/unidades/1/estoque/movimentacoes", headers=headers, params={"produtoId": 1})
    assert [item["id"] for item in only_tapioca.json()] == [third, first]
    assert_error(client.get("/unidades/1/estoque/movimentacoes", headers=auth(client, CLIENTE)), 403, "PERFIL_SEM_PERMISSAO", "/unidades/1/estoque/movimentacoes")


def test_menu_releases_expired_reservations(client: TestClient, session_factory: sessionmaker):
    order_id = create_order(client, auth(client, CLIENTE))["id"]
    with session_factory() as session:
        session.execute(update(Pedido).where(Pedido.id == order_id).values(expira_em=datetime(2020, 1, 1)))
        session.commit()
    assert free_stock(client, 1, 1) == 20
    with session_factory() as session:
        order = session.get(Pedido, order_id)
        assert (order.status, order.motivo_cancelamento) == ("CANCELADO", "PRAZO_EXPIRADO")


# --- Cadastro público de cliente ----------------------------------------------


def signup(client: TestClient, **changes):
    payload = {"nome": "Maria das Dores", "email": "maria@exemplo.com", "senha": "Segura123", "aceite_termos": True, **changes}
    return client.post("/auth/cadastro", json=payload)


def test_client_signs_up_and_can_order(client: TestClient):
    response = signup(client, email="  Maria@Exemplo.COM ")
    assert response.status_code == 201, response.text
    body = response.json()
    assert {key: body[key] for key in ("nome", "email", "perfil")} == {"nome": "Maria das Dores", "email": "maria@exemplo.com", "perfil": "CLIENTE"}
    assert not {"senha", "senha_hash"} & set(body)
    login = client.post("/auth/login", json={"email": "maria@exemplo.com", "senha": "Segura123"})
    assert (login.status_code, login.json()["perfil"], login.json()["user_id"]) == (200, "CLIENTE", body["id"])
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert create_order(client, headers)["cliente_id"] == body["id"]


def test_signup_ignores_profile_and_unit_sent_in_body(client: TestClient):
    response = signup(client, perfil="GERENTE", unidade_id=1)
    assert (response.status_code, response.json()["perfil"]) == (201, "CLIENTE")
    headers = auth(client, ("maria@exemplo.com", "Segura123"))
    assert_error(client.get("/auditoria", headers=headers), 403, "PERFIL_SEM_PERMISSAO", "/auditoria")


def test_signup_rejects_email_already_registered(client: TestClient):
    assert_error(signup(client, email="CLIENTE@raizes.local"), 409, "EMAIL_JA_CADASTRADO", "/auth/cadastro")


def test_signup_requires_accepting_terms(client: TestClient):
    assert_error(signup(client, aceite_termos=False), 422, "TERMOS_NAO_ACEITOS", "/auth/cadastro")
    assert client.post("/auth/login", json={"email": "maria@exemplo.com", "senha": "Segura123"}).status_code == 401


def test_signup_rejects_weak_password(client: TestClient):
    assert_error(signup(client, senha="senhafraca"), 422, "SENHA_FRACA", "/auth/cadastro")


def test_signup_validates_name_and_email_format(client: TestClient):
    body = assert_error(signup(client, nome=" ", email="nao-e-email"), 422, "DADOS_INVALIDOS", "/auth/cadastro")
    assert sorted(detail["field"] for detail in body["details"]) == ["email", "nome"]


def test_signup_records_only_the_consents_given(client: TestClient):
    assert signup(client, aceita_fidelidade=True).status_code == 201
    consents = client.get("/me/consentimentos", headers=auth(client, ("maria@exemplo.com", "Segura123"))).json()
    assert [(item["finalidade"], item["concedido"], item["versao_termo"]) for item in consents] == [("FIDELIDADE", True, "v1")]



# --- Fidelidade: pontos e resgate ----------------------------------------------
# Tapioca (produto 1) custa R$ 18,90 na unidade 1: 6 unidades = R$ 113,40 = 113 pontos.


def set_loyalty_consent(client: TestClient, headers: dict[str, str], granted: bool) -> None:
    response = client.post("/me/consentimentos", headers=headers, json={"finalidade": "FIDELIDADE", "concedido": granted})
    assert response.status_code == 200, response.text


def pay(client: TestClient, headers: dict[str, str], order_id: int, resultado: str = "APROVADO") -> None:
    response = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": resultado})
    assert response.status_code == 200, response.text


def loyalty(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get("/me/fidelidade", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def statement(client: TestClient, headers: dict[str, str]) -> list[tuple[str, int]]:
    return [(item["tipo"], item["pontos"]) for item in loyalty(client, headers)["extrato"]]


def earn_113_points(client: TestClient, headers: dict[str, str]) -> None:
    set_loyalty_consent(client, headers, True)
    pay(client, headers, create_order(client, headers, quantidade=6)["id"])


def test_paid_order_earns_one_point_per_real_with_consent(client: TestClient):
    headers = auth(client, CLIENTE)
    set_loyalty_consent(client, headers, True)
    order_id = create_order(client, headers, quantidade=2)["id"]
    assert loyalty(client, headers)["saldo_pontos"] == 0
    pay(client, headers, order_id)
    data = loyalty(client, headers)
    assert (data["saldo_pontos"], data["consentimento_ativo"]) == (37, True)
    assert [(item["tipo"], item["pontos"], item["pedido_id"]) for item in data["extrato"]] == [("CREDITO", 37, order_id)]


def test_purchase_without_consent_earns_no_points(client: TestClient):
    headers = auth(client, CLIENTE)
    pay(client, headers, create_order(client, headers, quantidade=6)["id"])
    data = loyalty(client, headers)
    assert (data["saldo_pontos"], data["consentimento_ativo"], data["extrato"]) == (0, False, [])


def test_points_become_discount_and_paid_value_earns_points(client: TestClient):
    headers = auth(client, CLIENTE)
    earn_113_points(client, headers)
    order = create_order(client, headers, quantidade=2, pontos=100)
    assert (order["total_centavos"], order["desconto_centavos"], order["pontos_resgatados"]) == (3280, 500, 100)
    assert loyalty(client, headers)["saldo_pontos"] == 13
    pay(client, headers, order["id"])
    assert loyalty(client, headers)["saldo_pontos"] == 45
    assert statement(client, headers) == [("CREDITO", 32), ("DEBITO", 100), ("CREDITO", 113)]


def test_cancelled_order_returns_redeemed_points(client: TestClient):
    headers = auth(client, CLIENTE)
    earn_113_points(client, headers)
    order_id = create_order(client, headers, quantidade=2, pontos=100)["id"]
    assert client.post(f"/pedidos/{order_id}/cancelamento", headers=headers).status_code == 200
    assert loyalty(client, headers)["saldo_pontos"] == 113
    assert statement(client, headers) == [("ESTORNO", 100), ("DEBITO", 100), ("CREDITO", 113)]


def test_refused_payment_returns_redeemed_points(client: TestClient):
    headers = auth(client, CLIENTE)
    earn_113_points(client, headers)
    order_id = create_order(client, headers, quantidade=2, pontos=100)["id"]
    pay(client, headers, order_id, "RECUSADO")
    assert loyalty(client, headers)["saldo_pontos"] == 113


def test_revoked_consent_freezes_points(client: TestClient):
    headers = auth(client, CLIENTE)
    earn_113_points(client, headers)
    set_loyalty_consent(client, headers, False)
    pay(client, headers, create_order(client, headers, quantidade=6)["id"])
    assert loyalty(client, headers)["saldo_pontos"] == 113
    blocked = client.post("/pedidos", headers=headers, json=order_payload(quantidade=2, pontos=100))
    assert_error(blocked, 409, "FIDELIDADE_INATIVA", "/pedidos")
    set_loyalty_consent(client, headers, True)
    assert create_order(client, headers, quantidade=2, pontos=100)["desconto_centavos"] == 500


def test_redemption_limits(client: TestClient):
    headers = auth(client, CLIENTE)
    earn_113_points(client, headers)
    not_multiple = client.post("/pedidos", headers=headers, json=order_payload(quantidade=2, pontos=150))
    assert [detail["field"] for detail in assert_error(not_multiple, 422, "DADOS_INVALIDOS", "/pedidos")["details"]] == ["pontos_resgatados"]
    assert_error(client.post("/pedidos", headers=headers, json=order_payload(quantidade=6, pontos=200)), 409, "SALDO_PONTOS_INSUFICIENTE", "/pedidos")
    assert_error(client.post("/pedidos", headers=headers, json=order_payload(produto_id=3, pontos=100)), 422, "DESCONTO_ACIMA_DO_LIMITE", "/pedidos")
    assert loyalty(client, headers)["saldo_pontos"] == 113


def test_staff_orders_cannot_redeem_points(client: TestClient):
    response = client.post("/pedidos", headers=auth(client, ATENDENTE_RECIFE), json=order_payload(canal="BALCAO", pontos=100))
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", "/pedidos")


def test_loyalty_statement_is_only_for_clients(client: TestClient):
    assert_error(client.get("/me/fidelidade", headers=auth(client, GERENTE_RECIFE)), 403, "PERFIL_SEM_PERMISSAO", "/me/fidelidade")


# --- Casos negativos do plano de testes que só a coleção Postman cobria --------


def test_login_with_wrong_password_is_rejected(client: TestClient):
    response = client.post("/auth/login", json={"email": CLIENTE[0], "senha": "errada"})
    assert_error(response, 401, "CREDENCIAIS_INVALIDAS", "/auth/login")


def test_order_beyond_stock_is_rejected_without_reserving(client: TestClient):
    response = client.post("/pedidos", headers=auth(client, CLIENTE), json=order_payload(quantidade=21))
    assert_error(response, 409, "ESTOQUE_INSUFICIENTE", "/pedidos")
    assert free_stock(client, 1, 1) == 20


def test_payment_result_cannot_be_changed(client: TestClient):
    order_id = create_paid_order(client)
    response = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=auth(client, CLIENTE), json={"resultado": "RECUSADO"})
    assert_error(response, 409, "PAGAMENTO_IMUTAVEL", f"/pedidos/{order_id}/pagamentos/mock")



# --- Casos da seção 5 do MODELO.md ---------------------------------------------


def test_kitchen_only_sees_paid_orders(client: TestClient):
    client_headers = auth(client, CLIENTE)
    waiting_id = create_order(client, client_headers)["id"]
    paid_id = create_paid_order(client)
    kitchen_headers = auth(client, COZINHA_RECIFE)
    assert [order["id"] for order in client.get("/pedidos", headers=kitchen_headers).json()] == [paid_id]
    assert_error(client.get(f"/pedidos/{waiting_id}", headers=kitchen_headers), 404, "PEDIDO_NAO_ENCONTRADO", f"/pedidos/{waiting_id}")
    assert client.get(f"/pedidos/{paid_id}", headers=kitchen_headers).status_code == 200


def test_client_cannot_see_or_pay_another_clients_order(client: TestClient):
    order_id = create_order(client, auth(client, CLIENTE))["id"]
    assert client.post("/auth/cadastro", json={"nome": "Outra Cliente", "email": "outra@exemplo.com", "senha": "Segura123", "aceite_termos": True}).status_code == 201
    other = auth(client, ("outra@exemplo.com", "Segura123"))
    assert_error(client.get(f"/pedidos/{order_id}", headers=other), 404, "PEDIDO_NAO_ENCONTRADO", f"/pedidos/{order_id}")
    assert_error(client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=other, json={"resultado": "APROVADO"}), 404, "PEDIDO_NAO_ENCONTRADO", f"/pedidos/{order_id}/pagamentos/mock")
    assert client.get("/pedidos", headers=other).json() == []


def test_product_without_offer_in_the_unit_is_unavailable(client: TestClient):
    response = client.post("/pedidos", headers=auth(client, CLIENTE), json=order_payload(unidade_id=2, produto_id=2))
    assert_error(response, 404, "PRODUTO_INDISPONIVEL", "/pedidos")


def test_catalog_change_does_not_alter_existing_order(client: TestClient, session_factory: sessionmaker):
    headers = auth(client, CLIENTE)
    order_id = create_order(client, headers)["id"]
    with session_factory() as session:
        session.execute(update(ProdutoUnidade).where(ProdutoUnidade.id == 1).values(preco_centavos=2500))
        session.execute(update(Produto).where(Produto.id == 1).values(nome="Tapioca renomeada"))
        session.commit()
    order = client.get(f"/pedidos/{order_id}", headers=headers).json()
    assert (order["total_centavos"], order["itens"][0]["preco_unitario_centavos"], order["itens"][0]["nome"]) == (1890, 1890, "Tapioca de Carne de Sol")


# --- Nomes de campo do roteiro no corpo do pedido -------------------------------
# O roteiro usa unidadeId, canalPedido, produtoId e pontosResgatados; os nomes antigos continuam aceitos.


def test_order_accepts_roteiro_field_names(client: TestClient):
    payload = {"unidadeId": 1, "canalPedido": "APP", "itens": [{"produtoId": 3, "quantidade": 2}]}
    response = client.post("/pedidos", headers=auth(client, CLIENTE), json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["unidade_id"], body["canal_pedido"], body["itens"][0]["produto_id"], body["total_centavos"]) == (1, "APP", 3, 1780)


def test_order_without_channel_points_to_roteiro_field_name(client: TestClient):
    response = client.post("/pedidos", headers=auth(client, CLIENTE), json={"unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 1}]})
    body = assert_error(response, 422, "DADOS_INVALIDOS", "/pedidos")
    assert [detail["field"] for detail in body["details"]] == ["canalPedido"]


def test_order_reads_points_from_roteiro_field_name(client: TestClient):
    payload = {"unidadeId": 1, "canalPedido": "APP", "itens": [{"produtoId": 1, "quantidade": 2}], "pontosResgatados": 150}
    body = assert_error(client.post("/pedidos", headers=auth(client, CLIENTE), json=payload), 422, "DADOS_INVALIDOS", "/pedidos")
    assert [detail["field"] for detail in body["details"]] == ["pontosResgatados"]


# --- Swagger documenta os erros no formato único --------------------------------


def error_schema_properties(openapi: dict, operation: dict, status_code: str) -> set[str]:
    schema = operation["responses"][status_code]["content"]["application/json"]["schema"]
    return set(resolve_schema(openapi, schema)["properties"])


def test_swagger_documents_errors_in_the_standard_format(client: TestClient):
    openapi = client.get("/openapi.json").json()
    formato = {"error", "message", "details", "timestamp", "path"}
    criar = openapi["paths"]["/pedidos"]["post"]
    for status_code in ("401", "403", "404", "409", "422"):
        assert error_schema_properties(openapi, criar, status_code) == formato, status_code
    pagar = openapi["paths"]["/pedidos/{pedido_id}/pagamentos/mock"]["post"]
    assert error_schema_properties(openapi, pagar, "503") == formato
    login = openapi["paths"]["/auth/login"]["post"]
    assert error_schema_properties(openapi, login, "401") == formato
    assert "HTTPValidationError" not in openapi["components"]["schemas"]
