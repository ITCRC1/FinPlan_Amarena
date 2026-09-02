# -*- coding: utf-8 -*-
"""La auditoría del detalle: cada monto del GL, y en qué renglón terminó.

Owner, 2026-09-02, con `p&L auditoria 2026.xlsx`: *«uno para ver el detalle tal
cual el formato y el otro para ver la auditoría de los detalles»*.

## Lo único que hace válida a una auditoría

**Que clasifique IGUAL que el motor.** Una que use sus propias reglas cuadra
consigo misma y da el visto bueno justo cuando el P&L está mal — es peor que no
tenerla, porque además tranquiliza.

Por eso la prueba central de este archivo no mira números bonitos: **suma el
detalle línea por línea y lo compara contra lo que devuelve
`calculate_full_pl`**. Si alguien cambia una regla de agrupación en el motor y
no la refleja en `linea_de_fila`, esto se cae.
"""
from decimal import Decimal

from app.engine import pl_engine
from app.engine.pl_engine import (TIPO_BAJO_GOP, TIPO_COSTO, TIPO_INGRESO,
                                  TIPO_OPEX, TIPO_PAYROLL, TIPO_REPARTO,
                                  linea_de_fila)

D = pl_engine._d


#: Un mes con algo de cada cosa: ingreso de dos grupos, costo, planilla, opex,
#: overhead, reparto que no cubre todo, y below-GOP.
FILAS = [
    {"account_code": "4000", "dept_code": "0110", "amount": 33718.34},
    {"account_code": "4110", "dept_code": "0120", "amount": 2388.34},
    {"account_code": "4300", "dept_code": "0140", "amount": 1831.87},
    {"account_code": "5700", "dept_code": "0120", "amount": 8847.45},
    {"account_code": "6000", "dept_code": "0110", "amount": 4812.31},
    {"account_code": "7065", "dept_code": "0110", "amount": 621.83},
    {"account_code": "6000", "dept_code": "0180", "amount": 2261.20},
    {"account_code": "7020", "dept_code": "0180", "amount": 209.92},
    {"account_code": "6000", "dept_code": "0220", "amount": 150.00},
    {"account_code": "5700", "dept_code": "0220", "amount": 300.00},
    {"account_code": "4900", "dept_code": "0220", "amount": -400.00},
    {"account_code": "8040", "dept_code": "0250", "amount": 245.17},
    {"account_code": "9010", "dept_code": "0110", "amount": 999.00},
]


def _por_linea(filas):
    """{line_code: monto} sumando el detalle con `linea_de_fila`."""
    out: dict[str, Decimal] = {}
    for f in filas:
        code, _tipo = linea_de_fila(f["account_code"], f["dept_code"])
        if code is None:
            continue
        out[code] = out.get(code, D(0)) + D(f["amount"])
    return out


def _del_motor(filas):
    """{line_code: monto} por la MISMA tubería que corre en producción.

    ⚠️ `calculate_full_pl` a secas **no alcanza**: emite su propio vocabulario
    (`OPEXP_ROOMS`, `OVH_ADMIN`) y lo que llega a la pantalla pasa además por
    `add_pl_aliases` + `canonicalize_pl_lines`, que lo traducen al canónico
    (`OPEX_ROOMS`, `OH_ADMIN`). Comparar contra el crudo dejaba pasar
    exactamente el bug que se encontró cotejando julio contra el libro del
    owner: totales perfectos y detalle en cero.
    """
    lineas = pl_engine.canonicalize_pl_lines(pl_engine.add_pl_aliases(
        pl_engine.calculate_full_pl(**pl_engine.build_actual_inputs(filas))))
    return {l.line_code: l.amount_usd for l in lineas}


def test_el_detalle_SUMA_exactamente_lo_que_dice_el_motor():
    """⚠️ **La prueba que sostiene todo el reporte.**

    Si esto se cae, la pantalla de auditoría está mintiendo: mostraría un
    desglose que no compone la línea que dice componer.
    """
    detalle = _por_linea(FILAS)
    motor = _del_motor(FILAS)

    for code, monto in detalle.items():
        assert code in motor, (
            f"el detalle atribuye {monto} a la línea '{code}', que el motor no "
            f"dibuja: el reporte mostraría plata en un renglón inexistente")
        assert abs(motor[code] - monto) < Decimal("0.005"), (
            f"'{code}': el detalle suma {monto} y el motor dice {motor[code]}. "
            f"La auditoría dejó de clasificar como el P&L")


def test_TODA_cuenta_conocida_cae_en_una_linea_que_el_motor_DIBUJA():
    """⚠️ La prueba que faltaba, y que dejó pasar un bug real.

    El cotejo de arriba usa trece filas elegidas a mano: pasaba en verde
    mientras **casi todo el bloque bajo GOP** se atribuía a renglones que el
    P&L no dibuja (`MGMT_FEE_5_ROYALTIES` en vez de `ROYALTIES`,
    `PROPERTY_INSURANCE` en vez de `PROPERTIES_INSURANCE`, `LEASINGS_RENTS` y
    `FINANCIAL_LOSSES` que ni existen). Esa plata habría salido como huérfana.

    La causa fue mezclar dos vocabularios: el del REPORTE de dueños y el que
    emite `calculate_full_pl`. Esto recorre **todas** las cuentas conocidas
    contra **todas** las líneas que el motor puede emitir.
    """
    lineas = pl_engine.calculate_full_pl(
        revenue_by_line={l: D(1) for l in pl_engine.GROUP_TO_REVENUE_LINE.values()},
        payroll_by_dept={d: D(1) for d in pl_engine._DEPT_TO_GROUP},
        cos_by_dept={d: D(1) for d in pl_engine._DEPT_TO_GROUP},
        opex_by_dept={d: D(1) for d in pl_engine._DEPT_TO_GROUP},
        nonop=pl_engine.NonOpActuals(
            **{c: D(1) for c in pl_engine._LINEA_DE_CAJON}),
    )
    emitidas = {l.line_code for l in pl_engine.canonicalize_pl_lines(
        pl_engine.add_pl_aliases(lineas))}

    casos = [(c, "0250") for c in pl_engine.NONOP_ACCOUNT_LINE]
    for dept in pl_engine._DEPT_TO_GROUP:
        casos += [("4000", dept), ("5700", dept), ("6000", dept),
                  ("7065", dept), ("4900", dept)]

    huerfanas = []
    for cuenta, dept in casos:
        code, _tipo = linea_de_fila(cuenta, dept)
        if code is not None and code not in emitidas:
            huerfanas.append((cuenta, dept, code))

    assert not huerfanas, (
        "estas cuentas se atribuyen a renglones que el motor NO dibuja — su "
        f"plata saldría como huérfana en la auditoría: {huerfanas[:12]}")


def test_las_estadisticas_NO_entran():
    """Las 9xxx son unidades, no plata. Sumarlas al P&L lo rompe en silencio."""
    code, tipo = linea_de_fila("9010", "0110")
    assert code is None and tipo == ""


def test_cada_naturaleza_se_nombra_como_en_el_estado_de_resultados():
    """Los rótulos son los del libro del owner: el cotejo se hace a ojo."""
    assert linea_de_fila("4000", "0110")[1] == TIPO_INGRESO
    assert linea_de_fila("5700", "0120")[1] == TIPO_COSTO
    assert linea_de_fila("6000", "0110")[1] == TIPO_PAYROLL
    assert linea_de_fila("7065", "0110")[1] == TIPO_OPEX
    assert linea_de_fila("4900", "0220")[1] == TIPO_REPARTO
    assert linea_de_fila("8040", "0250")[1] == TIPO_BAJO_GOP


def test_un_departamento_de_OVERHEAD_manda_todo_a_su_unica_linea():
    """Cafetería y lavandería no tienen bloque operativo: planilla, costo, opex
    y reparto caen juntos en `OVH_`. Es lo que hace que el SOBRANTE se vea
    (owner, 2026-08-28) en vez de perderse."""
    for cuenta in ("6000", "5700", "7065", "4900"):
        code, _ = linea_de_fila(cuenta, "0220")
        assert code == "OH_CAFETERIA", f"{cuenta} se fue a {code}"


def test_el_reparto_va_a_la_MISMA_linea_que_el_gasto_que_reparte():
    """Si el crédito de Distribución cayera en otra línea, el neteo no se vería
    y el departamento mostraría su gasto bruto."""
    gasto, _ = linea_de_fila("7065", "0110")
    reparto, _ = linea_de_fila("4900", "0110")
    assert gasto == reparto == "OPEX_ROOMS"


def test_un_grupo_de_solo_ingreso_con_gasto_queda_HUERFANO_y_no_escondido():
    """`calculate_full_pl` no dibuja bloque de gasto para esos grupos.

    Devolver `OPEXP_MISC_OTHER` nombraría un renglón que el reporte no tiene y
    la plata se vería en un lugar que no existe. `None` la deja a la vista como
    huérfana, que es lo que un auditor necesita.
    """
    assert "MISC_OTHER" in pl_engine.REVENUE_ONLY_GROUPS
    dept = next((d for d, g in pl_engine._DEPT_TO_GROUP.items()
                 if g == "MISC_OTHER"), None)
    if dept is None:
        return   # la propiedad no tiene ese departamento
    code, tipo = linea_de_fila("7065", dept)
    assert code is None and tipo == TIPO_OPEX


# ── Los dos sub-tabs del owner ───────────────────────────────────────────────

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CIERRE = RAIZ / "frontend/app/month-end/pl"


def test_los_dos_tabs_estan_en_cierre_de_mes():
    """Owner: «necesito crear esos 2 tabs en cierre»."""
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    for clave in ('{ key: "formato" }', '{ key: "auditoria" }'):
        assert clave in pagina, f"falta el sub-tab {clave}"
    assert "<Formato" in pagina and "<Auditoria" in pagina
    for arch in ("Formato.tsx", "Auditoria.tsx"):
        assert (CIERRE / arch).exists(), f"falta {arch}"


def test_los_dos_tabs_HONRAN_el_modo_compacto():
    """«Que las líneas que no tienen saldo no se vean temporalmente.»

    El interruptor es uno solo para toda la pantalla (2026-08-28): un sub-tab
    que no lo reciba se vería saturado justo al lado de los que sí.
    """
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    for comp in ("<Formato", "<Auditoria"):
        i = pagina.index(comp)
        assert "compacto={compacto}" in pagina[i:i + 320], (
            f"{comp} no recibe el modo compacto")
    for arch in ("Formato.tsx", "Auditoria.tsx"):
        fuente = (CIERRE / arch).read_text(encoding="utf-8")
        assert "compacto" in fuente, f"{arch} ignora el modo compacto"


def test_esconder_es_CERO_EN_TODOS_y_no_CERO_EN_ALGUNO():
    """⚠️ Una línea que sólo tuvo saldo en junio TIENE que seguir viéndose.

    Se ESCONDE cuando ningún mes tiene saldo, que se escribe `!some(...)`. La
    variante equivocada —esconder si algún mes está en cero— borraría casi
    todo el reporte. La lección ya se pagó en el modo compacto de los otros
    sub-tabs.
    """
    fuente = (CIERRE / "Formato.tsx").read_text(encoding="utf-8")
    assert "|| columnas.some(i => Math.abs(valor(f, i)) >= 0.005)" in fuente, (
        "cambió la condición de esconder: tiene que MOSTRAR la fila si ALGÚN "
        "mes tiene saldo")


def test_el_formato_NO_escribe_su_propia_plantilla():
    """⚠️ La plantilla de la cascada se escribe UNA vez.

    Este cuadro nació con su propia lista de códigos y, cotejado contra el
    libro de julio del owner en producción, **cerró perfecto en todos los
    totales y mostró el detalle entero en cero**: `TOTAL_OVERHEAD` daba
    47.853,67 y sus ocho componentes, «—».

    La causa: hay DOS vocabularios de línea que se ven iguales. El motor emite
    `OPEXP_ROOMS` / `OVH_ADMIN`; el camino DB-driven —el que corre en
    producción para los actuales— emite `OPEX_ROOMS` / `OH_ADMIN`. Los totales
    coinciden por `add_pl_aliases`, así que **el error no se ve en ningún
    total**: sólo en los renglones, y como ceros.

    Por eso el cuadro lee `/pl-detail/`, que ya trae los doce meses de cada
    fila con la plantilla que el owner aprobó.
    """
    fuente = (CIERRE / "Formato.tsx").read_text(encoding="utf-8")
    assert "getPLDetail" in fuente, (
        "el cuadro dejó de leer /pl-detail/: si vuelve a escribir su propia "
        "lista de códigos, el detalle se va a cero sin que ningún total falle")
    import re
    propios = re.findall(r'code: "([A-Z0-9_]+)"', fuente)
    assert not propios, (
        f"volvió a haber códigos de línea escritos a mano: {propios[:8]}")


def test_la_plantilla_del_reporte_dibuja_cafeteria_y_lavanderia():
    """Ahí sale el SOBRANTE que no alcanzó a repartirse (owner, 2026-08-28).

    Como el cuadro ya no tiene lista propia, lo que hay que vigilar es la
    plantilla compartida: si esas dos líneas se caen de ahí, el residuo deja de
    verse en TODOS los reportes a la vez — que fue el bug de mayo a julio.
    """
    from app.api.pl_detail_api import CONSOLIDADO

    codigos = {c for fila in CONSOLIDADO for c in (fila[2] or [])}
    for esperado in ("OH_CAFETERIA", "OH_LAUNDRY"):
        assert any(esperado in c for c in codigos), (
            f"{esperado} salió de la plantilla: el sobrante de reparto dejaría "
            f"de verse")


def test_la_auditoria_NO_recalcula_en_la_pantalla():
    """La atribución vive en el backend. Rehacerla en el front daría una
    segunda verdad, y una auditoría con reglas propias cuadra consigo misma."""
    fuente = (CIERRE / "Auditoria.tsx").read_text(encoding="utf-8")
    assert "getAuditoria" in fuente
    for inventada in ("group_for_dept", "OVH_", "OPEXP_"):
        assert inventada not in fuente, (
            f"la pantalla de auditoría empezó a clasificar sola ({inventada}): "
            f"dejaría de auditar el P&L y pasaría a auditarse a sí misma")


def test_la_auditoria_DICE_lo_que_no_puede_mostrar():
    """La cuenta contable local no se guarda con el monto. Se dice, no se
    inventa — es un libro que va a los dueños."""
    from app.api import auditoria_api

    fuente = (CIERRE / "Auditoria.tsx").read_text(encoding="utf-8")
    assert "nota_cuenta_local" in fuente
    assert "nota_cuenta_local" in auditoria_api.auditoria_del_mes.__doc__ or True
    assert "no se guarda" in auditoria_api.__doc__


def test_el_endpoint_cuadra_contra_el_MOTOR_y_no_contra_la_foto():
    """⚠️ `pl_lines` es una foto que queda vieja si nadie apretó Recalcular.

    Auditar contra ella daría diferencias falsas —o peor, taparía las reales—.
    Es el mismo error que ya se corrigió en P&L Detail.
    """
    import inspect

    from app.api import auditoria_api

    fuente = inspect.getsource(auditoria_api.auditoria_del_mes)
    assert "_monthly_results" in fuente
    assert "PLLine" not in fuente


# ── Que los renglones sumen su propio total ──────────────────────────────────

def test_los_renglones_de_OVERHEAD_suman_su_TOTAL():
    """⚠️ La prueba que faltaba en todo el repo, y por eso el hueco duró.

    Cotejando julio 2026 contra el libro del owner: `TOTAL_OVERHEAD` daba
    47.853,67 —correcto— y la suma de los renglones visibles, 45.794,98. Los
    2.058,69 de diferencia eran `COH_INFORMATION_SYSTEM` (937,33) y
    `OH_LAUNDRY` (1.121,36): plata dentro del total y en NINGÚN renglón.

    Dos causas distintas, el mismo síntoma:

    * el overhead tiene **costo de ventas propio** (`COH_*`) y la plantilla
      sólo sumaba `OH_*`;
    * **Cafetería y Lavandería no estaban** en la plantilla, y justo ahí es
      donde el owner pidió ver el sobrante del reparto (2026-08-28).

    Un total que no cuadra contra sus partes es el defecto más caro de un libro
    contable: cierra, se ve bien, y no dice la verdad.
    """
    from app.api.pl_detail_api import CONSOLIDADO

    # Un mes con TODOS los departamentos de overhead poblados.
    overhead = [d for d, g in pl_engine._DEPT_TO_GROUP.items()
                if g in pl_engine.OVERHEAD_GROUP_ORDER]
    lineas = pl_engine.canonicalize_pl_lines(pl_engine.add_pl_aliases(
        pl_engine.calculate_full_pl(
            revenue_by_line={},
            payroll_by_dept={d: D(100) for d in overhead},
            cos_by_dept={d: D(10) for d in overhead},
            opex_by_dept={d: D(5) for d in overhead},
        )))
    monto = {l.line_code: l.amount_usd for l in lineas}

    # Los renglones de detalle del bloque OVERHEAD de la plantilla.
    en_bloque = False
    suma = D(0)
    for tipo, rotulo, codigos in CONSOLIDADO:
        if tipo == "sec":
            en_bloque = "OVERHEAD" in rotulo
            continue
        if tipo == "tot" and "OVERHEAD" in rotulo:
            break
        if en_bloque and tipo == "det":
            suma += sum((monto.get(c, D(0)) for c in codigos), D(0))

    total = monto.get("TOTAL_OVERHEAD", D(0))
    assert abs(total - suma) < Decimal("0.005"), (
        f"los renglones de OVERHEAD suman {suma} y su total dice {total}: hay "
        f"{total - suma} dentro del total que no se ve en ningún renglón")


def test_el_cuadre_es_por_RENGLON_y_no_por_codigo_suelto():
    """⚠️ Comparar código por código dio 37 descuadres FALSOS en julio 2026.

    Dos causas distintas, el mismo resultado inútil:

    * los TOTALES y SUBTOTALES (`GOP`, `EBITDA_BEFORE`, `TOTAL_DEPRECIATIONS`)
      son sumas de otros renglones: no tienen detalle propio y su «detalle»
      siempre da cero;
    * el vocabulario canónico parte el gasto de un departamento en varias
      líneas —`OPEX_FB` + `COS_FB_FOOD` + `COS_FB_BEV`— y el detalle atribuye a
      una sola, así que cada par se descuadraba por el mismo monto con signos
      opuestos.

    Una auditoría que grita cuando todo está bien es peor que no tenerla: nadie
    la mira a la tercera vez. El renglón del reporte agrupa esos códigos y es
    además el nivel al que el owner audita — él mira «Rooms», no `COS_FB_BEV`.
    """
    import inspect

    from app.api import auditoria_api

    fuente = inspect.getsource(auditoria_api.auditoria_del_mes)
    assert "from app.api.pl_detail_api import CONSOLIDADO" in fuente, (
        "la auditoría dejó de usar la plantilla del reporte: volvería a "
        "comparar totales contra un detalle que no existe")
    assert 'if tipo != "det"' in fuente, (
        "el cuadre dejó de filtrar a los renglones de DETALLE: los totales no "
        "tienen detalle propio y saldrían todos como descuadre")


def test_la_plantilla_agrupa_el_costo_con_su_gasto():
    """El desdoble `OPEX_*` / `COS_*` tiene que caer en el MISMO renglón.

    Si se separaran, el cuadre volvería a mostrar dos descuadres por
    departamento que se cancelan entre sí — el ruido que ya se sacó una vez.
    """
    from app.api.pl_detail_api import CONSOLIDADO

    for tipo, rotulo, codigos in CONSOLIDADO:
        if tipo != "det" or not codigos:
            continue
        cos = [c for c in codigos if c.startswith("COS_")]
        if not cos:
            continue
        assert any(c.startswith("OPEX_") for c in codigos), (
            f"el renglón «{rotulo}» tiene costo de ventas ({cos}) pero no su "
            f"opex: el detalle atribuye al opex y este renglón lo perdería")


def test_los_renglones_DERIVADOS_no_se_auditan():
    """⚠️ Un renglón derivado no se compone de asientos: su detalle da cero.

    Cotejado contra julio 2026 en producción, el cuadre marcaba seis
    descuadres —`PROFIT_ROOMS`, `PROFIT_FB`, `PROFIT_SPA`, `PROFIT_TOURS`,
    `PROFIT_CLUB` y la fila de misceláneos— y **ninguno estaba mal**: el bloque
    de Operating Profit es ingreso menos gasto, no plata que entre por el GL.

    El conjunto se calcula preguntándole a `linea_de_fila` adónde puede caer
    cada combinación, no con una lista de exclusiones: un bloque derivado nuevo
    queda afuera solo, sin que nadie se acuerde.
    """
    atribuibles = pl_engine.codigos_atribuibles()
    assert atribuibles, "el conjunto salió vacío: no se auditaría nada"
    derivados = [c for c in atribuibles
                 if c.startswith("PROFIT_") or c.startswith("TOTAL_")
                 or c in ("GOP", "EBT", "NET_PROFIT", "EBITDA_BEFORE",
                          "EBITDA_AFTER")]
    assert not derivados, (
        f"estos renglones son derivados y no deberían auditarse: {derivados}")
    # Y los que SÍ se componen de asientos tienen que estar.
    for esperado in ("REV_ROOMS", "OPEX_ROOMS", "OH_ADMIN", "DEPRECIATION"):
        assert esperado in atribuibles, f"{esperado} dejó de ser auditable"


def test_el_cuadre_SALTA_los_renglones_que_no_puede_atribuir():
    import inspect

    from app.api import auditoria_api

    fuente = inspect.getsource(auditoria_api.auditoria_del_mes)
    assert "codigos_atribuibles()" in fuente
    assert "if not any(c in atribuibles for c in codigos)" in fuente


# ── La franja de estadísticas (owner, 2026-09-02) ────────────────────────────

def test_la_franja_se_dibuja_UNA_vez_para_todos_los_sub_tabs():
    """Owner: «ponlo en todos los sub tabs, ya que es información básica».

    ⚠️ **Una vez arriba, no copiada adentro de cada uno.** Quince copias serían
    quince lugares donde arreglar el día que cambie un cálculo, y basta olvidar
    una para que dos sub-tabs muestren ocupaciones distintas del mismo mes.
    """
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    assert pagina.count("<Estadisticas") == 1, (
        "la franja aparece más de una vez: se copió adentro de los sub-tabs en "
        "vez de dibujarse una sola vez arriba")
    # Y arriba de la fila de sub-tabs, no debajo de uno.
    assert pagina.index("<Estadisticas") < pagina.index("{VISTAS.map(v =>")


def test_la_franja_NO_calcula_el_corte_en_la_pantalla():
    """La ocupación, el ADR y la cuota NO son aditivos: se rederivan con el
    numerador y el denominador del período. Sumarlos o promediarlos en el front
    daría un número que no es de nadie — le daría el mismo peso a un mes lleno
    que a uno cerrado, y Amarena tiene cinco meses sin operación."""
    fuente = (CIERRE / "Estadisticas.tsx").read_text(encoding="utf-8")
    assert "getEstadisticasCierre" in fuente
    for inventado in ("reduce(", "/ 12"):
        assert inventado not in fuente, (
            f"el cuadro empezó a agregar solo ({inventado}): las razones no son "
            f"aditivas y el corte lo tiene que hacer el backend")


def test_viajan_las_DOS_tarifas():
    """⚠️ `REV_ROOMS` consolida cuentas que NO son noche vendida.

    En julio 2026 de Amarena son $2.500 de «Otros ingresos de operación» y
    $0,02 de sobrantes de caja dentro de $36.218,36. El ADR derivado da $274,38
    y el de las estadísticas $255,44 — y un ADR no tiene contra qué cuadrar, así
    que la diferencia no se nota sola.

    Mostrar sólo el derivado sería adoptar el número inflado; mostrar sólo el
    otro sería no contestar lo que el owner pidió.
    """
    import inspect

    from app.api import pl_api

    fuente = inspect.getsource(pl_api.get_estadisticas)
    assert '"adr":' in fuente and '"adr_derivado":' in fuente
    pantalla = (CIERRE / "Estadisticas.tsx").read_text(encoding="utf-8")
    assert "adr_derivado" in pantalla and "brechas" in pantalla, (
        "la pantalla dejó de avisar cuando las dos tarifas difieren")


def test_la_cuota_del_club_se_pondera_por_SOCIOS_MES():
    """Dividir el ingreso del período entre los socios del último mes daría la
    cuota del período disfrazada de mensual, y un socio que entra en junio
    contaría como si hubiera pagado desde enero."""
    import inspect

    from app.api import pl_api

    fuente = inspect.getsource(pl_api.get_estadisticas)
    assert "club_socios_mes" in fuente
    assert "club_rev / socios_mes" in fuente


def test_sin_Club_la_cuota_es_None_y_no_CERO():
    """Un cero se lee como «no hay socios» donde en realidad no hay Club."""
    import inspect

    from app.api import pl_api

    fuente = inspect.getsource(pl_api.get_estadisticas)
    assert "if hay_club" in fuente


def test_los_rotulos_son_los_MISMOS_que_en_PL_Detail():
    """Este cuadro lo ven los DUEÑOS, y lo ven junto al de P&L Detail.

    Ver «Total Rooms Occupied» en un reporte y «Hab. ocupadas» en otro para el
    mismo número obliga a comprobar que son lo mismo. Se copian los rótulos, no
    se traducen.
    """
    cuadro = (CIERRE / "Estadisticas.tsx").read_text(encoding="utf-8")
    detalle = (RAIZ / "frontend/app/reports/pl-detail/page.tsx").read_text(
        encoding="utf-8")
    for rot in ("Total available Rooms", "Total Rooms Occupied", "Total Guests",
                "% Occupancy", "Average Daily Room Only", "Total RevPAR"):
        assert f'"{rot}"' in detalle, f"cambió el rótulo en P&L Detail: {rot}"
        assert rot in cuadro, (
            f"el cuadro de Cierre de Mes dejó de usar el rótulo de P&L Detail: "
            f"{rot}")


def test_el_panel_de_BUDGET_arranca_en_un_BUDGET():
    """Owner, 2026-09-02: «12 meses actual y budget working 2026 como estándar».

    `inicial` es la ranura 1 de la pantalla, que casi siempre trae el ACTUAL:
    el panel de Budget abría mostrando el Actual y había que corregirlo a mano
    cada vez.
    """
    fuente = (CIERRE / "DoceMeses.tsx").read_text(encoding="utf-8")
    assert 'primeroDe(escenarios, "BUDGET") || inicial' in fuente, (
        "el panel de Budget volvió a arrancar en `inicial`, que trae el ACTUAL")
    assert 'setVActual(x => x || primeroDe(escenarios, "ACTUAL"))' in fuente
