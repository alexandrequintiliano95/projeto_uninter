# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Ponto de entrada: cria a aplicação FastAPI, registra os tratadores de erro e as rotas de cada recurso."""

from fastapi import FastAPI

from app.api.erros import registrar_tratadores
from app.api.rotas import auditoria, auth, catalogo, consentimentos, estoque, pedidos, saude

app = FastAPI(title="API Raízes do Nordeste", version="0.1.0")
registrar_tratadores(app)
for modulo in (saude, auth, catalogo, pedidos, estoque, consentimentos, auditoria):
    app.include_router(modulo.router)
