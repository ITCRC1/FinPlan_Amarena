# -*- coding: utf-8 -*-
"""Los checkbooks, para consultar sin entrar a Planning.

Owner, 2026-09-03: *«algunos usuarios no van a tener acceso a Planning por
obvias razones; necesito un sub-tab en Cierre mensual para poder generar los
checkbooks, la misma vista de Planning pero para visualizar qué hay a modo de
reportes: opex por departamento, salario por departamento, costo y gastos de
propietario»*.
"""
from pathlib import Path

FRONT = Path(__file__).resolve().parents[2] / "frontend"
CIERRE = FRONT / "app/month-end/pl"
VISTA = CIERRE / "Checkbooks.tsx"


def test_estan_los_CUATRO_libros_que_pidio():
    src = VISTA.read_text(encoding="utf-8")
    for clase in ("opex", "payroll", "cost", "property"):
        assert f'clase: "{clase}"' in src, f"falta el checkbook de {clase}"


def test_es_de_SOLO_LECTURA():
    """⚠️ Es la mitad del pedido: quien no debe tocar el presupuesto entra y ve
    lo mismo, sin forma de que un clic distraído cambie un número.

    Y no se resuelve escondiendo el botón de guardar: un formulario de sólo
    lectura sigue mandando lo que se escriba si alguien encuentra la ruta. Acá
    no hay un solo campo.
    """
    # ⚠️ Se mira el CÓDIGO y no el archivo entero: el comentario de arriba
    # explica por qué no hay campos que guarden, y buscar «guarda» a secas se
    # dispara con la explicación en vez de con el defecto.
    src = VISTA.read_text(encoding="utf-8")
    codigo = chr(10).join(l for l in src.splitlines()
                          if not l.lstrip().startswith(("*", "//", "/*")))
    for editable in ("<input", "<textarea", "contentEditable", "onBlur=",
                     "guardarComentario", "api.put", "api.post"):
        assert editable not in codigo, (
            f"la vista de consulta trae «{editable}»: dejó de ser de sólo "
            f"lectura")


def test_usa_el_MISMO_endpoint_que_el_desplegable_del_PL():
    """⚠️ Reusarlo no es ahorro: es lo que garantiza que lo que se ve acá SUMA
    exactamente la línea del reporte. Un endpoint propio sería una segunda
    aritmética, y el día que difiera no habría cómo saber cuál tiene razón."""
    src = VISTA.read_text(encoding="utf-8")
    assert "getDetalleDeCelda" in src


def test_dice_de_donde_sale_cada_version():
    """Un presupuesto no tiene mayor cargado; su detalle vive en el auxiliar.
    Mezclarlos sin decirlo sería peor que no mostrarlos."""
    src = VISTA.read_text(encoding="utf-8")
    assert "v.fuente" in src


def test_avisa_que_el_gasto_de_propiedad_NO_va_por_departamento():
    """Vive todo en el 0250 y se abre por cuenta. Sin el aviso, el selector de
    departamento parece roto cuando no cambia nada."""
    src = VISTA.read_text(encoding="utf-8")
    assert 'clase === "property" && dept' in src


def test_el_sub_tab_esta_registrado_y_tiene_ROTULO():
    import json
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    assert '{ key: "checkbooks" }' in pagina
    assert 'vista === "checkbooks"' in pagina
    for idioma in ("es", "en"):
        textos = json.loads((FRONT / f"messages/{idioma}.json").read_text(encoding="utf-8"))
        assert '"tab_checkbooks"' in json.dumps(textos), (
            f"sin rótulo en {idioma}: el sub-tab saldría como «tab_checkbooks»")


def test_baja_en_el_WORD_y_el_EXCEL_con_TODOS_los_departamentos():
    """⚠️ En el documento van los cuatro libros completos, no la selección que
    estaba puesta en la pantalla. Un reporte que sale distinto según el filtro
    del momento no se puede archivar: dos copias del mismo mes dirían cosas
    distintas."""
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    cuerpo = pagina[pagina.index("    checkbooks: async () => {"):]
    cuerpo = cuerpo[:cuerpo.index("    revenue: async ()")]
    assert 'getDetalleDeCelda(ids, clase, "")' in cuerpo
    assert cuerpo.count("[") > 0 and '"payroll", "Salarios"' in cuerpo


def test_los_cuatro_libros_son_SUB_TABS_de_segundo_nivel():
    """Owner, 2026-09-03: «puede ser que se ponga un sub tab CHECKBOOKS e
    internamente se pongan las 4 en sub tab del sub».

    ⚠️ Van con subrayado y no como los botones-pastilla de la fila de arriba:
    dos filas de pastillas idénticas se leen como UN solo nivel, y entonces
    «Opex» del checkbook parece hermano de «Opex x Depto», que es otro reporte.
    La forma tiene que decir cuál está adentro de cuál.
    """
    src = VISTA.read_text(encoding="utf-8")
    assert "2px solid var(--brand)" in src
    assert '2px solid transparent' in src
    # Y no el fondo lleno de la fila de arriba.
    assert 'background: clase === l.clase ? "var(--brand)"' not in src
