from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def token(email: str, senha: str) -> str:
    response = client.post("/auth/login", json={"email": email, "senha": senha})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_and_public_catalog():
    assert client.get("/health").status_code == 200
    assert client.get("/unidades").status_code == 200
    assert len(client.get("/unidades/1/cardapio").json()) >= 1


def test_login_and_missing_token():
    access_token = token("cliente@raizes.local", "Cliente@123")
    assert access_token
    assert client.get("/pedidos").status_code == 401


def test_client_cannot_create_balcao_order():
    headers = {"Authorization": f"Bearer {token('cliente@raizes.local', 'Cliente@123')}"}
    response = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "BALCAO", "itens": [{"produto_id": 1, "quantidade": 1}]})
    assert response.status_code == 403


def test_create_order_and_reject_payment():
    headers = {"Authorization": f"Bearer {token('cliente@raizes.local', 'Cliente@123')}"}
    order = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 2, "quantidade": 1}]})
    assert order.status_code == 201
    order_id = order.json()["id"]
    payment = client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=headers, json={"resultado": "RECUSADO"})
    assert payment.status_code == 200
    assert payment.json()["pedido_status"] == "CANCELADO"


def test_invalid_channel_and_invalid_quantity():
    headers = {"Authorization": f"Bearer {token('cliente@raizes.local', 'Cliente@123')}"}
    invalid_channel = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "INVALIDO", "itens": [{"produto_id": 1, "quantidade": 1}]})
    invalid_quantity = client.post("/pedidos", headers=headers, json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 1, "quantidade": 0}]})
    assert invalid_channel.status_code == 422
    assert invalid_quantity.status_code == 422


def test_kitchen_advances_paid_order():
    client_headers = {"Authorization": f"Bearer {token('cliente@raizes.local', 'Cliente@123')}"}
    order = client.post("/pedidos", headers=client_headers, json={"unidade_id": 1, "canal_pedido": "APP", "itens": [{"produto_id": 3, "quantidade": 1}]})
    assert order.status_code == 201
    order_id = order.json()["id"]
    assert client.post(f"/pedidos/{order_id}/pagamentos/mock", headers=client_headers, json={"resultado": "APROVADO"}).status_code == 200
    kitchen_headers = {"Authorization": f"Bearer {token('cozinha.recife@raizes.local', 'Cozinha@123')}"}
    response = client.patch(f"/pedidos/{order_id}/status", headers=kitchen_headers, json={"status": "CONFIRMADO"})
    assert response.status_code == 200
    assert response.json()["status"] == "EM_PREPARO"


def test_client_consent_and_manager_audit():
    client_headers = {"Authorization": f"Bearer {token('cliente@raizes.local', 'Cliente@123')}"}
    consent = client.post("/me/consentimentos", headers=client_headers, json={"finalidade": "FIDELIDADE", "concedido": True, "versao_termo": "v1"})
    assert consent.status_code == 200
    assert client.get("/me/consentimentos", headers=client_headers).json()[0]["concedido"] is True
    manager_headers = {"Authorization": f"Bearer {token('gerente.recife@raizes.local', 'Gerente@123')}"}
    assert client.get("/auditoria", headers=manager_headers).status_code == 200
    assert client.get("/auditoria", headers=client_headers).status_code == 403
