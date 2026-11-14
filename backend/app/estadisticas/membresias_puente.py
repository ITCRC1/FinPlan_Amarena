# -*- coding: utf-8 -*-
"""El puente de las membresías del club hacia las cuentas estadísticas 98xx.

Owner, 2026-11-11, mirando el cuadro de membresías: *«por qué estas
estadísticas no quedaron mapeadas»*.

## Por qué faltaba

Había **dos** tablas de membresías conviviendo y el catálogo apuntaba a la
equivocada:

* `club_membership_stats` — cuatro columnas fijas. Es la que nombran los
  `legado` de 9800-9803, la que lee `detail_excel` y la que escribe el
  importador del mayor. Para Amarena 2026 tenía siete filas de basura.
* `membresias_mes` — una fila por concepto, nacida el 29-sep-2026 cuando el
  owner pidió el tab de MEMBRESÍAS. Es la que dibuja la pantalla y la que
  tiene los números de verdad (130 socios en agosto y setiembre).

La segunda no la usaba nadie más que su propia API: una isla. Y
`statistical_entries` estaba **vacía en toda la base**.

## Cinco conceptos contra cuatro cuentas

El catálogo tenía cuatro códigos y la pantalla cinco conceptos, así que
«pendiente de firma» y «excepción no paga» no tenían dónde caer. Se agregaron
**9804** y **9805** en `seed_data/stats_catalog.json`.

⚠️ **Y el choque de fondo no se cierra con dos códigos más.** `membresias_mes`
guarda un concepto por FILA a propósito —su documentación lo dice: «hoy hay una
segunda etapa del club, mañana habrá una tercera»— justo para que un estado
nuevo sea un renglón y no una migración. Este catálogo usa códigos FIJOS. Son
principios opuestos. El día que la propiedad agregue un estado, el concepto se
va a cargar bien en la pantalla y **no va a tener cuenta**.

Por eso `sincronizar_membresias` **devuelve** los conceptos que no supo mapear
en vez de descartarlos en silencio. Un conteo que desaparece sin avisar es
exactamente el modo de falla que este proyecto persigue: el total sigue
cuadrando contra sí mismo y nadie ve que faltan dos socios.

## El total es calculado, no leído

`membresias_mes` **no guarda** el total —su modelo lo explica: guardarlo
abriría la puerta a que el total y sus partes digan cosas distintas—. Así que
9800 se calcula acá como la suma de los conceptos del mes, incluidos los que no
tienen cuenta propia. Si se sumaran sólo los mapeados, el total del estadístico
no cuadraría contra el de la pantalla.

⚠️ Un mes **sin ninguna fila** no es un mes en cero: es un mes que nadie contó.
No se escribe, igual que lo deja en blanco la pantalla. Escribir un cero diría
«el club no tiene socios en octubre», que es una afirmación que nadie hizo.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membresia_mes import MembresiaMes
from app.models.statistical_entry import StatisticalEntry

#: Depto del Club. El mismo que declara el catálogo en `deptos` para las 98xx.
DEPT_CLUB = "260"

#: Concepto de `membresias_mes` → cuenta estadística.
#:
#: `activas` va a 9802 «pagando»: los rótulos difieren —«activas de cobro» en
#: la pantalla de la propiedad— pero es el mismo hecho, y renombrar la cuenta
#: rompería el histórico que ya se reporta con ese código.
CONCEPTO_A_CUENTA: dict[str, str] = {
    "activas":          "9802",
    "condicionados":    "9801",
    "plan_pago":        "9803",
    "pendiente_firma":  "9804",
    "excepcion":        "9805",
}

#: El total. No es un concepto guardado: es la suma de todos ellos.
CUENTA_TOTAL = "9800"

#: Todo lo que este puente escribe, para poder borrarlo sin tocar lo que
#: cargó un archivo o una pantalla.
CUENTAS = {CUENTA_TOTAL, *CONCEPTO_A_CUENTA.values()}

#: `origen` de lo que escribe el puente. 'MOTOR' = lo calculó el sistema, así
#: que una recarga lo puede pisar sin preguntar; 'ARCHIVO' y 'MANUAL' no.
ORIGEN = "MOTOR"


#: Los cuatro campos que pedía `club_membership_stats`, y de qué concepto de
#: `membresias_mes` sale cada uno. `total` no está acá: es la SUMA.
#:
#: `pagando` ≡ `activas`: los rótulos difieren —«Membresías Pagando» en la
#: pantalla del Club, «activas de cobro» en la del cierre— pero es el mismo
#: hecho, y así lo trató siempre el cálculo del ingreso del Club
#: (`club_fee_budgets.base = 'pagando'`).
LEGADO_A_CONCEPTO = {
    "condicionados": "condicionados",
    "pagando": "activas",
    "acuerdo_pago": "plan_pago",
}


async def vista_legado(db: AsyncSession, scenario_id: str
                       ) -> tuple[dict[str, list[int]], set[int]]:
    """Las membresías con la FORMA vieja, leídas de la tabla nueva.

    Devuelve `({campo: [12 meses]}, meses_con_dato)`, igual que devolvía
    `club_membership_stats`. Existe para que los seis consumidores de la tabla
    vieja —la pantalla del Club, el P&L, su detalle, el clonado de escenarios,
    el importador del mayor y el Excel de detalle— cambien de fuente **sin
    reescribirse enteros**.

    ⚠️ **`total` es la SUMA de los cinco conceptos, no un campo guardado.** La
    tabla vieja lo guardaba aparte, y por eso podía decir `total=130` con
    `pagando=86`: dos números sobre el mismo hecho, sin nada que los obligara a
    cuadrar. En Amarena llegó a tener `total=0` junto a `pagando=86`. Acá el
    total no se puede contradecir con sus partes porque sale de ellas.

    ⚠️ **Los meses con dato se devuelven aparte.** Para el saldo del año hay
    que distinguir «diciembre no se cargó» de «diciembre es cero»; confundirlos
    inventa socios. Ver `club_stats_api.cierre`.
    """
    filas = (await db.execute(
        select(MembresiaMes).where(MembresiaMes.scenario_id == scenario_id)
    )).scalars().all()

    out = {c: [0] * 12 for c in ("total", *LEGADO_A_CONCEPTO)}
    cargados: set[int] = set()
    for f in filas:
        m = f.month or 0
        if not 1 <= m <= 12:
            continue
        cargados.add(m)
        cant = int(Decimal(str(f.cantidad or 0)))
        out["total"][m - 1] += cant
        for campo, concepto in LEGADO_A_CONCEPTO.items():
            if f.concepto == concepto:
                out[campo][m - 1] = cant
    return out, cargados


async def sincronizar_membresias(db: AsyncSession, scenario_id: str) -> dict:
    """Vuelca `membresias_mes` del escenario en `statistical_entries`.

    Reemplaza **sólo** las cuentas de este puente y sólo las de este escenario.
    Devuelve qué escribió y, sobre todo, `sin_cuenta`: los conceptos que el
    catálogo no conoce.
    """
    filas = (await db.execute(
        select(MembresiaMes).where(MembresiaMes.scenario_id == scenario_id)
    )).scalars().all()

    # Por mes: {concepto: cantidad}. Un mes sin filas no aparece acá, y por eso
    # no se escribe.
    por_mes: dict[int, dict[str, Decimal]] = {}
    for f in filas:
        por_mes.setdefault(f.month, {})[f.concepto] = Decimal(str(f.cantidad or 0))

    sin_cuenta = sorted({
        c for conceptos in por_mes.values() for c in conceptos
        if c not in CONCEPTO_A_CUENTA
    })

    # Se borra ANTES de escribir, pero sólo estas cuentas: si el escenario
    # quedó sin membresías, el estadístico tiene que quedar sin ellas también.
    await db.execute(
        delete(StatisticalEntry).where(
            StatisticalEntry.scenario_id == scenario_id,
            StatisticalEntry.account_code.in_(CUENTAS),
        )
    )
    await db.flush()

    escritas = 0
    for mes, conceptos in sorted(por_mes.items()):
        for concepto, cantidad in conceptos.items():
            cuenta = CONCEPTO_A_CUENTA.get(concepto)
            if not cuenta:
                continue          # se informa en `sin_cuenta`, no se esconde
            db.add(StatisticalEntry(
                scenario_id=scenario_id, account_code=cuenta, month=mes,
                dept_code=DEPT_CLUB, value=cantidad, origen=ORIGEN,
            ))
            escritas += 1

        # El total incluye TAMBIÉN lo que no tiene cuenta: es el total que
        # muestra la pantalla, y las dos cifras tienen que ser la misma.
        db.add(StatisticalEntry(
            scenario_id=scenario_id, account_code=CUENTA_TOTAL, month=mes,
            dept_code=DEPT_CLUB, value=sum(conceptos.values(), Decimal("0")),
            origen=ORIGEN,
        ))
        escritas += 1

    return {
        "meses": sorted(por_mes),
        "valores_escritos": escritas,
        "sin_cuenta": sin_cuenta,
    }
