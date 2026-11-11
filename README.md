# Projeto Uninter

Back-end da rede fictícia Raízes do Nordeste, com Python, FastAPI e SQLite.

## Estado atual

Permissões, fluxo de status e modelo de dados definidos. A API, as migrações e os testes ainda serão implementados.

- [Modelo inicial: permissões, status e DER](docs/MODELO.md)
- [Plano de execução](PLAN.md)
- [Registro da revisão do plano](PLAN-REVIEW-LOG.md)

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

Próxima etapa: criar os endpoints da API usando os modelos deste banco.
