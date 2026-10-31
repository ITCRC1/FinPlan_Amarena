# -*- coding: utf-8 -*-
"""Configura el modelo de Cash Flow de CUALQUIER propiedad. ESCRIBE en
`cashflow_wc_params`. Version generica del script de Amarena.

Uso
---
Se corre dentro del contenedor del backend de la propiedad. Variables:

    MEZCLA=medida   usa la mezcla de cobranza medida (nrr/credit explicitos)
    MEZCLA=default  NO escribe la mezcla: el sistema usa su perfil por defecto
                    (10% no reembolsable a 2 meses, flex por mes, 10% a credito).
                    Es lo correcto cuando la propiedad no tiene datos de canales.
    NRR=0.22        solo con MEZCLA=medida
    CREDIT=0.19     solo con MEZCLA=medida
    DRY=1           recorre todo y no escribe nada
    REVERTIR=1      borra las filas que este script crea

Que hace en TODOS los casos
---------------------------
  enabled = True                 prende el modelo de timing
  payroll_outsourced = False     la planilla propia NO lleva IVA ni va a A/P de
                                 proveedor. El default del sistema es True y le
                                 cobra 13% de IVA a los salarios.
  + la mecanica de Costa Rica: IVA 13%, tarjeta 70% con retenciones de 2.5% de
    IVA y 2.5% de renta, servicio de A&B 10% con rezago de un mes, proveedores
    60% en el mes, aguinaldo en diciembre, retencion de anticipos 5%.

Solo toca escenarios en estado 'draft'. Los 'locked' se saltan.
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

ANIOS = (2026, 2027)

# Mecanica de Costa Rica + la correccion de planilla. Igual en las cuatro.
BASE = {
    "retention": 0.05,
    "card_pct": 0.70,
    "card_iva_ret": 0.025,
    "card_renta_ret": 0.025,
    "ap_same_pct": 0.60,
    "service_rate": 0.10,
    "service_lag": 1,
    "iva_rate": 0.13,
    "payroll_outsourced": False,
    "aguinaldo_pay_month": 12,
}


def _params() -> tuple[dict, str]:
    p = dict(BASE)
    modo = os.environ.get("MEZCLA", "default")
    if modo == "medida":
        nrr = float(os.environ.get("NRR", "0.22"))
        credit = float(os.environ.get("CREDIT", "0.19"))
        if nrr + credit > 1.0:
            raise SystemExit("NRR + CREDIT no puede pasar de 1.0")
        p.update({"mix_nrr": nrr, "lead_nrr": 2, "mix_flex": [0.0] * 12,
                  "lead_flex": 1, "mix_credit": credit, "lag_credit": 1})
        nota = "mezcla MEDIDA: {:.0%} a 2 meses, {:.0%} en el mes, {:.0%} a 30 dias".format(
            nrr, 1 - nrr - credit, credit)
    else:
        nota = "mezcla POR DEFECTO del sistema (la propiedad no tiene datos de canales)"
    return p, nota


def _fmt(tipo: str, version: str, anio: int) -> str:
    return "{:<9} {:<16} {}".format(tipo, version, anio)


def _estado(params: dict | None, enabled) -> str:
    if params is None:
        return "SIN CONFIGURAR"
    mezcla = ("nrr={} credit={}".format(params.get("mix_nrr"), params.get("mix_credit"))
              if "mix_nrr" in params else "mezcla por defecto")
    return "enabled={}  {}  planilla_propia={}".format(
        enabled, mezcla, not params.get("payroll_outsourced", True))


async def _leer(s, filas):
    out = []
    for sid, tipo, version, anio, status in filas:
        w = (await s.execute(select(CashFlowWCParams).where(
            CashFlowWCParams.scenario_id == sid))).scalar_one_or_none()
        p = None
        if w is not None:
            p = w.params if isinstance(w.params, dict) else json.loads(w.params or "{}")
        out.append("  {} [{:<6}]  {}".format(
            _fmt(tipo, version, anio), status, _estado(p, w.enabled if w else None)))
    return out


async def main() -> int:
    revertir = os.environ.get("REVERTIR") == "1"
    dry = os.environ.get("DRY") == "1"
    params, nota = _params()

    async with SessionLocal() as s:
        hoteles = [r[0] for r in (await s.execute(
            select(Scenario.hotel_id).distinct())).all()]
        print("propiedad en esta base: {}".format(hoteles))
        print("criterio: {}".format(nota))
        print()

        escenarios = (await s.execute(
            select(Scenario).where(Scenario.year.in_(ANIOS))
            .order_by(Scenario.year, Scenario.type, Scenario.version)
        )).scalars().all()
        if not escenarios:
            print("No hay escenarios {} en esta base.".format(ANIOS))
            return 1

        # Valores sueltos ANTES del commit: tocar el ORM despues dispara una
        # recarga perezosa que en async revienta con MissingGreenlet.
        filas = [(sc.id, sc.type, sc.version, sc.year, sc.status) for sc in escenarios]

        print("ANTES")
        print("-" * 92)
        for l in await _leer(s, filas):
            print(l)

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
            w.params = dict(params)
            tocados.append(etiqueta)

        if dry:
            await s.rollback()
        else:
            await s.commit()

        print()
        print("DESPUES")
        print("-" * 92)
        for l in await _leer(s, filas):
            print(l)

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
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
