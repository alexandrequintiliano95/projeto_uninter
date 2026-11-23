# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Erros de regra de negócio. A camada de API converte cada tipo em um status HTTP."""


class ErroDominio(Exception):
    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


class NaoAutenticado(ErroDominio):
    """Usuário sem token, com token inválido ou inativo."""


class PermissaoNegada(ErroDominio):
    """Perfil ou unidade sem permissão para a operação."""


class NaoEncontrado(ErroDominio):
    """Registro inexistente ou fora do escopo do usuário."""


class Conflito(ErroDominio):
    """Operação incompatível com o estado atual (estoque, status, pagamento)."""


class DadosInvalidos(ErroDominio):
    """Dados que passam na validação de formato, mas violam uma regra de negócio."""


class ServicoIndisponivel(ErroDominio):
    """Dependência externa (ex.: provedor de pagamento) temporariamente indisponível."""
