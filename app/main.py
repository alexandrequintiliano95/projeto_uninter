from datetime import datetime, timedelta, timezone
from os import getenv

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict, Field
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Auditoria, ConsentimentoEvento, ItemPedido, Pagamento, Pedido, Produto, ProdutoUnidade, Unidade, Usuario


app = FastAPI(title="API Raízes do Nordeste", version="0.1.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
password_hash = PasswordHash.recommended()
JWT_SECRET = getenv("JWT_SECRET", "dev-only-change-me-32-byte-secret-key")
JWT_ALGORITHM = "HS256"
TOKEN_MINUTES = 60


class LoginRequest(BaseModel):
    email: str
    senha: str


class LoginResponse(BaseModel):
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
    canal_pedido: str
    itens: list[PedidoItemRequest] = Field(min_length=1)


class PagamentoRequest(BaseModel):
    resultado: str


class StatusRequest(BaseModel):
    status: str


class ConsentimentoRequest(BaseModel):
    finalidade: str
    concedido: bool
    versao_termo: str = "v1"


def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"error": code, "message": message})


def create_token(user: Usuario) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "perfil": user.perfil, "exp": now + timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def current_user(token: str | None = Depends(oauth2_scheme), session: Session = Depends(db_session)) -> Usuario:
    if not token:
        raise error("NAO_AUTENTICADO", "Token não informado.", status.HTTP_401_UNAUTHORIZED)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise error("TOKEN_INVALIDO", "Token inválido ou expirado.", status.HTTP_401_UNAUTHORIZED)
    user = session.get(Usuario, user_id)
    if not user or not user.ativo:
        raise error("USUARIO_INATIVO", "Usuário não encontrado ou inativo.", status.HTTP_401_UNAUTHORIZED)
    return user


def active_user(user: Usuario = Depends(current_user)) -> Usuario:
    return user


def audit(session: Session, user_id: int | None, unidade_id: int | None, action: str, entity: str, entity_id: int, details: str = "") -> None:
    session.add(Auditoria(usuario_id=user_id, unidade_id=unidade_id, acao=action, tipo_entidade=entity, entidade_id=entity_id, detalhes=details, criado_em=datetime.now(timezone.utc).replace(tzinfo=None)))


def expire_orders(session: Session, unidade_id: int | None = None) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = select(Pedido).where(Pedido.status == "AGUARDANDO_PAGAMENTO", Pedido.expira_em <= now)
    if unidade_id:
        query = query.where(Pedido.unidade_id == unidade_id)
    for order in session.scalars(query):
        for item in session.scalars(select(ItemPedido).where(ItemPedido.pedido_id == order.id)):
            offer = session.get(ProdutoUnidade, item.produto_unidade_id)
            if offer:
                offer.saldo_livre += item.quantidade
                offer.saldo_reservado -= item.quantidade
        order.status = "CANCELADO"
        order.motivo_cancelamento = "PRAZO_EXPIRADO"
        order.atualizado_em = now
        audit(session, None, order.unidade_id, "PEDIDO_EXPIRADO", "PEDIDO", order.id)


def ensure_order_access(order: Pedido, user: Usuario) -> None:
    if user.perfil == "CLIENTE" and order.cliente_id != user.id:
        raise error("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.", status.HTTP_404_NOT_FOUND)
    if user.perfil != "CLIENTE" and order.unidade_id != user.unidade_id:
        raise error("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.", status.HTTP_404_NOT_FOUND)


def order_payload(session: Session, order: Pedido) -> dict:
    items = list(session.scalars(select(ItemPedido).where(ItemPedido.pedido_id == order.id).order_by(ItemPedido.id)))
    return {
        "id": order.id,
        "unidade_id": order.unidade_id,
        "cliente_id": order.cliente_id,
        "canal_pedido": order.canal_pedido,
        "status": order.status,
        "total_centavos": order.total_centavos,
        "motivo_cancelamento": order.motivo_cancelamento,
        "expira_em": order.expira_em.isoformat() + "Z",
        "itens": [{"produto_id": item.produto_unidade_id, "nome": item.nome_produto, "quantidade": item.quantidade, "preco_unitario_centavos": item.preco_unitario_centavos} for item in items],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(data: LoginRequest, session: Session = Depends(db_session)) -> LoginResponse:
    user = session.scalar(select(Usuario).where(Usuario.email == data.email.lower().strip()))
    if not user or not user.ativo or not password_hash.verify(data.senha, user.senha_hash):
        raise error("CREDENCIAIS_INVALIDAS", "E-mail ou senha inválidos.", status.HTTP_401_UNAUTHORIZED)
    return LoginResponse(access_token=create_token(user), token_type="Bearer", expires_in=TOKEN_MINUTES * 60, user_id=user.id, perfil=user.perfil)


@app.get("/unidades", response_model=list[UnidadeResponse])
def list_unidades(session: Session = Depends(db_session)) -> list[Unidade]:
    return list(session.scalars(select(Unidade).where(Unidade.ativa.is_(True)).order_by(Unidade.id)))


@app.get("/unidades/{unidade_id}/cardapio", response_model=list[CardapioItem])
def cardapio(unidade_id: int, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), session: Session = Depends(db_session)) -> list[CardapioItem]:
    unidade = session.get(Unidade, unidade_id)
    if not unidade or not unidade.ativa:
        raise error("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.", status.HTTP_404_NOT_FOUND)
    rows = session.execute(
        select(ProdutoUnidade, Produto)
        .join(Produto, Produto.id == ProdutoUnidade.produto_id)
        .where(ProdutoUnidade.unidade_id == unidade_id, ProdutoUnidade.ativo.is_(True), Produto.ativo.is_(True))
        .order_by(Produto.id)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return [CardapioItem(produto_id=offer.produto_id, nome=product.nome, descricao=product.descricao, preco_centavos=offer.preco_centavos, saldo_disponivel=offer.saldo_livre) for offer, product in rows]


@app.post("/pedidos", status_code=status.HTTP_201_CREATED)
def create_order(data: PedidoRequest, user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> dict:
    if data.canal_pedido not in {"APP", "WEB", "PICKUP", "BALCAO", "TOTEM"}:
        raise error("CANAL_INVALIDO", "Canal de pedido inválido.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if user.perfil == "CLIENTE" and data.canal_pedido not in {"APP", "WEB", "PICKUP"}:
        raise error("CANAL_NAO_PERMITIDO", "Canal não permitido para este perfil.", status.HTTP_403_FORBIDDEN)
    if user.perfil in {"ATENDENTE", "GERENTE"} and data.canal_pedido not in {"BALCAO", "TOTEM", "PICKUP"}:
        raise error("CANAL_NAO_PERMITIDO", "Canal não permitido para este perfil.", status.HTTP_403_FORBIDDEN)
    if user.perfil == "COZINHA":
        raise error("PERFIL_SEM_PERMISSAO", "Perfil não pode criar pedidos.", status.HTTP_403_FORBIDDEN)
    if user.perfil != "CLIENTE" and user.unidade_id != data.unidade_id:
        raise error("UNIDADE_NAO_PERMITIDA", "Operação fora da unidade do usuário.", status.HTTP_403_FORBIDDEN)
    unidade = session.get(Unidade, data.unidade_id)
    if not unidade or not unidade.ativa:
        raise error("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.", status.HTTP_404_NOT_FOUND)
    expire_orders(session, data.unidade_id)
    product_ids = [item.produto_id for item in data.itens]
    if len(product_ids) != len(set(product_ids)):
        raise error("ITENS_DUPLICADOS", "O mesmo produto não pode aparecer duas vezes.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    offers = {offer.produto_id: offer for offer in session.scalars(select(ProdutoUnidade).where(ProdutoUnidade.unidade_id == data.unidade_id, ProdutoUnidade.produto_id.in_(product_ids), ProdutoUnidade.ativo.is_(True)))}
    if len(offers) != len(product_ids):
        raise error("PRODUTO_INDISPONIVEL", "Produto inexistente ou indisponível na unidade.", status.HTTP_404_NOT_FOUND)
    products = {product.id: product for product in session.scalars(select(Produto).where(Produto.id.in_(product_ids), Produto.ativo.is_(True)))}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    total = 0
    for item in data.itens:
        offer = offers[item.produto_id]
        if offer.saldo_livre < item.quantidade:
            raise error("ESTOQUE_INSUFICIENTE", "Não há quantidade suficiente para um ou mais itens.", status.HTTP_409_CONFLICT)
        total += offer.preco_centavos * item.quantidade
    order = Pedido(unidade_id=data.unidade_id, criado_por_id=user.id, cliente_id=user.id if user.perfil == "CLIENTE" else None, canal_pedido=data.canal_pedido, status="AGUARDANDO_PAGAMENTO", total_centavos=total, criado_em=now, atualizado_em=now, expira_em=now + timedelta(minutes=15))
    session.add(order)
    session.flush()
    for item in data.itens:
        offer = offers[item.produto_id]
        offer.saldo_livre -= item.quantidade
        offer.saldo_reservado += item.quantidade
        session.add(ItemPedido(pedido_id=order.id, produto_unidade_id=offer.id, nome_produto=products[item.produto_id].nome, quantidade=item.quantidade, preco_unitario_centavos=offer.preco_centavos))
    audit(session, user.id, data.unidade_id, "PEDIDO_CRIADO", "PEDIDO", order.id)
    session.commit()
    return order_payload(session, order)


@app.get("/pedidos/{pedido_id}")
def get_order(pedido_id: int, user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> dict:
    expire_orders(session, user.unidade_id if user.perfil != "CLIENTE" else None)
    order = session.get(Pedido, pedido_id)
    if not order:
        raise error("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.", status.HTTP_404_NOT_FOUND)
    ensure_order_access(order, user)
    session.commit()
    return order_payload(session, order)


@app.get("/pedidos")
def list_orders(canal_pedido: str | None = None, pedido_status: str | None = None, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> list[dict]:
    expire_orders(session, user.unidade_id if user.perfil != "CLIENTE" else None)
    query = select(Pedido).order_by(Pedido.id.desc()).offset((page - 1) * limit).limit(limit)
    if user.perfil == "CLIENTE":
        query = query.where(Pedido.cliente_id == user.id)
    else:
        query = query.where(Pedido.unidade_id == user.unidade_id)
    if canal_pedido:
        query = query.where(Pedido.canal_pedido == canal_pedido)
    if pedido_status:
        query = query.where(Pedido.status == pedido_status)
    orders = list(session.scalars(query))
    session.commit()
    return [order_payload(session, order) for order in orders]


@app.post("/pedidos/{pedido_id}/pagamentos/mock")
def mock_payment(pedido_id: int, data: PagamentoRequest, user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> dict:
    if data.resultado not in {"APROVADO", "RECUSADO"}:
        raise error("RESULTADO_INVALIDO", "Resultado deve ser APROVADO ou RECUSADO.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    order = session.get(Pedido, pedido_id)
    if not order:
        raise error("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.", status.HTTP_404_NOT_FOUND)
    ensure_order_access(order, user)
    expire_orders(session, order.unidade_id)
    session.refresh(order)
    existing = session.scalar(select(Pagamento).where(Pagamento.pedido_id == order.id))
    if existing:
        if existing.status != data.resultado:
            raise error("PAGAMENTO_IMUTAVEL", "O pagamento já possui outro resultado.", status.HTTP_409_CONFLICT)
        session.commit()
        return {"pedido_id": order.id, "status": existing.status, "pedido_status": order.status}
    if order.status != "AGUARDANDO_PAGAMENTO":
        raise error("PEDIDO_SEM_PAGAMENTO", "Pedido não aguarda pagamento.", status.HTTP_409_CONFLICT)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(Pagamento(pedido_id=order.id, status=data.resultado, valor_centavos=order.total_centavos, criado_em=now))
    for item in session.scalars(select(ItemPedido).where(ItemPedido.pedido_id == order.id)):
        offer = session.get(ProdutoUnidade, item.produto_unidade_id)
        offer.saldo_reservado -= item.quantidade
        if data.resultado == "APROVADO":
            pass
        else:
            offer.saldo_livre += item.quantidade
    order.status = "CONFIRMADO" if data.resultado == "APROVADO" else "CANCELADO"
    order.motivo_cancelamento = None if data.resultado == "APROVADO" else "PAGAMENTO_RECUSADO"
    order.atualizado_em = now
    audit(session, user.id, order.unidade_id, "PAGAMENTO_MOCK", "PEDIDO", order.id, data.resultado)
    session.commit()
    return {"pedido_id": order.id, "status": data.resultado, "pedido_status": order.status}


@app.patch("/pedidos/{pedido_id}/status")
def update_order_status(pedido_id: int, data: StatusRequest, user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> dict:
    transitions = {"CONFIRMADO": "EM_PREPARO", "EM_PREPARO": "PRONTO", "PRONTO": "ENTREGUE"}
    order = session.get(Pedido, pedido_id)
    if not order:
        raise error("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.", status.HTTP_404_NOT_FOUND)
    ensure_order_access(order, user)
    allowed_roles = {"CONFIRMADO": {"COZINHA", "GERENTE"}, "EM_PREPARO": {"COZINHA", "GERENTE"}, "PRONTO": {"ATENDENTE", "GERENTE"}}
    if data.status not in transitions or order.status != data.status or user.perfil not in allowed_roles[data.status]:
        raise error("TRANSICAO_INVALIDA", "Transição de status não permitida.", status.HTTP_409_CONFLICT)
    order.status = transitions[data.status]
    order.atualizado_em = datetime.now(timezone.utc).replace(tzinfo=None)
    audit(session, user.id, order.unidade_id, "STATUS_ATUALIZADO", "PEDIDO", order.id, order.status)
    session.commit()
    return order_payload(session, order)


@app.get("/me/consentimentos")
def list_consents(user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> list[dict]:
    events = list(session.scalars(select(ConsentimentoEvento).where(ConsentimentoEvento.usuario_id == user.id).order_by(ConsentimentoEvento.finalidade, ConsentimentoEvento.id.desc())))
    latest: dict[str, ConsentimentoEvento] = {}
    for event in events:
        latest.setdefault(event.finalidade, event)
    return [{"finalidade": event.finalidade, "concedido": event.concedido, "versao_termo": event.versao_termo, "criado_em": event.criado_em.isoformat() + "Z"} for event in latest.values()]


@app.post("/me/consentimentos")
def save_consent(data: ConsentimentoRequest, user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> dict:
    if user.perfil != "CLIENTE":
        raise error("PERFIL_SEM_PERMISSAO", "Somente clientes gerenciam seus consentimentos.", status.HTTP_403_FORBIDDEN)
    if data.finalidade not in {"FIDELIDADE", "MARKETING"}:
        raise error("FINALIDADE_INVALIDA", "Finalidade de consentimento inválida.", status.HTTP_422_UNPROCESSABLE_CONTENT)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    event = ConsentimentoEvento(usuario_id=user.id, finalidade=data.finalidade, concedido=data.concedido, versao_termo=data.versao_termo, criado_em=now)
    session.add(event)
    session.flush()
    audit(session, user.id, None, "CONSENTIMENTO_ATUALIZADO", "CONSENTIMENTO", event.id, data.finalidade)
    session.commit()
    return {"id": event.id, "finalidade": event.finalidade, "concedido": event.concedido, "versao_termo": event.versao_termo, "criado_em": now.isoformat() + "Z"}


@app.get("/auditoria")
def list_audit(user: Usuario = Depends(active_user), session: Session = Depends(db_session)) -> list[dict]:
    if user.perfil != "GERENTE":
        raise error("PERFIL_SEM_PERMISSAO", "Somente gerentes consultam auditoria.", status.HTTP_403_FORBIDDEN)
    events = session.scalars(select(Auditoria).where(Auditoria.unidade_id == user.unidade_id).order_by(Auditoria.id.desc()).limit(100))
    return [{"id": event.id, "acao": event.acao, "tipo_entidade": event.tipo_entidade, "entidade_id": event.entidade_id, "detalhes": event.detalhes, "criado_em": event.criado_em.isoformat() + "Z"} for event in events]
