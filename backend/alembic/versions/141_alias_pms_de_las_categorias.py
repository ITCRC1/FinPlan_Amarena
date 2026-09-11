# -*- coding: utf-8 -*-
"""Cómo llama el PMS a cada categoría de habitación.

Owner, 2026-09-10, mirando el paso del calce antes de subir abril: *«no era
que íbamos a realizar un mapping… de las habitaciones»*.

## La inconsistencia que esto cierra

Para los CANALES el mapeo ya era persistente: el código del PMS vive en
`market_codes` y la decisión queda guardada. Para las CATEGORÍAS no había
nada — el calce se resolvía en la pantalla, en memoria, y se perdía al
guardar. Subir cinco meses significaba elegir la misma categoría cinco veces.

## Por qué el parecido no alcanza

Medido contra el PDF de marzo 2026 de Amarena y su Master Data real:

    PDF                          Master Data                              calce
    GARDEN VIEW DLXE VILLA       Garden View Deluxe-Tented Villa          probable
    BEACH FRONT DLXE VILLA       Beachfront Deluxe-Tented Villa           NINGUNO
    BEACH FRONT MASTER VILLA     Beachfront Master-Suite Tented Villa     NINGUNO

Dos de tres quedan sin calce por un detalle tonto: el PMS parte «BEACH
FRONT» en dos palabras y la propiedad la escribe «Beachfront» en una. Para
el comparador son palabras distintas, y prefiere no adivinar — que es lo
correcto, porque adivinar mal archiva las noches bajo otra categoría y el
total del hotel sigue cuadrando igual.

## Qué hace

Agrega `alias_pms` a `room_type_configs`. El calce pasa a resolverse primero
por alias exacto y sólo después por parecido. El alias **se aprende al
guardar el mes**: no hay pantalla nueva que mantener, y un alias que nadie
mantiene envejece peor que no tenerlo.

Vacío por defecto: el día que esto se despliega no cambia ningún calce — la
primera carga se elige a mano, como hoy, y a partir de ahí sale solo.

Aditiva y reversible.

Revision ID: 141
Revises: 140
"""
import sqlalchemy as sa
from alembic import op

revision = "141"
down_revision = "140"
branch_labels = None
depends_on = None


#: Los tres alias que ya sabemos, leídos del PDF real de marzo 2026 contra el
#: Master Data de Amarena. Se cargan acá para que la PRIMERA carga tampoco
#: pida elegir: el owner ya vio y confirmó este mapa.
#:
#: ⚠️ Se aplican por NOMBRE, no por código. Los códigos (`BI02`, `PO03`…) son
#: canónicos del grupo y los comparten todas las propiedades con nombres
#: distintos: escribir el alias por código le pondría a Corcovado los rótulos
#: del PMS de Amarena. Por nombre exacto, en cualquier otra propiedad esto no
#: encuentra nada y no hace nada.
ALIAS = [
    ("Garden View Deluxe-Tented Villa", "GARDEN VIEW DLXE VILLA"),
    ("Beachfront Deluxe-Tented Villa", "BEACH FRONT DLXE VILLA"),
    ("Beachfront Master-Suite Tented Villa", "BEACH FRONT MASTER VILLA"),
]


def upgrade() -> None:
    op.add_column("room_type_configs",
                  sa.Column("alias_pms", sa.String(120), nullable=False,
                            server_default=""))
    # Sólo donde no haya alias todavía: si alguien ya lo puso a mano, manda el
    # suyo.
    for nombre, alias in ALIAS:
        op.execute(sa.text("""
            UPDATE room_type_configs
               SET alias_pms = :alias
             WHERE name = :nombre
               AND (alias_pms IS NULL OR alias_pms = '')
        """).bindparams(alias=alias, nombre=nombre))


def downgrade() -> None:
    op.drop_column("room_type_configs", "alias_pms")
