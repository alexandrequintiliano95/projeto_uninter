from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app, db_session


CLIENTE = ("cliente@raizes.local", "Cliente@123")
ATENDENTE_RECIFE = ("atendente.recife@raizes.local", "Atendente@123")
COZINHA_RECIFE = ("cozinha.recife@raizes.local", "Cozinha@123")
GERENTE_RECIFE = ("gerente.recife@raizes.local", "Gerente@123")


def auth(client: TestClient, credentials: tuple[str, str]) -> dict[str, str]:
    email, senha = credentials
    response = client.post("/auth/login", json={"email": email, "senha": senha})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_order(client: TestClient, headers: dict[str, str], *, unidade_id: int = 1, canal: str = "APP", produto_id: int = 1) -> dict:
    response = client.post("/pedidos", headers=headers, json={"unidade_id": unidade_id, "canal_pedido": canal, "itens": [{"produto_id": produto_id, "quantidade": 1}]})
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
    response = client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": "CONFIRMADO"})
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


def test_kitchen_cannot_mark_order_delivered(client: TestClient):
    order_id = create_paid_order(client)
    kitchen_headers = auth(client, COZINHA_RECIFE)
    for current in ("CONFIRMADO", "EM_PREPARO"):
        assert client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": current}).status_code == 200
    response = client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": "PRONTO"})
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", f"/pedidos/{order_id}/status")
    assert client.get(f"/pedidos/{order_id}", headers=kitchen_headers).json()["status"] == "PRONTO"


def test_client_cannot_change_order_status(client: TestClient):
    order_id = create_paid_order(client)
    response = client.patch(f"/pedidos/{order_id}/status", headers=auth(client, CLIENTE), json={"status": "CONFIRMADO"})
    assert_error(response, 403, "PERFIL_SEM_PERMISSAO", f"/pedidos/{order_id}/status")


def test_skipping_a_step_is_conflict(client: TestClient):
    order_id = create_paid_order(client)
    response = client.patch(f"/pedidos/{order_id}/status", headers=auth(client, GERENTE_RECIFE), json={"status": "PRONTO"})
    assert_error(response, 409, "TRANSICAO_INVALIDA", f"/pedidos/{order_id}/status")


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
    canal = resolve_schema(openapi, resolve_schema(openapi, body)["properties"]["canal_pedido"])
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
