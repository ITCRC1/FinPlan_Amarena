# -*- coding: utf-8 -*-
"""El detalle por canal de la estadística de habitaciones, y qué canal cuenta
para el ADR.

Owner, 2026-09-09, al preguntar cómo se vería el acumulado de abril a agosto:
*«debe haber un check box para que en la misma tabla se de la instrucción que
el CPL no forme parte del ADR global»*.

## Dos cosas, un mismo hallazgo

El PDF del PMS abre cada categoría por agencia y ese detalle se estaba
tirando: se guardaban las filas por categoría y el canal moría con la
pantalla. En marzo 2026 eso esconde lo más importante del mes — **CPL puso el
60.8% de las noches con el 0.7% del ingreso**, y el ADR pasa de $125.44 a
$317.66 según se lo cuente o no.

1. `actual_room_stat_canales` guarda la apertura, para que el mix por canal se
   pueda leer acumulado y no sólo el mes que se está subiendo.
2. `market_codes.cuenta_para_adr` guarda la decisión de qué canal entra a la
   base del ADR. Va en `market_codes` y no en una tabla nueva porque ahí ya
   vive el código del PMS con su canal canónico: es la misma fila.

⚠️ **`cuenta_para_adr` NO cambia noches, pax ni ingreso.** Sólo mueve la BASE
del ADR. Si tocara los totales, el cuadre contra el PDF se rompería y ya no se
podría saber si la diferencia es del archivo o del filtro. El default es
`true`: el día que esto se despliega, ningún ADR de ninguna propiedad se
mueve — sólo cambia cuando alguien desmarca una casilla.

Aditiva y reversible.

Revision ID: 139
Revises: 138
"""
import sqlalchemy as sa
from alembic import op

revision = "139"
down_revision = "138"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actual_room_stat_canales",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36),
                  sa.ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("room_type_name", sa.String(120), nullable=False),
        sa.Column("canal_code", sa.String(40), nullable=False),
        sa.Column("nights_occupied", sa.Numeric(12, 2), nullable=False,
                  server_default="0"),
        sa.Column("pax", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("revenue", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint("scenario_id", "month", "room_type_name", "canal_code",
                            name="uq_roomstat_canal"),
    )
    op.create_index("ix_roomstat_canal_scenario", "actual_room_stat_canales",
                    ["scenario_id"])
    op.create_index("ix_roomstat_canal_code", "actual_room_stat_canales",
                    ["canal_code"])

    # Default `true`: nada se mueve hasta que alguien desmarque.
    op.add_column("market_codes",
                  sa.Column("cuenta_para_adr", sa.Boolean(), nullable=False,
                            server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("market_codes", "cuenta_para_adr")
    op.drop_index("ix_roomstat_canal_code", table_name="actual_room_stat_canales")
    op.drop_index("ix_roomstat_canal_scenario", table_name="actual_room_stat_canales")
    op.drop_table("actual_room_stat_canales")
