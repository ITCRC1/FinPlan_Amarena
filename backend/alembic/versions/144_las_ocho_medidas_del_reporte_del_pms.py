# -*- coding: utf-8 -*-
"""Las ocho medidas del reporte del PMS se guardan, no solo tres.

Owner, 2026-09-28, pidiendo la estadística en el Dashboard: *«una por tab del
excel»*. Los tabs del Excel de segmentación son ocho — Ing.Hospedaje, Ing.AyB,
Ing.Otros, Hab.Entradas, Hab.Estancias, Cli.Entradas, Cli.Estancias y Tarifa
Promedio — y el sistema sólo guardaba tres.

## Lo que se perdía

El lector del PMS lee las ocho columnas y las muestra en pantalla; el guardado
escribía `nights_occupied` (Hab.Estancias), `pax` (Cli.Estancias) y `revenue`
(Ing.Hospedaje) y descartaba el resto.

Medido contra los seis meses de Amarena ya cargados:

    Ing.Otros      mar-ago   $14,754.85   se perdía entero
    Hab.Entradas   mar-ago          366   se perdía entero
    Cli.Entradas   mar-ago          833   se perdía entero
    Ing.AyB        mar-ago        $0.00   (el reporte no lo abre por agencia)

Los $14,754 de otros ingresos existían **únicamente** en el Excel que la
propiedad mantiene a mano: el sistema no tenía cómo cuadrarlos ni cómo
mostrarlos, y nada decía que faltaran.

⚠️ **Entradas ≠ Estancias.** Entradas son las llegadas; estancias, las noches.
`nights_occupied` y `pax` son y siguen siendo las ESTANCIAS — esta migración
agrega las entradas al lado, no las reemplaza. Confundirlas da un ADR y un
ratio de huéspedes por habitación que parecen razonables y están mal.

## Qué hace

Cuatro columnas en `actual_room_stats` y las mismas cuatro en
`actual_room_stat_canales`, con default 0.

Aditiva y reversible. **No rellena nada hacia atrás**: los seis meses ya
cargados quedan con 0 en las columnas nuevas hasta que se vuelva a subir el
archivo, y 0 ahí significa «esta carga es anterior a que se guardara», no «el
hotel no tuvo otros ingresos». Rellenarlos requeriría releer los archivos, que
esta migración no tiene; el Dashboard lo dice donde se ve.

Revision ID: 144
Revises: 143
"""
import sqlalchemy as sa
from alembic import op

revision = "144"
down_revision = "143"
branch_labels = None
depends_on = None

#: (tabla, columna, precisión). Las mismas cuatro en las dos tablas: la
#: apertura por canal tiene que poder sumar lo mismo que el total, o el día que
#: alguien compare las dos va a encontrar una diferencia que no existe.
COLUMNAS = [
    ("ingreso_ayb", sa.Numeric(14, 2)),
    ("ingreso_otros", sa.Numeric(14, 2)),
    ("hab_entradas", sa.Numeric(12, 2)),
    ("cli_entradas", sa.Numeric(12, 2)),
]
TABLAS = ("actual_room_stats", "actual_room_stat_canales")


def upgrade() -> None:
    for tabla in TABLAS:
        for nombre, tipo in COLUMNAS:
            op.add_column(tabla, sa.Column(nombre, tipo, nullable=False,
                                           server_default="0"))


def downgrade() -> None:
    for tabla in TABLAS:
        for nombre, _tipo in COLUMNAS:
            op.drop_column(tabla, nombre)
