# -*- coding: utf-8 -*-
"""Configura el modelo de Cash Flow de Amarena. ESCRIBE en `cashflow_wc_params`.

Que hace
--------
Enciende el modelo de timing (`enabled = True`) y le carga los criterios a
TODOS los escenarios de AMA 2026 y 2027 que esten en estado `draft`.
Los escenarios `locked` se saltan - el candado existe por algo.

Es idempotente: se puede correr dos veces sin romper nada.

Como se corre
-------------
Desde la raiz del repo, con el CLI de Railway logueado:

    railway ssh --service "FinPlan_Amarena-Backend" -- bash -lc "cd /app && python -" \
        < backend/scripts/configurar_cashflow_amarena.py

Como se revierte
----------------
Las filas no existian antes. Para volver atras, misma invocacion con la
variable de entorno REVERTIR=1:

    railway ssh --service "FinPlan_Amarena-Backend" -- bash -lc "cd /app && REVERTIR=1 python -" \
        < backend/scripts/configurar_cashflow_amarena.py

De donde sale cada numero
-------------------------
mix_credit 0.19   Travel Agent / Promociones = 19.0% de la venta. Medido en
                  `actual_room_stat_canales` de Amarena. Paga a 30 dias.
mix_nrr    0.22   Direct Client es 43.9% de la venta y deja 50% de deposito al
                  reservar, 2 meses antes. 43.9% x 50% = 22%.
resto      0.59   El saldo de las directas (22%) mas todo OTA (37.1%), que
                  cobra en el mes de la estadia. Sale como residuo.

payroll_outsourced = False
                  Amarena paga su planilla directamente - 38 plazas, confirmado
                  por el owner el 2026-10-30. El default del sistema es True y
                  le cobraba 13% de IVA a los salarios: $60,980 inventados en
                  2027. Ojo: este mismo parametro esta mal en CWL.

El resto (tarjeta, retenciones, servicio A&B, IVA, proveedores, aguinaldo) se
toma igual que CWL porque es ley de Costa Rica y mecanica del sistema, identica
en las dos propiedades.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models.scenario import Scenario
from app.models.cashflow_wc_params import CashFlowWCParams

HOTEL = "AMA"
ANIOS = (2026, 2027)

PARAMS = {
    #  Cobranza: medida en los canales reales de Amarena 
    "mix_nrr": 0.22,          # deposito de reservas directas
    "lead_nrr": 2,            # ... 2 meses antes de la estadia
    "mix_flex": [0.0] * 12,   # sin tramo flexible: el saldo va al mes de estadia
    "lead_flex": 1,
    "mix_credit": 0.19,       # Travel Agent / Promociones
    "lag_credit": 1,          # ... a 30 dias
    "retention": 0.05,        # retencion sobre anticipos (cancelaciones)
    #  Tarjeta: tasas de ley 
    "card_pct": 0.70,
    "card_iva_ret": 0.025,
    "card_renta_ret": 0.025,
    #  Proveedores 
    "ap_same_pct": 0.60,      # 60% en el mes, 40% al siguiente
    #  Servicio 10% de A&B 
    "service_rate": 0.10,
    "service_lag": 1,
    #  IVA 
    "iva_rate": 0.13,
    #  La correccion 
    "payroll_outsourced": False,
    # aguinaldo_monthly NO se fija: el sistema lo deriva de la planilla real
    # (`_aguinaldo_de_planilla`), que es mejor que un monto escrito a mano.
    "aguinaldo_pay_month": 12,
}


def _fmt(tipo: str, version: str, anio: int) -> str:
    return "{:<8} {:<16} {}".format(tipo, version, anio)


def _estado(params: dict | None, enabled: bool | None) -> str:
    if params is None:
        return "SIN CONFIGURAR"
    return "enabled={}  nrr={}  credit={}  resto={:.2f}  planilla_propia={}".format(
        enabled, params.get("mix_nrr"), params.get("mix_credit"),
        1 - float(params.get("mix_nrr", 0)) - float(params.get("mix_credit", 0)),
        not params.get("payroll_outsourced", True))


async def _leer(s, filas):
    """Estado actual de cada escenario. Devuelve lista de (clave, texto)."""
    out = []
    for sid, tipo, version, anio, status in filas:
        w = (await s.execute(select(CashFlowWCParams).where(
            CashFlowWCParams.scenario_id == sid))).scalar_one_or_none()
        p = None
        if w is not None:
            p = w.params if isinstance(w.params, dict) else json.loads(w.params or "{}")
        out.append(("  {} [{:<6}]  {}".format(
            _fmt(tipo, version, anio), status, _estado(p, w.enabled if w else None))))
    return out


async def main() -> int:
    revertir = os.environ.get("REVERTIR") == "1"
    # DRY=1 recorre todo y NO confirma la transaccion: sirve para probar el
    # script sin tocar la base.
    dry = os.environ.get("DRY") == "1"

    async with SessionLocal() as s:
        escenarios = (await s.execute(
            select(Scenario)
            .where(Scenario.hotel_id == HOTEL, Scenario.year.in_(ANIOS))
            .order_by(Scenario.year, Scenario.type, Scenario.version)
        )).scalars().all()

        if not escenarios:
            print("No encontre escenarios de {} para {}.".format(HOTEL, ANIOS))
            return 1

        # Se guardan como valores sueltos ANTES de cualquier commit/rollback.
        # Tocar un atributo del ORM despues de confirmar dispara una recarga
        # perezosa que en async revienta con MissingGreenlet.
        filas = [(sc.id, sc.type, sc.version, sc.year, sc.status) for sc in escenarios]

        print("ANTES")
        print("-" * 86)
        for linea in await _leer(s, filas):
            print(linea)

        tocados: list[str] = []
        saltados: list[str] = []

        for sid, tipo, version, anio, status in filas:
            etiqueta = _fmt(tipo, version, anio)
            if status == "locked":
                saltados.append(etiqueta)
                continue
            w = (await s.execute(select(CashFlowWCParams).where(
                CashFlowWCParams.scenario_id == sid))).scalar_one_or_none()

            if revertir:
                if w is not None:
                    await s.delete(w)
                    tocados.append(etiqueta)
                continue

            if w is None:
                w = CashFlowWCParams(scenario_id=sid)
                s.add(w)
            w.enabled = True
            w.params = dict(PARAMS)
            tocados.append(etiqueta)

        if dry:
            await s.rollback()
        else:
            await s.commit()

        print()
        print("DESPUES")
        print("-" * 86)
        for linea in await _leer(s, filas):
            print(linea)

        print()
        if dry:
            print(">>> MODO PRUEBA (DRY=1): no se escribio nada.")
            print("    Habria tocado {} escenario(s):".format(len(tocados)))
        else:
            print("{}: {}".format("revertidos" if revertir else "configurados", len(tocados)))
        for x in tocados:
            print("   {} {}".format("-" if revertir else "+", x))
        if saltados:
            print("saltados por estar enllavados (el candado manda):")
            for x in saltados:
                print("   . " + x)
        if not revertir and not dry:
            print()
            print("Listo. Abri Cash Flow -> Metodo Directo y apreta Recalcular.")
            print("Falta UN dato que el script no puede inventar: el saldo de caja")
            print("inicial. Se carga en la pantalla del Cash Flow.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
