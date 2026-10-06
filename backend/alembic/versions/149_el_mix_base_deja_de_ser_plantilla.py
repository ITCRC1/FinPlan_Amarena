# -*- coding: utf-8 -*-
"""El mix base de Amarena deja de ser la plantilla heredada.

Owner, 2026-10-06: *«corrige, eso está malo... todo debe estar basado en los
nuevos datos que metimos»*.

La base traía **B2B 55% al 20%, Direct website 35% al 15% y OTA 10% al 5%**, con
los otros cuatro sub-canales en cero. Eso no es Amarena: el hotel vende 8% por
agencia y 40% por OTA en enero, y **una OTA al 5% no existe**. Son valores de
plantilla que nadie reemplazó al dar de alta la propiedad, y de ahí salía el Net
Factor 0.8325 que el Budget 2027 venía arrastrando.

⚠️ **Se veía razonable, y por eso duró.** 0.8325 cae en el rango creíble de un
hotel. Si hubiera dado 0.95 o 0.60 alguien lo habría cuestionado el primer día.

## De dónde salen los números nuevos

El mix es el **promedio del año ponderado por la venta de cada mes** del BUDGET
Working 2027 — no el promedio simple, que con un mix estacional da distinto. Las
comisiones son las que cerró el owner el 2026-10-05.

El Direct va en **0%** a propósito: su costo —tarjeta, motor de reservas,
promoción y el departamento de Sales & Marketing— ya está presupuestado en el
OPEX 2027, $175.073 entre las cinco cuentas. Cobrarlo también como descuento de
tarifa era contarlo dos veces.

Net Factor que implica esta base: **0.8684**, el mismo que da el escenario 2027
con su mix mensual.

## ⚠️ Qué puede mover

La base aplica a **todo sub-canal que no tenga excepción propia**, así que un
escenario sin excepciones cambia de Net Factor con esto. No pude medir cuáles:
la base sólo resuelve dentro de la red de Railway y desde fuera no se alcanza.

Dos cosas acotan el riesgo y conviene tenerlas presentes:

* El motor **prefiere el factor de las tarifas** (`net_rate / rack_rate`) sobre
  el del mix. En un escenario con tarifas netas cargadas —que son todos los que
  tienen datos— esto no mueve nada hasta que alguien corra el APLICAR.
* BUDGET Working 2027 tiene sus doce meses cargados como excepción, así que
  **no lo toca**.

Lo que sí cambia seguro, y es el punto: **un escenario nuevo nace con el mix de
Amarena y no con el de la plantilla.**

Revision ID: 149
Revises: 148
"""
from alembic import op
import sqlalchemy as sa

revision = "149"
down_revision = "148"
branch_labels = None
depends_on = None

#: (code, nombre en pantalla, mix, comisión) — como fracción, que es como lo
#: guarda la tabla. Se busca por code O por nombre, igual que la 148: el code
#: depende de cómo se sembró la propiedad.
NUEVA_BASE = [
    ("B2B",         "B2B — agency / DMC / TO",           "0.0992", "0.3000"),
    ("DIR_WEB",     "Direct — website / booking engine", "0.2303", "0.0000"),
    ("DIR_TEL",     "Direct — phone / email / social",   "0.2137", "0.0000"),
    ("CRC_DIRECT",  "Costa Rica Collection direct",      "0.0958", "0.1000"),
    ("DIR_GROUPS",  "Direct groups",                     "0.0523", "0.2000"),
    ("EXEC_DIRECT", "Executive personal direct",         "0.0166", "0.0000"),
    ("OTA",         "OTA",                               "0.2921", "0.2800"),
]

#: La plantilla que había antes, para que el downgrade devuelva exactamente eso
#: y no un cero que rompería la suma del mix.
BASE_ANTERIOR = [
    ("B2B",         "B2B — agency / DMC / TO",           "0.5500", "0.2000"),
    ("DIR_WEB",     "Direct — website / booking engine", "0.3500", "0.1500"),
    ("DIR_TEL",     "Direct — phone / email / social",   "0.0000", "0.0000"),
    ("CRC_DIRECT",  "Costa Rica Collection direct",      "0.0000", "0.0000"),
    ("DIR_GROUPS",  "Direct groups",                     "0.0000", "0.0000"),
    ("EXEC_DIRECT", "Executive personal direct",         "0.0000", "0.0000"),
    ("OTA",         "OTA",                               "0.1000", "0.0500"),
]

_SQL = sa.text(
    "UPDATE canales_comerciales SET mix_pct = :mix, comision_pct = :com "
    "WHERE code = :code OR nombre = :nombre"
)


def _aplicar(filas) -> None:
    conn = op.get_bind()
    for code, nombre, mix, com in filas:
        conn.execute(_SQL, {"code": code, "nombre": nombre, "mix": mix, "com": com})


def upgrade() -> None:
    _aplicar(NUEVA_BASE)


def downgrade() -> None:
    _aplicar(BASE_ANTERIOR)
