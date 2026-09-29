# -*- coding: utf-8 -*-
"""El resumen del hotel que cierra el reporte del PMS, por mes.

Owner, 2026-09-29, pidiendo el Resumen Consolidado en el Dashboard.

## Lo que faltaba

El PDF de Skill4 termina con un bloque del HOTEL —no por categoría— y hasta
hoy se leía para cuadrar y se tiraba:

    Capacidad de Hab: 16      Total de Habitac: 496
    Total de Hab Disp: 238    Total Hab Bloq: 258
    Total de Ingresos del Hotel: 6606.88

`actual_room_stats` guarda por categoría, y las habitaciones disponibles y
bloqueadas no son de ninguna categoría. Sin ellas no existe el **«% Ocupación
sobre habitaciones disponibles»**, que es la ocupación que la propiedad mira:
en marzo 2026 da 21.4% contra el 10.3% sobre el inventario completo, porque
ese mes hubo 258 habitaciones-noche bloqueadas de 496. Dos números que miden
cosas distintas y el sistema sólo sabía calcular uno.

## ⚠️ No se rellena hacia atrás

Los seis meses ya cargados quedan SIN resumen. No se puede inventar: las
bloqueadas son un hecho operativo —cuántas habitaciones estuvieron fuera de
servicio— y no salen de multiplicar nada. Se llenan volviendo a subir el PDF
de cada mes.

⚠️ Y **sólo el PDF los trae**. La base plana («Datos») es sólo el detalle por
agencia: un mes cargado desde el Excel deja este resumen vacío, y eso es
correcto porque el archivo no lo dice.

Aditiva y reversible.

Revision ID: 147
Revises: 146
"""
import sqlalchemy as sa
from alembic import op

revision = "147"
down_revision = "146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actual_room_stats_mes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36),
                  sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("capacidad_hab", sa.Integer, nullable=False, server_default="0"),
        sa.Column("habitaciones_totales", sa.Numeric(12, 2), nullable=False,
                  server_default="0"),
        sa.Column("habitaciones_disponibles", sa.Numeric(12, 2), nullable=False,
                  server_default="0"),
        sa.Column("habitaciones_bloqueadas", sa.Numeric(12, 2), nullable=False,
                  server_default="0"),
        sa.Column("ingreso_puntos_venta", sa.Numeric(14, 2), nullable=False,
                  server_default="0"),
        sa.Column("ingreso_total_hotel", sa.Numeric(14, 2), nullable=False,
                  server_default="0"),
        sa.UniqueConstraint("scenario_id", "month", name="uq_roomstat_mes"),
    )


def downgrade() -> None:
    op.drop_table("actual_room_stats_mes")
