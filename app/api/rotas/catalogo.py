# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter, Query

from app.api.deps import Sessao
from app.api.schemas import INTEIRO_INVALIDO, CardapioItem, UnidadeResponse, respostas_de_erro
from app.application import catalogo

router = APIRouter(tags=["Catálogo"])


@router.get("/unidades", response_model=list[UnidadeResponse], summary="Listar unidades")
def list_unidades(session: Sessao) -> list[UnidadeResponse]:
    return [UnidadeResponse.model_validate(unidade) for unidade in catalogo.listar_unidades(session)]


@router.get("/unidades/{unidade_id}/cardapio", response_model=list[CardapioItem], responses=respostas_de_erro(404, 422, caminho="/unidades/999/cardapio", exemplos={404: ("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.")}, campo_invalido=("unidade_id", INTEIRO_INVALIDO)), summary="Consultar cardápio da unidade")
def cardapio(session: Sessao, unidade_id: int, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)) -> list[CardapioItem]:
    return [CardapioItem.model_validate(item) for item in catalogo.cardapio(session, unidade_id, page, limit)]
