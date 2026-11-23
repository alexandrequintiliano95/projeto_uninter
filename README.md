# Projeto Uninter

> Nota: trechos alterados com apoio de IA (Claude Code) e revisados pelo autor.

Back-end da rede fictícia Raízes do Nordeste, com Python, FastAPI e SQLite.

## Estado atual

Permissões, fluxo de status, banco, migração, seed e primeira versão da API já estão disponíveis. O fluxo de pedidos foi validado localmente.

- [Modelo inicial: permissões, status e DER](docs/MODELO.md)
- [Plano de execução](PLAN.md)
- [Registro da revisão do plano](PLAN-REVIEW-LOG.md)
- [Contrato da API](docs/API.md)
- [Arquitetura em camadas](docs/ARQUITETURA.md)
- [Diagramas da solução](docs/DIAGRAMAS.md)
- [Roteiro do relatório acadêmico](docs/RELATORIO_MODELO.md)

## Banco inicial

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
python seed.py
```

O banco local será criado em `raizes.db`. O seed cria duas unidades, três produtos, cinco usuários e ofertas com estoque. As senhas são fictícias e servem apenas para os testes locais.

## API local

```powershell
uvicorn app.main:app --reload
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`.

Endpoints disponíveis nesta etapa: `/health`, `/auth/cadastro`, `/auth/login`, `/unidades`, `/unidades/{id}/cardapio`, `/pedidos`, `/pedidos/{id}`, `/pedidos/{id}/pagamentos/mock`, `/pedidos/{id}/cancelamento`, `/pedidos/{id}/status`, `/unidades/{id}/estoque/movimentacoes`, `/me/consentimentos`, `/me/fidelidade` e `/auditoria`.

Testes automatizados: `python -m pytest -q`. A coleção Postman está em `postman/raizes-backend.postman_collection.json` e possui 11 requisições, incluindo casos positivos e negativos.
