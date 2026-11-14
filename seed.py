from pwdlib import PasswordHash
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Produto, ProdutoUnidade, Unidade, Usuario


def seed() -> None:
    password = PasswordHash.recommended()
    with SessionLocal.begin() as session:
        if session.scalar(select(Unidade.id).limit(1)):
            print("Seed já aplicado!")
            return
        unidade_a = Unidade(nome="Raízes Recife Centro", cidade="Recife", uf="PE")
        unidade_b = Unidade(nome="Raízes Caruaru", cidade="Caruaru", uf="PE")
        session.add_all([unidade_a, unidade_b])
        session.flush()
        session.add_all([
            Usuario(nome="Cliente Teste", email="cliente@raizes.local", senha_hash=password.hash("Cliente@123"), perfil="CLIENTE"),
            Usuario(nome="Atendente Recife", email="atendente.recife@raizes.local", senha_hash=password.hash("Atendente@123"), perfil="ATENDENTE", unidade_id=unidade_a.id),
            Usuario(nome="Cozinha Recife", email="cozinha.recife@raizes.local", senha_hash=password.hash("Cozinha@123"), perfil="COZINHA", unidade_id=unidade_a.id),
            Usuario(nome="Gerente Recife", email="gerente.recife@raizes.local", senha_hash=password.hash("Gerente@123"), perfil="GERENTE", unidade_id=unidade_a.id),
            Usuario(nome="Gerente Caruaru", email="gerente.caruaru@raizes.local", senha_hash=password.hash("Gerente@123"), perfil="GERENTE", unidade_id=unidade_b.id),
        ])
        tapioca = Produto(nome="Tapioca de Carne de Sol", descricao="Tapioca recheada com carne de sol")
        cuscuz = Produto(nome="Cuscuz Nordestino", descricao="Cuscuz recheado com queijo coalho")
        suco = Produto(nome="Suco de Cajá", descricao="Suco regional de cajá")
        session.add_all([tapioca, cuscuz, suco])
        session.flush()
        session.add_all([
            ProdutoUnidade(unidade_id=unidade_a.id, produto_id=tapioca.id, preco_centavos=1890, saldo_livre=20),
            ProdutoUnidade(unidade_id=unidade_a.id, produto_id=cuscuz.id, preco_centavos=1590, saldo_livre=15),
            ProdutoUnidade(unidade_id=unidade_a.id, produto_id=suco.id, preco_centavos=890, saldo_livre=30),
            ProdutoUnidade(unidade_id=unidade_b.id, produto_id=tapioca.id, preco_centavos=1990, saldo_livre=10),
            ProdutoUnidade(unidade_id=unidade_b.id, produto_id=suco.id, preco_centavos=950, saldo_livre=12),
        ])
    print("Seed aplicado")


if __name__ == "__main__":
    seed()
