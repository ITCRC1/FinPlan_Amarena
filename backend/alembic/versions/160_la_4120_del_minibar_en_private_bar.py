# -*- coding: utf-8 -*-
"""La 4120 del minibar entra por Private Bar (0121), no por A&B.

## Qué pasaba

El mayor trae `0121 | 4120 – Ingresos Venta del MINIBAR` ($69,99) y el mapeo
rebotaba la fila con «NO EXISTE»: la 4120 estaba declarada **solo** en `0120
Departamento de A&B` (línea `REV_FB_BEV`). El departamento existía y la cuenta
existía; lo que no existía era **el par**.

Owner, 2026-11-25: *«pero 0120 es Food and Beverage, realmente debe quedar como
Private Bar»*. Codificarlo en A&B habría entrado sin rebotar, pero el minibar
habría quedado sumado dentro de bebidas del restaurante.

## Qué hace

Agrega UNA fila: `0121 + 4120 → REV_PRIVATE_BAR`. Nada más. No se tocan las
cuentas de tienda que Private Bar ya lleva —son decisión del owner del
2026-08-12, «el Private Bar lleva las MISMAS cuentas que el Gift Shop»— ni la
4120 de A&B, que sigue igual.

⚠️ **La misma cuenta en dos departamentos son dos filas, y eso es legal**: la
llave del seed es `report_id + source_department + account_code + source_origin`
y el índice activo es `report_id + dept_code + account_code`. `0120|4120` y
`0121|4120` no chocan en ninguno de los dos.

Va junto con la fila nueva en `app/seed_data/mapping_pl.json`: sin eso, el seed
la borraría de vuelta en el próximo despliegue (ver CLAUDE.md, «el SEED manda»).

Revision ID: 160
Revises: 159
"""
import sqlalchemy as sa
from alembic import op

revision = "160"
down_revision = "159"
branch_labels = None
depends_on = None

REPORT = "P&L_DETAIL_OWNERS"
DEPTO = "Departamento Private Bar"
DEPT_CODE = "0121"
CUENTA = "4120"
LINEA = "REV_PRIVATE_BAR"


def upgrade() -> None:
    # El seed vuelve a afirmarla en cada arranque; esto es solo para que la base
    # de hoy ya la tenga y el mayor deje de rebotar sin esperar al despliegue.
    op.execute(sa.text("""
        INSERT INTO account_mapping (
            active_status, report_id, report_line_code, report_line_name,
            report_section, display_order, source_origin, source_department,
            account_code, account_name_example, financial_nature,
            rollup_operator, sign_rule, notes, dept_code)
        SELECT 'YES', :report, :linea, 'Private Bar', 'REVENUES', 21, 'Revenue',
               :depto, :cuenta, 'NA Beverage · minibar de la habitación',
               'Revenue', 'SUM',
               'Aggregate to line as positive display value; calculations '
               'subtract expense lines at subtotal level.',
               'El minibar se codifica 0121+4120 en el mayor. La 4120 también '
               'existe en 0120 (A&B): son dos filas distintas porque la llave '
               'del mapeo lleva el departamento.',
               :dept_code
        WHERE NOT EXISTS (
            SELECT 1 FROM account_mapping
             WHERE report_id = :report AND dept_code = :dept_code
               AND account_code = :cuenta AND active_status = 'YES')
    """).bindparams(report=REPORT, linea=LINEA, depto=DEPTO,
                    cuenta=CUENTA, dept_code=DEPT_CODE))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM account_mapping
         WHERE report_id = :report AND dept_code = :dept_code
           AND account_code = :cuenta AND source_department = :depto
    """).bindparams(report=REPORT, dept_code=DEPT_CODE, cuenta=CUENTA, depto=DEPTO))
