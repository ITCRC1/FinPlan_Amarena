# -*- coding: utf-8 -*-
"""El alias de una cuenta por departamento: cómo se lee en los reportes.

Owner, 2026-11-27: «quiero que sea editable un tipo ALIAS para poner como
quiero que salga en los reportes finales» · «hay cuentas que se repiten en
varios departamentos… Cleaning Rooms o Cleaning F&B, y ninguno se ve afectado».

Tabla aparte de `account_mapping` A PROPÓSITO: el seed re-afirma ese mapeo campo
por campo en cada despliegue y borraría los alias sin avisar (CLAUDE.md, «el
SEED manda»). Acá no los toca nunca.

Revision ID: 163
Revises: 162
"""
import sqlalchemy as sa
from alembic import op

revision = "163"
down_revision = "162"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alias_de_cuenta",
        sa.Column("id", sa.String(36), primary_key=True),
        # Sin default de columna: el hotel lo pone el modelo con HOTEL_ID, que
        # es distinto en cada propiedad y esta migración corre en las cuatro.
        sa.Column("hotel_id", sa.String(10), nullable=False),
        # `dept_code` vacío = vale para todos los departamentos.
        sa.Column("dept_code", sa.String(10), nullable=False, server_default=""),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.Column("alias", sa.String(160), nullable=False),
        sa.Column("nota", sa.String(300), nullable=False, server_default=""),
        sa.Column("escrito_por", sa.String(160), nullable=False, server_default=""),
        sa.Column("escrito_el", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hotel_id", "dept_code", "account_code",
                            name="uq_alias_depto_cuenta"),
    )


def downgrade():
    op.drop_table("alias_de_cuenta")
