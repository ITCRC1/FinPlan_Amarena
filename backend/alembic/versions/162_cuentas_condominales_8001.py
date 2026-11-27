# -*- coding: utf-8 -*-
"""La 8001 «Cuotas Condominales» del 0250, agrupada en la línea RENT.

Owner, 2026-11-27: *«puedes crear la cuenta 8001 departamento 0250»* · *«esa que
agrupe en el P&L como Rent»* · *«sí, debe leerse Cuotas»*.

Cuenta nueva, sin movimiento en el mayor: nace para que contabilidad pueda
cargarla. Va **bajo el GOP**, en la misma línea que la 8000 (RENT), así que en
el P&L se verá sumada dentro de Renta y no como renglón propio.

⚠️ No confundir con la **7717 Cuotas Condominales** del Club (260), creada el
mismo día: esa es gasto operativo ARRIBA del GOP. Si alguna vez las dos
recibieran la misma cuota, estaría contada dos veces en dos niveles distintos
del estado de resultados.

Va junto con `app/seed_data/mapping_pl.json`, que es el que manda: sin esa fila
el seed borraría esta en el próximo despliegue (CLAUDE.md, «el SEED manda»).

Revision ID: 162
Revises: 161
"""
import sqlalchemy as sa
from alembic import op

revision = "162"
down_revision = "161"
branch_labels = None
depends_on = None

REPORT = "P&L_DETAIL_OWNERS"
DEPTO = "Departamento de Property Expenses"
DEPT_CODE = "0250"
CUENTA = "8001"
NOMBRE = "Cuotas Condominales"


def upgrade() -> None:
    # `id` es String(36) y la base NO le pone default: lo llena el seed desde
    # Python. Omitirlo tumbó el arranque entero en la 160.
    op.execute(sa.text("""
        INSERT INTO account_mapping (
            id, active_status, report_id, report_line_code, report_line_name,
            report_section, display_order, source_origin, source_department,
            account_code, account_name_example, financial_nature,
            rollup_operator, sign_rule, notes, dept_code)
        SELECT gen_random_uuid()::text, 'YES', :report, 'RENT', 'RENT',
               'OWNER / NON-OP EXPENSES', 86, 'Below GOP', :depto, :cuenta,
               :nombre, 'Expense', 'SUM',
               'Aggregate to line as positive display value; calculations '
               'subtract expense lines at subtotal level.',
               'Agregada 2026-11-27 (owner): agrupa en RENT, bajo GOP.',
               :dept_code
        WHERE NOT EXISTS (
            SELECT 1 FROM account_mapping
             WHERE report_id = :report AND dept_code = :dept_code
               AND account_code = :cuenta AND active_status = 'YES')
    """).bindparams(report=REPORT, depto=DEPTO, cuenta=CUENTA,
                    nombre=NOMBRE, dept_code=DEPT_CODE))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM account_mapping
         WHERE report_id = :report AND dept_code = :dept_code
           AND account_code = :cuenta
    """).bindparams(report=REPORT, dept_code=DEPT_CODE, cuenta=CUENTA))
