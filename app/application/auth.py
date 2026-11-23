from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.errors import NaoAutenticado
from app.infrastructure.models import Usuario
from app.infrastructure.repositorios import UsuarioRepositorio
from app.infrastructure.seguranca import TOKEN_MINUTES, criar_token, ler_token, verificar_senha


@dataclass(frozen=True)
class Login:
    access_token: str
    token_type: str
    expires_in: int
    user_id: int
    perfil: str


def autenticar(session: Session, email: str, senha: str) -> Login:
    usuario = UsuarioRepositorio(session).por_email(email.lower().strip())
    if not usuario or not usuario.ativo or not verificar_senha(senha, usuario.senha_hash):
        raise NaoAutenticado("CREDENCIAIS_INVALIDAS", "E-mail ou senha inválidos.")
    return Login(access_token=criar_token(usuario.id, usuario.perfil), token_type="Bearer", expires_in=TOKEN_MINUTES * 60, user_id=usuario.id, perfil=usuario.perfil)


def usuario_do_token(session: Session, token: str | None) -> Usuario:
    if not token:
        raise NaoAutenticado("NAO_AUTENTICADO", "Token não informado.")
    usuario = UsuarioRepositorio(session).obter(ler_token(token))
    if not usuario or not usuario.ativo:
        raise NaoAutenticado("USUARIO_INATIVO", "Usuário não encontrado ou inativo.")
    return usuario
