# -*- coding: utf-8 -*-
"""Borra la fila vieja de 7310/Tours para que el seed de mapeo vuelva a correr.

## El síntoma

Cada arranque del backend imprime:

    seed de mapeo omitido: duplicate key value violates unique constraint
    "uq_mapping_activo_depto_cuenta"

y sigue levantando. `app/seed.py` envuelve la siembra del mapeo en un
`try/except`, así que el despliegue se ve exitoso.

## Por qué se cae

`be34e1e` cambió el `source_origin` de una regla en
`app/seed_data/mapping_pl.json` y no borró la vieja de la base:

    report_id  P&L_DETAIL_OWNERS
    dept_code  0150 (Tours) · cuenta 7310 · línea OPEX_TOURS
    JSON       source_origin = 'Payroll'
    base       source_origin = 'Revenue'

El seed busca por `(report_id, source_department, account_code,
source_origin)`. Con el origen cambiado **no encuentra la fila**, así que la
INSERTA — y choca contra `uq_mapping_activo_depto_cuenta`, que es un índice
parcial sobre `(report_id, dept_code, account_code, vigente_desde,
vigente_hasta)` entre las filas `active_status='YES'`. Dos llaves distintas
sobre la misma fila: la del seed lleva `source_origin`, la del índice lleva
`dept_code`.

⚠️ **Y como el seed hace UN SOLO COMMIT, no entra ninguna de las 1.091
filas.** No es que falte una regla: es que el mapeo entero dejó de
re-afirmarse en cada despliegue desde entonces. Es exactamente lo que
`CLAUDE.md` describe —«el total sigue cuadrando: no hay error, no hay alerta,
y la plata cambia de línea sola»— y lo que `textos.py` manda hacer cuando el
log dice «seed de mapeo omitido»: arreglar la siembra, no la base.

## Qué hace esta migración

Borra **una** fila: la vieja, la de `source_origin='Revenue'`. Con eso el
seed inserta la del JSON en el próximo arranque y vuelve a correr completo.

⚠️ **La línea de destino NO cambia**: las dos reglas apuntan a `OPEX_TOURS`.
Lo que cambia es qué origen matchea la cuenta 7310 de Tours — que es
precisamente lo que `be34e1e` decidió y nunca llegó a producción.

Idempotente: si la fila vieja ya no está, no hace nada.
`downgrade` la repone tal cual estaba.

Revision ID: 140
Revises: 139
"""
import sqlalchemy as sa
from alembic import op

revision = "140"
down_revision = "139"
branch_labels = None
depends_on = None

REPORT = "P&L_DETAIL_OWNERS"
DEPTO = "Departamento de Tours"
DEPT_CODE = "0150"
CUENTA = "7310"
LINEA = "OPEX_TOURS"


def upgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM account_mapping
         WHERE report_id = :report
           AND dept_code = :dept_code
           AND account_code = :cuenta
           AND source_department = :depto
           AND source_origin = 'Revenue'
           AND active_status = 'YES'
    """).bindparams(report=REPORT, dept_code=DEPT_CODE, cuenta=CUENTA, depto=DEPTO))


def downgrade() -> None:
    # Se repone sólo si no está: volver a insertarla con la nueva ya presente
    # chocaría contra el mismo índice que originó todo esto.
    op.execute(sa.text("""
        INSERT INTO account_mapping
              (report_id, source_department, account_code, source_origin,
               dept_code, report_line_code, active_status)
        SELECT :report, :depto, :cuenta, 'Revenue', :dept_code, :linea, 'YES'
         WHERE NOT EXISTS (
               SELECT 1 FROM account_mapping
                WHERE report_id = :report AND dept_code = :dept_code
                  AND account_code = :cuenta AND source_origin = 'Revenue')
    """).bindparams(report=REPORT, depto=DEPTO, cuenta=CUENTA,
                    dept_code=DEPT_CODE, linea=LINEA))
