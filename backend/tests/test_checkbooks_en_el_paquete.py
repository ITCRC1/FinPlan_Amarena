# -*- coding: utf-8 -*-
"""Los cuatro checkbooks entran al paquete del cierre, en tres cortes.

Owner, 2026-09-30: *«quiero agregar todos estos tabs al excel que bajo para el
resumen ejecutivo, con el mismo formato: opex mes, ytd y full year; salarios
mes, ytd y full year…»* y, aclarandolo: *«seria practicamente unir o hacer merge
de los excels ya que estan en el mismo formato»*.

Y eso es exactamente lo que se hizo: no hay un cuadro nuevo. Los checkbooks ya
sabian dibujarse en mes · YTD · full year (`cuadroCheckbookCortes`), asi que se
enganchan como capitulos mas del paquete y quedan a la par de los demas en
«Armar paquete» — con su casilla y sus flechas.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
PAGINA = FRONT / "app/month-end/pl/page.tsx"


def _src() -> str:
    return PAGINA.read_text(encoding="utf-8")


def test_los_cuatro_libros_son_capitulos():
    s = _src()
    assert "const EXTRAS = [" in s
    for clave, clase in (("cb_opex", "opex"), ("cb_payroll", "payroll"),
                         ("cb_cost", "cost"), ("cb_property", "property")):
        assert f'key: "{clave}"' in s and f'clase: "{clase}"' in s
    # Se registran como capitulos, no como un caso aparte del boton.
    assert "...Object.fromEntries(EXTRAS.map(e => [e.key, async () => {" in s


def test_es_un_MERGE_y_no_un_cuadro_nuevo():
    """⚠️ Owner: «seria practicamente unir o hacer merge de los excels ya que
    estan en el mismo formato». Escribir otro armado seria una segunda
    definicion del mismo cuadro: empiezan iguales y se separan en el primer
    arreglo que alguien hace de un lado — y entonces el checkbook suelto y el
    del paquete dirian cosas distintas de los mismos datos."""
    s = _src()
    assert "cuadroCheckbookCortes(" in s
    assert 'from "@/lib/checkbookCortes"' in s


def test_heredan_las_reglas_del_full_year():
    """La varianza es Forecast contra Budget, y la primera columna del año es el
    Forecast Current — no el Actual, que ahi repite el YTD. Vienen con el cuadro
    justamente por no haberlo reescrito."""
    s = _src()
    # ⚠️ Desde el 2026-09-30 el Forecast Current NO se resuelve aca: sale de
    # `actualFullPL`, el mismo memo que usan los tres P&L. Eran tres copias de
    # la misma regla en el mismo archivo, y el dia que una cambie el checkbook y
    # el P&L dirian años completos distintos sin que nada avise.
    assert "const actualFull = actualFullPL;" in s
    assert "escenarios.find(e => e.is_current_forecast)?.id" in s
    # ⚠️ Se comprueba campo por campo y no la llave entera: el objeto de
    # opciones crece —`notaDelPresupuesto` entro el 2026-09-30— y una prueba
    # que compara la llave literal se cae con cada campo nuevo sin que nada se
    # haya roto.
    assert "visibles, actualDelFullYear: actualFull," in s


def test_aparecen_en_ARMAR_PAQUETE_junto_a_los_demas():
    """Si no entraran en la lista del panel, bajarian siempre y no se podrian
    ordenar ni apagar — que es lo contrario de lo que se pidio hace dos
    mensajes."""
    s = _src()
    assert "const CLAVES_DEL_PAQUETE = () =>" in s
    assert "...EXTRAS.map(e => e.key)" in s
    assert "vistas={CLAVES_DEL_PAQUETE()}" in s
    assert "CLAVES_DEL_PAQUETE(), subOcultos," in s


def test_NO_pasan_por_tab_enablement():
    """⚠️ Esa matriz gobierna sub-tabs de esta pantalla, y estos no lo son: no
    tienen fila, asi que si se filtraran por ella nunca apareceria ninguno."""
    s = _src()
    i = s.index("const EXTRAS = [")
    assert "No pasan por `tab_enablement`" in s[max(0, i - 900):i]


def test_tienen_nombre_propio_en_el_panel():
    """No estan en el diccionario de traducciones —no son tabs—, asi que
    `t('tab_cb_opex')` devolveria la clave cruda y el panel mostraria
    «tab_cb_opex»."""
    s = _src()
    assert "const rotuloDelCapitulo = useCallback((k: string) => {" in s
    assert "rotulo={rotuloDelCapitulo}" in s
    assert "t(`tab_${k}`)" in s   # los sub-tabs siguen saliendo del diccionario


def test_un_libro_vacio_no_baja_como_hoja_en_cero():
    """Una hoja con una sola fila en cero se lee como «no hubo gasto», que es
    una afirmacion — y distinta de «este libro no tiene nada cargado»."""
    s = _src()
    assert "return c.filas.length > 1 ? [c] : [];" in s


def test_los_dos_cuadros_del_DASHBOARD_tambien_entran():
    """Owner, 2026-09-30: *«tambien quiero que incluyas estos 2 excels»* ·
    *«esta en dashboard»*: el Resumen consolidado del PMS y las Membresias del
    club.

    ⚠️ No arman nada nuevo. Los dos YA tenian su cuadro, porque cada uno baja su
    propio Excel desde el Dashboard; aca se enganchan los MISMOS. El del PMS
    estaba escrito adentro del componente y se movio a `lib/resumenConsolidado`
    justamente para poder reusarlo sin copiarlo.
    """
    s = _src()
    assert "const DEL_DASHBOARD = [" in s
    assert 'key: "pms"' in s and 'key: "membresias"' in s
    assert "cuadroResumenConsolidado(a)" in s
    assert "cuadroDelAnio(a)" in s
    # Y entran a la lista del panel, como todo lo demas.
    assert "...DEL_DASHBOARD.map(e => e.key)" in s


def test_el_cuadro_del_PMS_es_UNO_solo():
    """Lo bajan dos botones —el del Dashboard y el paquete—. Dos armados del
    mismo cuadro se separan en el primer arreglo que alguien hace de un lado."""
    front = pathlib.Path(__file__).resolve().parents[2] / "frontend"
    lib = (front / "lib/resumenConsolidado.ts").read_text(encoding="utf-8")
    assert "export function cuadroResumenConsolidado" in lib
    comp = (front / "components/ResumenConsolidado.tsx").read_text(encoding="utf-8")
    assert "cuadroResumenConsolidado(anio)" in comp
    # El componente ya no arma sus columnas a mano.
    assert 'label: "Total / Prom."' not in comp


def test_caen_al_ACTUAL_cuando_la_principal_no_tiene_el_dato():
    """⚠️ El conteo del PMS y las membresias se cargan en el ACTUAL, y el cierre
    suele mirarse contra el Budget. Sin el respaldo la hoja saldria vacia justo
    cuando el dato existe — y una hoja vacia se lee como «no hubo»."""
    s = _src()
    assert "const conRespaldo = useCallback(" in s
    assert 'e.type === "ACTUAL"' in s
    assert "for (const id of conRespaldo())" in s


def test_el_ARMADO_DE_INGRESOS_completa_el_consolidado():
    """Owner, 2026-09-30: *«ahora hagamos merge al archivo de resumen ejecutivo.
    agreguemos al final para tener ahora si un consolidado»*.

    Con esto el paquete del cierre queda con todo: la cascada en tres cortes por
    ambito, los cuatro checkbooks, los dos cuadros del Dashboard y las OCHO
    vistas del armado de ingresos — en UN archivo.
    """
    s = _src()
    assert 'key: "armado"' in s
    assert "cuadrosDelArmado({" in s
    assert "cargarFuentesIngresos(" in s
    # Va de ULTIMO, que es donde se pidio.
    i_armado = s.index('key: "armado"')
    i_pms = s.index('key: "pms"')
    assert i_armado > i_pms


def test_el_armado_NO_se_reescribe_para_el_paquete():
    """⚠️ Lo bajan dos lugares: el boton de Armado de ingresos y el paquete del
    cierre. Dos versiones del mismo cuadro empiezan iguales y se separan en el
    primer arreglo que alguien hace de un lado — y entonces el consolidado y el
    suelto dirian cosas distintas de los mismos datos."""
    front = pathlib.Path(__file__).resolve().parents[2] / "frontend"
    lib = front / "lib/revenuePlanPaquete.ts"
    assert lib.exists()
    src = lib.read_text(encoding="utf-8")
    assert "export function cuadrosDelArmado" in src
    assert "export const VISTAS_INGRESOS" in src
    # Las dos pantallas la usan.
    rp = (front / "app/month-end/revenue-plan/page.tsx").read_text(encoding="utf-8")
    assert "cuadrosDelArmado({" in rp
    assert 'from "@/lib/revenuePlanPaquete"' in rp


def test_el_armado_hereda_las_reglas_del_full_year():
    """La primera columna del año es el Forecast Current y la varianza es
    Forecast contra Budget. Vienen con el cuadro por no haberlo reescrito."""
    front = pathlib.Path(__file__).resolve().parents[2] / "frontend"
    src = (front / "lib/revenuePlanPaquete.ts").read_text(encoding="utf-8")
    # La regla ya no se escribe aca: sale de `vistaDe`, en el lib.
    assert "vistaDe(todas, a.visibles, a.actualDelFullYear, a.escenarios)" in src
    assert 'from "@/lib/tresCortes"' in src
    # Y la agregacion de cada vista sigue siendo la de su lib: aca no se suma
    # una razon por accidente.
    assert 'from "@/lib/revenuePlanCortes"' in src
    assert "totalDeIngresos(" in src and "valorDeIngresos(" in src
