"""Cria o histórico de entradas e saídas de estoque."""
from alembic import op
import sqlalchemy as sa

revision = "0002_movimentacao_estoque"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movimentacao_estoque",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_unidade_id", sa.Integer(), sa.ForeignKey("produto_unidade.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("tipo", sa.String(7), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(200), nullable=False),
        sa.Column("saldo_livre_anterior", sa.Integer(), nullable=False),
        sa.Column("saldo_livre_novo", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint("tipo IN ('ENTRADA','SAIDA')", name="ck_movimentacao_tipo"),
        sa.CheckConstraint("quantidade > 0", name="ck_movimentacao_quantidade_positiva"),
        sa.CheckConstraint("saldo_livre_anterior >= 0 AND saldo_livre_novo >= 0", name="ck_movimentacao_saldos_nao_negativos"),
    )


def downgrade() -> None:
    op.drop_table("movimentacao_estoque")
