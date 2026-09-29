# -*- coding: utf-8 -*-
"""Las noches disponibles de un mes cargado son las de TODO el inventario.

Owner, 2026-09-28: *«las habitaciones disponibles siempre deben ser 16 por el
número de días del mes. no puede cambiar»*.

## El defecto

`put_room_stats_entry` escribía una fila **sólo por la categoría que había
vendido** ese mes. Una categoría sin ventas no dejaba fila, y como las noches
disponibles del mes se arman sumando las filas, esa categoría **desaparecía
del inventario**.

En Amarena la Garden View · Accesible (1 unidad) no vendió de marzo a julio.
Resultado en producción, medido:

    mes      noches disp.   deberían ser   ocupación    debería ser
    marzo         465            496          4.30%         4.03%
    abril         450            480         10.22%         9.58%
    mayo          465            496         12.90%        12.10%
    junio         450            480         14.00%        13.13%
    julio         465            496         28.39%        26.61%
    agosto        496            496         40.73%        40.73%

⚠️ Es el modo de falla caro: el ingreso cuadra, el total cuadra, las noches
vendidas cuadran — **sólo el denominador está mal**, y la ocupación y el
RevPAR salen inflados sin un solo síntoma. Agosto sale bien y eso lo esconde
más: la serie parece consistente. Se destapó comparando contra el Excel de
segmentación que mantiene la propiedad, que siempre usó 16.

## Qué hace

Por cada mes que ya tiene estadística cargada, agrega en **cero** las
categorías activas que no tienen fila, con su `nights_available = units x días
del mes`, y re-afirma el `units` y las noches disponibles de las que sí están
contra `RoomTypeConfig`.

Que una categoría no venda es un dato del mes; que exista, no.

Sólo toca meses que YA tienen filas: agregar categorías a un mes vacío lo
haría figurar como cargado —`cargado` es «tiene filas»— y un mes que nadie
subió se leería como un mes sin ventas, que es otra cosa.

No mueve noches vendidas, pax ni ingreso de ninguna fila existente.

Revision ID: 143
Revises: 142
"""
import calendar
import uuid

import sqlalchemy as sa
from alembic import op

revision = "143"
down_revision = "142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Las categorías activas de cada propiedad, con su inventario.
    cats = conn.execute(sa.text("""
        SELECT hotel_id, name, units FROM room_type_configs WHERE active
    """)).fetchall()
    if not cats:
        return
    por_hotel: dict[str, list[tuple[str, int]]] = {}
    for hotel_id, name, units in cats:
        por_hotel.setdefault(hotel_id, []).append((name, int(units or 0)))

    # Los meses que ya tienen estadística, con el año de su escenario —los días
    # del mes dependen del año (febrero) y del mes.
    meses = conn.execute(sa.text("""
        SELECT DISTINCT a.scenario_id, a.month, s.year, s.hotel_id
          FROM actual_room_stats a
          JOIN scenarios s ON s.id = a.scenario_id
    """)).fetchall()

    for scenario_id, month, year, hotel_id in meses:
        del_mes = por_hotel.get(hotel_id) or []
        if not del_mes:
            continue
        dias = calendar.monthrange(int(year), int(month))[1]
        presentes = {r[0] for r in conn.execute(sa.text("""
            SELECT room_type_name FROM actual_room_stats
             WHERE scenario_id = :sc AND month = :m
        """).bindparams(sc=scenario_id, m=month)).fetchall()}

        for nombre, units in del_mes:
            if nombre in presentes:
                # Re-afirma el inventario de la que sí está. No toca las
                # cifras vendidas.
                conn.execute(sa.text("""
                    UPDATE actual_room_stats
                       SET units = :u, nights_available = :na
                     WHERE scenario_id = :sc AND month = :m
                       AND room_type_name = :n
                """).bindparams(u=units, na=units * dias, sc=scenario_id,
                                m=month, n=nombre))
            elif units:
                # La que falta entra en cero, con su inventario. Sin unidades
                # («Other Rooms Revenue») no hay inventario que declarar.
                #
                # ⚠️ El `id` se genera acá. En el modelo es un `String(36)` con
                # default de PYTHON (`uuid4`), no de servidor: un INSERT crudo
                # que lo omita revienta con NOT NULL y se lleva el deploy
                # entero por delante.
                conn.execute(sa.text("""
                    INSERT INTO actual_room_stats
                        (id, scenario_id, room_type_name, month, units,
                         nights_available, nights_occupied, revenue, pax)
                    VALUES (:id, :sc, :n, :m, :u, :na, 0, 0, 0)
                """).bindparams(id=str(uuid.uuid4()), sc=scenario_id, n=nombre,
                                m=month, u=units, na=units * dias))


def downgrade() -> None:
    # Se borran sólo las filas que esta migración pudo haber creado: las que
    # están enteramente en cero. Una fila en cero que alguien haya cargado a
    # mano dice lo mismo, así que perderla no cambia ninguna cifra.
    op.execute("""
        DELETE FROM actual_room_stats
         WHERE nights_occupied = 0 AND revenue = 0 AND pax = 0
    """)
