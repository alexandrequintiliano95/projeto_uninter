from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.errors import NaoEncontrado
from app.infrastructure.models import Unidade
from app.infrastructure.repositorios import CatalogoRepositorio


@dataclass(frozen=True)
class ItemCardapio:
    produto_id: int
    nome: str
    descricao: str
    preco_centavos: int
    saldo_disponivel: int


def listar_unidades(session: Session) -> list[Unidade]:
    return CatalogoRepositorio(session).unidades_ativas()


def cardapio(session: Session, unidade_id: int, page: int, limit: int) -> list[ItemCardapio]:
    catalogo = CatalogoRepositorio(session)
    unidade = catalogo.unidade(unidade_id)
    if not unidade or not unidade.ativa:
        raise NaoEncontrado("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.")
    return [
        ItemCardapio(produto_id=oferta.produto_id, nome=produto.nome, descricao=produto.descricao, preco_centavos=oferta.preco_centavos, saldo_disponivel=oferta.saldo_livre)
        for oferta, produto in catalogo.cardapio(unidade_id, page, limit)
    ]
