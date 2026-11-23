# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter, status

from app.api.deps import Sessao
from app.api.schemas import CadastroRequest, CadastroResponse, LoginRequest, LoginResponse, respostas_de_erro
from app.application import auth

router = APIRouter(tags=["Autenticação"])


@router.post("/auth/cadastro", status_code=status.HTTP_201_CREATED, response_model=CadastroResponse, responses=respostas_de_erro(409, 422), summary="Cadastrar cliente")
def signup(data: CadastroRequest, session: Sessao) -> CadastroResponse:
    """Cadastro público de cliente. Perfil e unidade enviados no corpo são ignorados: a conta nasce como CLIENTE."""
    usuario = auth.cadastrar_cliente(session, data.nome, data.email, data.senha, data.aceite_termos, data.aceita_fidelidade, data.aceita_marketing)
    return CadastroResponse.model_validate(usuario)


@router.post("/auth/login", response_model=LoginResponse, responses=respostas_de_erro(401, 422), summary="Fazer login")
def login(data: LoginRequest, session: Sessao) -> LoginResponse:
    return LoginResponse.model_validate(auth.autenticar(session, data.email, data.senha))
