# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter, Query

from app.api.deps import Sessao
from app.api.schemas import CardapioItem, UnidadeResponse
from app.application import catalogo

router = APIRouter(tags=["Catálogo"])


@router.get("/unidades", response_model=list[UnidadeResponse])
def list_unidades(session: Sessao) -> list[UnidadeResponse]:
    return [UnidadeResponse.model_validate(unidade) for unidade in catalogo.listar_unidades(session)]


@router.get("/unidades/{unidade_id}/cardapio", response_model=list[CardapioItem])
def cardapio(session: Sessao, unidade_id: int, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)) -> list[CardapioItem]:
    return [CardapioItem.model_validate(item) for item in catalogo.cardapio(session, unidade_id, page, limit)]
