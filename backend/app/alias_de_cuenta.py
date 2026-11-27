# -*- coding: utf-8 -*-
"""El alias de una cuenta: cómo quiere el owner que se lea en los reportes.

Owner, 2026-11-27: *«quiero que sea editable un tipo ALIAS para poner como
quiero que salga en los reportes finales»* · *«hay cuentas que se repiten en
varios departamentos… si yo quisiera nombrar Cleaning Rooms o ponerle Cleaning
F&B y ninguno se ve afectado»* · *«deben vivir las dos, pero yo escoger el
alias»*.

## Qué resuelve

Una cuenta tiene hasta tres nombres y hasta hoy ganaba el que menos control
tiene el owner:

1. **el alias** — lo que se escribe acá;
2. **el nombre del mayor** — lo que contabilidad tipeó en Integrity;
3. **`account_name_example`** del mapeo.

Antes el orden era 2 → 3, así que editar el mapeo casi nunca cambiaba lo que
bajaba al reporte. Ahora el alias gana, y el nombre contable **no se borra**:
sigue en el mayor, y la pantalla lo muestra debajo. El día que alguien audite
contra Integrity, la cuenta sigue siendo la misma.

## Por qué vive en su propia tabla

`seed_mapping` re-afirma **campo por campo** todas las filas de
`account_mapping` desde `mapping_pl.json` en cada despliegue. Un alias guardado
ahí se borraría solo en el próximo deploy, sin error y sin alerta — el modo de
falla más caro del sistema (CLAUDE.md, «el SEED manda»). En tabla aparte el
seed no lo toca nunca.

## Por qué la resolución vive acá y no en cada reporte

Seis APIs distintas arman el nombre de una cuenta, cada una con su propia
precedencia. Enganchar el alias en una sola haría que el mismo dato se lea
distinto según la pantalla. `resolver()` es el único lugar donde se decide.
"""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.hotel_actual import HOTEL_ID

#: `(departamento, cuenta) → alias`. El departamento va en la llave porque la
#: misma cuenta vive en varios: la 7065 puede leerse «Cleaning Rooms» en
#: Habitaciones y «Cleaning F&B» en A&B sin que una toque a la otra.
Mapa = dict[tuple[str, str], str]


class AliasDeCuenta(Base):
    __tablename__ = "alias_de_cuenta"
    __table_args__ = (
        UniqueConstraint("hotel_id", "dept_code", "account_code",
                         name="uq_alias_depto_cuenta"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    hotel_id: Mapped[str] = mapped_column(String(10), default=lambda: HOTEL_ID)
    dept_code: Mapped[str] = mapped_column(String(10))
    account_code: Mapped[str] = mapped_column(String(20))
    alias: Mapped[str] = mapped_column(String(160))
    nota: Mapped[str] = mapped_column(String(300), default="")
    escrito_por: Mapped[str] = mapped_column(String(160), default="")
    escrito_el: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


def limpiar(texto: str | None) -> str:
    """El alias como se guarda: sin espacios de sobra y acotado a la columna."""
    return " ".join((texto or "").split())[:160]


async def mapa(session, hotel_id: str | None = None) -> Mapa:
    """Todos los alias de la propiedad, listos para `resolver()`.

    Una sola consulta: los reportes resuelven cientos de cuentas y no pueden
    ir a la base por cada una.
    """
    filas = (await session.execute(select(AliasDeCuenta).where(
        AliasDeCuenta.hotel_id == (hotel_id or HOTEL_ID)))).scalars().all()
    return {(f.dept_code or "", f.account_code): f.alias
            for f in filas if (f.alias or "").strip()}


def resolver(alias: Mapa, dept: str, cuenta: str,
             del_mayor: str | None = None,
             del_catalogo: str | None = None) -> str:
    """El nombre que se muestra, en el ÚNICO orden válido.

        alias → nombre del mayor → nombre del catálogo → el código

    ⚠️ Nunca devuelve vacío: una fila sin nombre en un reporte a dueños es
    peor que una con el código, porque no se puede rastrear.

    El alias se busca primero por `(departamento, cuenta)` y después por cuenta
    sola —con `dept=""`— para poder poner uno que valga en todos los
    departamentos sin repetirlo doce veces.
    """
    cuenta = str(cuenta or "")
    propio = alias.get((dept or "", cuenta)) or alias.get(("", cuenta))
    return (propio or (del_mayor or "").strip()
            or (del_catalogo or "").strip() or cuenta)
