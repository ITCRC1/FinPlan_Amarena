# -*- coding: utf-8 -*-
"""Los market codes que realmente usa Amarena, y el canal de los que se saben.

Owner, 2026-09-10, después de subir marzo–agosto: *«pero que debo decir»*,
frente a la pregunta de a qué canal pertenece cada código del PMS.

## El agujero

`market_codes` venía sembrado con los 13 códigos de **Opera** (BAR, TAFIT,
WEB…). Amarena no usa Opera: usa Skill4, y sus códigos son otros —
`DIRECTOS`, `RESONLINE`, `EXPEDIA HOTEL COLLECT`, `CPL`. Ninguno estaba en
la tabla.

Consecuencia: los nueve canales que traen los seis meses cargados se guardan
bien y se ven bien en las vistas del mes, pero **no ruedan al mix de
canales** — `canal` vacío significa «nadie decidió», y el mix no puede
inventar. Sobre los $154,688 cargados, el 100% del ingreso estaba sin
clasificar.

(Sólo `CPL` existía, y porque el owner lo destildó del ADR: el endpoint de
la casilla crea la fila con canal vacío si no está. O sea que la tabla se
estaba llenando por el camino equivocado.)

## Qué decide esta migración y qué no

Seis códigos no tienen ambigüedad y se registran con su canal:

    DIRECTOS                 Direct Client   el huésped reservó directo
    CPL                      INHOUSE         cortesía — ya está fuera del ADR
    PATROCINIO               INHOUSE         canje, $0.00 de ingreso
    BOOKING                  OTA
    EXPEDIA                  OTA
    EXPEDIA HOTEL COLLECT    OTA

Tres quedan **con canal vacío a propósito**, que es el estado «nadie lo
decidió» — visible y reportado, no adivinado:

    PROMOCIONES             $28,403   ¿tarifa promo directa, o promo en OTA?
    RESONLINE               $26,286   ¿el motor de la web propia, o el
                                      channel manager que reparte a OTAs?
    CAST CENTRAL AMERICA       $974   ¿receptivo con comisión, o corporativo?

⚠️ **No se adivinan aunque el nombre sugiera algo.** El canal define a qué
cubo de COMISIÓN rueda el código (`CANAL_A_COMISION`), y de ahí sale el Net
Rate. RESONLINE como `Website` no paga comisión de intermediario; como `OTA`
sí. Son $26,286 que cambian de trato según una letra, el total sigue
cuadrando en los dos casos, y nadie lo nota después. PROMOCIONES y RESONLINE
juntos son el **35% del ingreso cargado**: es la peor plata para adivinar.

Los tres se asignan desde la pantalla, que es lo que agrega este mismo
cambio: la vista «Por canal» del cierre gana un desplegable al lado de la
casilla del ADR, donde el dato está sobre la mesa en el momento justo.

## Convive con el seed

`seed_market_codes` es no destructivo para `nombre` y `canal`: sólo inserta
lo que falta y re-afirma el orden. Los nueve códigos van también al JSON,
así que una base nueva los trae; acá se aplican a la que ya está corriendo.
Si el owner cambia un canal en pantalla, ni el seed ni esta migración lo
pisan — el `WHERE` sólo toca filas sin canal.

Aditiva y reversible.

Revision ID: 142
Revises: 141
"""
import sqlalchemy as sa
from alembic import op

revision = "142"
down_revision = "141"
branch_labels = None
depends_on = None


#: (código, nombre, canal, orden). Canal vacío = nadie lo decidió todavía.
CODIGOS = [
    ("DIRECTOS",              "Directos",                "Direct Client", 101),
    ("PROMOCIONES",           "Promociones",             "",              102),
    ("RESONLINE",             "ResOnline",               "",              103),
    ("BOOKING",               "Booking.com",             "OTA",           104),
    ("EXPEDIA",               "Expedia",                 "OTA",           105),
    ("EXPEDIA HOTEL COLLECT", "Expedia Hotel Collect",   "OTA",           106),
    ("CAST CENTRAL AMERICA",  "CAST Central America",    "",              107),
    ("CPL",                   "Cortesía / Complimentary", "INHOUSE",      108),
    ("PATROCINIO",            "Patrocinio / Canje",      "INHOUSE",       109),
]


def upgrade() -> None:
    for code, nombre, canal, orden in CODIGOS:
        # Inserta el que falte. `ON CONFLICT DO NOTHING` y no un UPDATE: si la
        # fila ya está, su canal es del owner y no se toca.
        op.execute(sa.text("""
            INSERT INTO market_codes (code, nombre, canal, orden, activo,
                                      cuenta_para_kpis)
            VALUES (:code, :nombre, :canal, :orden, true, true)
            ON CONFLICT (code) DO NOTHING
        """).bindparams(code=code, nombre=nombre, canal=canal, orden=orden))

    # CPL ya existía —lo creó el endpoint de la casilla del ADR, con canal
    # vacío— así que el INSERT de arriba no lo alcanza. Se le pone el canal
    # SÓLO si sigue sin uno, y sin tocar `cuenta_para_kpis`: esa la decidió
    # el owner y vale más que esto.
    for code, _nombre, canal, _orden in CODIGOS:
        if not canal:
            continue
        op.execute(sa.text("""
            UPDATE market_codes SET canal = :canal
             WHERE code = :code AND (canal IS NULL OR canal = '')
        """).bindparams(code=code, canal=canal))


def downgrade() -> None:
    # Sólo los que esta migración pudo haber creado. Se dejan los que el owner
    # ya haya tocado: borrar por código a ciegas se llevaría su trabajo.
    for code, _nombre, _canal, _orden in CODIGOS:
        op.execute(sa.text(
            "DELETE FROM market_codes WHERE code = :code"
        ).bindparams(code=code))
