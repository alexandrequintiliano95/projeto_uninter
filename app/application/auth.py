# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.application.consentimentos import adicionar_evento
from app.domain.enums import FinalidadeConsentimento, Perfil
from app.domain.errors import Conflito, DadosInvalidos, NaoAutenticado
from app.domain.regras import VERSAO_TERMOS_DE_USO, exigir_senha_forte
from app.infrastructure.models import Usuario
from app.infrastructure.repositorios import AuditoriaRepositorio, UsuarioRepositorio
from app.infrastructure.seguranca import TOKEN_MINUTES, criar_token, gerar_hash_senha, ler_token, verificar_senha


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


def cadastrar_cliente(session: Session, nome: str, email: str, senha: str, aceite_termos: bool, aceita_fidelidade: bool = False, aceita_marketing: bool = False) -> Usuario:
    """Cadastro público: sempre cria um CLIENTE sem unidade. Perfil e unidade nunca vêm do request.

    O aceite dos termos de uso é obrigatório (base para executar o contrato). Fidelidade e marketing são consentimentos
    opcionais e separados: só geram evento quando a pessoa marca a opção.
    """
    if not aceite_termos:
        raise DadosInvalidos("TERMOS_NAO_ACEITOS", "É preciso aceitar os termos de uso para criar a conta.")
    exigir_senha_forte(senha)
    usuarios = UsuarioRepositorio(session)
    email = email.lower().strip()
    if usuarios.por_email(email):
        raise Conflito("EMAIL_JA_CADASTRADO", "Já existe uma conta com este e-mail.")
    usuario = Usuario(nome=nome, email=email, senha_hash=gerar_hash_senha(senha), perfil=Perfil.CLIENTE.value, unidade_id=None, ativo=True)
    usuarios.adicionar(usuario)
    AuditoriaRepositorio(session).registrar(usuario.id, None, "USUARIO_CADASTRADO", "USUARIO", usuario.id, f"Termos de uso {VERSAO_TERMOS_DE_USO} aceitos")
    for finalidade, concedido in ((FinalidadeConsentimento.FIDELIDADE, aceita_fidelidade), (FinalidadeConsentimento.MARKETING, aceita_marketing)):
        if concedido:
            adicionar_evento(session, usuario, finalidade, True, VERSAO_TERMOS_DE_USO)
    session.commit()
    return usuario
