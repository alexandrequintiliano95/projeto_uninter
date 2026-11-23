# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter

from app.api.deps import Sessao
from app.api.schemas import LoginRequest, LoginResponse
from app.application import auth

router = APIRouter(tags=["Autenticação"])


@router.post("/auth/login", response_model=LoginResponse)
def login(data: LoginRequest, session: Sessao) -> LoginResponse:
    return LoginResponse.model_validate(auth.autenticar(session, data.email, data.senha))
