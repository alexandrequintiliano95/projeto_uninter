"""Formato único de erro: {error, message, details, timestamp, path}, para qualquer falha da API."""

from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import Conflito, DadosInvalidos, ErroDominio, NaoAutenticado, NaoEncontrado, PermissaoNegada, ServicoIndisponivel

STATUS_POR_ERRO: dict[type[ErroDominio], int] = {
    NaoAutenticado: status.HTTP_401_UNAUTHORIZED,
    PermissaoNegada: status.HTTP_403_FORBIDDEN,
    NaoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflito: status.HTTP_409_CONFLICT,
    DadosInvalidos: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ServicoIndisponivel: status.HTTP_503_SERVICE_UNAVAILABLE,
}

ERROS_HTTP = {
    status.HTTP_404_NOT_FOUND: ("RECURSO_NAO_ENCONTRADO", "Recurso não encontrado."),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("METODO_NAO_PERMITIDO", "Método HTTP não permitido para este recurso."),
}


def resposta_de_erro(request: Request, http_status: int, codigo: str, mensagem: str, details: list[dict] | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    content = {"error": codigo, "message": mensagem, "details": details or [], "timestamp": timestamp, "path": request.url.path}
    return JSONResponse(status_code=http_status, content=content, headers=headers)


async def _erro_dominio(request: Request, exc: ErroDominio) -> JSONResponse:
    http_status = next((codigo for tipo, codigo in STATUS_POR_ERRO.items() if isinstance(exc, tipo)), status.HTTP_400_BAD_REQUEST)
    return resposta_de_erro(request, http_status, exc.codigo, exc.mensagem)


async def _erro_validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [{"field": ".".join(str(parte) for parte in erro["loc"][1:]) or str(erro["loc"][0]), "message": erro["msg"]} for erro in exc.errors()]
    return resposta_de_erro(request, status.HTTP_422_UNPROCESSABLE_CONTENT, "DADOS_INVALIDOS", "Um ou mais campos da requisição são inválidos.", details)


async def _erro_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codigo, mensagem = ERROS_HTTP.get(exc.status_code, ("ERRO_HTTP", str(exc.detail)))
    return resposta_de_erro(request, exc.status_code, codigo, mensagem, headers=exc.headers)


async def _erro_inesperado(request: Request, exc: Exception) -> JSONResponse:
    return resposta_de_erro(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "ERRO_INTERNO", "Erro interno inesperado. Tente novamente mais tarde.")


def registrar_tratadores(app: FastAPI) -> None:
    app.add_exception_handler(ErroDominio, _erro_dominio)
    app.add_exception_handler(RequestValidationError, _erro_validacao)
    app.add_exception_handler(StarletteHTTPException, _erro_http)
    app.add_exception_handler(Exception, _erro_inesperado)
