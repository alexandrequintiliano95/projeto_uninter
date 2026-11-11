from datetime import datetime, timedelta, timezone
from os import getenv

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Produto, ProdutoUnidade, Unidade, Usuario


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
