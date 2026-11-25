"""Mis libros: la carpeta (el sub-tab) de cada libro.

Owner, 2026-11-24: «podemos crear sub tabs acá… para subir archivos mensuales
para Cierre, Budget o Forecast y otros, ya si no se mezclan» y «es un mismo
repositorio solo que organizado por estos sub tabs».

Los libros que ya estaban caen en OTROS, salvo el Budget Package, que nace donde
corresponde. La carpeta NO entra en la llave única: el repositorio sigue siendo
uno y el título sigue mandando.

Revision ID: 159
Revises: 158
"""
import sqlalchemy as sa
from alembic import op

revision = "159"
down_revision = "158"
branch_labels = None
depends_on = None

TITULO_BUDGET_PACKAGE = "Budget Package (todo en un libro)"


def upgrade():
    # server_default se queda puesto: si una versión vieja del backend inserta
    # sin la columna, la fila cae en OTROS en vez de reventar.
    op.add_column("libros_colgados",
                  sa.Column("carpeta", sa.String(16), nullable=False,
                            server_default="OTROS"))
    op.execute(sa.text(
        "UPDATE libros_colgados SET carpeta = 'BUDGET' WHERE titulo = :t"
    ).bindparams(t=TITULO_BUDGET_PACKAGE))


def downgrade():
    op.drop_column("libros_colgados", "carpeta")
