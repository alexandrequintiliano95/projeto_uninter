# Projeto Uninter

Back-end da rede fictícia Raízes do Nordeste, com Python, FastAPI e SQLite.

## Estado atual

Permissões, fluxo de status, banco, migração, seed e primeira versão da API já estão disponíveis. O fluxo de pedidos foi validado localmente.

- [Modelo inicial: permissões, status e DER](docs/MODELO.md)
- [Plano de execução](PLAN.md)
- [Registro da revisão do plano](PLAN-REVIEW-LOG.md)
- [Contrato da API](docs/API.md)
- [Diagramas da solução](docs/DIAGRAMAS.md)

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

Endpoints disponíveis nesta etapa: `/health`, `/auth/login`, `/unidades`, `/unidades/{id}/cardapio`, `/pedidos`, `/pedidos/{id}`, `/pedidos/{id}/pagamentos/mock` e `/pedidos/{id}/status`.

Testes automatizados: `python -m pytest -q`. A coleção Postman está em `postman/raizes-backend.postman_collection.json` e possui 11 requisições, incluindo casos positivos e negativos.
