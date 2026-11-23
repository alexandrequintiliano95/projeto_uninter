# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
"""Cria o extrato de pontos de fidelidade e guarda o desconto por pontos no pedido."""
from alembic import op
import sqlalchemy as sa

revision = "0003_fidelidade"
down_revision = "0002_movimentacao_estoque"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pedido", sa.Column("desconto_centavos", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("pedido", sa.Column("pontos_resgatados", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "fidelidade_movimento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("pedido_id", sa.Integer(), sa.ForeignKey("pedido.id"), nullable=False),
        sa.Column("tipo", sa.String(8), nullable=False),
        sa.Column("pontos", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint("tipo IN ('CREDITO','DEBITO','ESTORNO')", name="ck_fidelidade_tipo"),
        sa.CheckConstraint("pontos > 0", name="ck_fidelidade_pontos_positivos"),
    )


def downgrade() -> None:
    op.drop_table("fidelidade_movimento")
    with op.batch_alter_table("pedido") as batch:
        batch.drop_column("pontos_resgatados")
        batch.drop_column("desconto_centavos")
