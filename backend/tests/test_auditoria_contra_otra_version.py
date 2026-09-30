# -*- coding: utf-8 -*-
"""La Auditoria, con una version al lado para comparar.

Owner, 2026-09-29: *«puedes poner a la par el budget o el forecast, la version
que yo quiera para que compare el actual. algunas solamente seran por cuenta
total. no pasa nada. pero al menos comparar contra algo»*.

## El hueco que llena

La auditoria decia de que esta hecho el mes pero no contra que medirlo. Un
renglon de $23.709 de Opex en Rooms no es alto ni bajo hasta que hay un
presupuesto al lado — y media pantalla estaba en blanco.

## Los tres casos del cruce

Corriendo la aritmetica real contra los tres casos, las diez comprobaciones
pasan y la columna de la otra version suma **exactamente su motor**:

    7400            coincide exacto            3.524,24 vs 3.000,00
    7105/Spa        B no tiene ese desglose    3.042,92 vs 5.000,00  (por total)
    7105/Rooms      ...y NO se vuelve a contar 1.000,00 vs vacio
    7999            B no la tiene                 55,00 vs vacio
    7250            B la tiene y A no                  0 vs   800,00  (solo en B)
                                               columna B = 8.800 = motor de B
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LOGICA = FRONT / "lib/auditoriaCompara.ts"
COMP = FRONT / "app/month-end/pl/Auditoria.tsx"
PAGINA = FRONT / "app/month-end/pl/page.tsx"


def test_existe_y_la_auditoria_lo_usa():
    assert LOGICA.exists()
    comp = COMP.read_text(encoding="utf-8")
    assert 'from "@/lib/auditoriaCompara"' in comp
    assert "compararDetalle(datos?.detalle ?? [], ix)" in comp


def test_el_total_de_la_cuenta_se_cuelga_de_UNA_sola_fila():
    """⚠️ El error que este cruce tendria si emparejara a lo bruto.

    Si el real trae tres outlets de la misma cuenta y el presupuesto la tiene
    sin desglosar, repetir el total en las tres filas lo contaria TRES veces —
    y la suma de la columna daria el triple sin que ninguna fila se viera rara.

    Medido: con 7105 en dos outlets y el presupuesto sin desglose, la columna
    da 8.800, que es exactamente el motor de la otra version.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "totalPuesto" in src
    assert "!totalPuesto.has(kc)" in src
    assert "porTotal" in src, "no se avisa que el monto vino del total"


def test_sin_contraparte_va_VACIO_y_no_en_cero():
    """Un cero dice «la otra version no tiene nada aca», que es una afirmacion
    distinta y muchas veces falsa: puede no tener ESE desglose, o puede que la
    fila de arriba ya se haya llevado el total de la cuenta."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "contra: number | null;" in src
    assert "f.contra === null ? null : f.monto - f.contra" in src
    comp = COMP.read_text(encoding="utf-8")
    assert 'f.contra === null ? "" : usd(f.contra)' in comp


def test_lo_que_solo_esta_del_otro_lado_TAMBIEN_se_ve():
    """Una partida presupuestada y sin ejecutar no deja rastro en el real, asi
    que sin esto la auditoria no la puede mostrar — y es justo la que interesa.
    Va en cero del lado de aca, que es el dato, y rotulada: en cero y sin marca
    se leeria como un movimiento de cero."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "soloContra" in src
    assert "if (vistas.has(kc)" in src
    comp = COMP.read_text(encoding="utf-8")
    assert "f.soloContra &&" in comp and "sólo en {rotuloB}" in comp


def test_las_opciones_del_catalogo_sin_usar_NO_se_comparan():
    """Son el inventario de cuentas disponibles, no un monto presupuestado.
    Compararlas meteria un cero donde no hay nada."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "if (!f.movimiento) continue;" in src


def test_el_cuadre_compara_MOTOR_contra_MOTOR():
    """⚠️ No el motor de una contra el detalle de la otra. El cuadre de la otra
    version es problema de la otra version, y mezclarlos haria que un descuadre
    de alla se leyera como una variacion de aca."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "ix.porLinea.set(f.linea, f.motor)" in src
    comp = COMP.read_text(encoding="utf-8")
    assert "ix!.porLinea.get(f.linea)" in comp
    assert "(f.motor ?? 0) - b!" in comp


def test_la_pantalla_y_el_EXCEL_comparan_contra_LA_MISMA_version():
    """⚠️ Si cada uno eligiera por su cuenta, el archivo podria estar comparando
    contra otra version que la pantalla de la que salio — y nada lo diria.

    Por eso la eleccion vive en la pagina y baja como prop.
    """
    comp = COMP.read_text(encoding="utf-8")
    assert "compara = \"\", onCompara" in comp
    assert "useState" not in comp.split("compara?: string;")[0].split(
        "export default function Auditoria")[-1], \
        "la version de al lado volvio a ser estado del sub-tab"
    pag = PAGINA.read_text(encoding="utf-8")
    assert "const [audContra, setAudContra] = useState" in pag
    assert "compara={audContra} onCompara={setAudContra}" in pag
    assert "audContra && audContra !== id" in pag


def test_el_EXCEL_usa_el_MISMO_cruce_que_la_pantalla():
    """Dos copias del cruce se separan en el primer arreglo, y la de la pantalla
    y la del archivo dirian cosas distintas de los mismos datos."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "compararDetalle(a.detalle, ix)" in pag
    assert "sumaContra(" in pag
    # Y el archivo dice contra que compara, en el subtitulo.
    assert "al lado: ${rotB}" in pag


def test_si_la_otra_version_falla_la_auditoria_SIGUE():
    """La auditoria sin comparacion sigue contestando la pregunta principal,
    que es si cuadra. Perder eso por un fallo de la comparacion seria cambiar
    lo importante por lo accesorio."""
    comp = COMP.read_text(encoding="utf-8")
    assert "catch { setDatosB(null); }" in comp
    pag = PAGINA.read_text(encoding="utf-8")
    assert "getAuditoria(audContra, mes, horizonte).catch(() => null)" in pag


def test_no_se_compara_una_version_contra_si_misma():
    """Daria una columna de diferencias en cero que parece una validacion y no
    valida nada."""
    comp = COMP.read_text(encoding="utf-8")
    assert "compara === scenarioId" in comp
    assert "escenarios.filter(e => e.id !== scenarioId)" in comp
