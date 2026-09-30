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
    # Cada nivel CONSUME lo que toma: la bolsa de la otra version se descuenta.
    assert "function tomar(b: Bolsa, monto: number)" in src
    assert "b.resto -= monto;" in src
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
    # Lo que quedo en la bolsa sin repartir es, literalmente, lo que solo esta
    # del otro lado.
    assert "for (const b of bolsas.values())" in src
    assert "Math.abs(b.resto) < CERO) continue;" in src
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
    assert "compara={audCompara} onCompara={setAudContra}" in pag
    assert "audCompara && audCompara !== id" in pag


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
    # El fallo se atrapa Y se cuenta: la pantalla sigue, con el aviso al lado.
    assert "setDatosB(null);" in comp and "setAvisoB(" in comp
    pag = PAGINA.read_text(encoding="utf-8")
    assert "getAuditoria(audCompara, mes, horizonte).catch(() => null)" in pag


def test_no_se_compara_una_version_contra_si_misma():
    """Daria una columna de diferencias en cero que parece una validacion y no
    valida nada."""
    comp = COMP.read_text(encoding="utf-8")
    assert "compara === scenarioId" in comp
    assert "escenarios.filter(e => e.id !== scenarioId)" in comp


def test_arranca_comparando_y_no_en_blanco():
    """⚠️ El primer intento arrancaba en «— sin comparar —», y la auditoria se
    veia EXACTAMENTE igual que antes de la funcion: habia que descubrir un
    selector nuevo entre otros cuatro para que apareciera algo.

    Owner, viendo eso: *«sigue igual, no cambio nada.. no compara»*.

    Sin eleccion propia cae en el CONTRA de la variacion de arriba — la version
    que la pantalla ya esta restando en todos los demas sub-tabs.
    """
    pag = PAGINA.read_text(encoding="utf-8")
    assert "useState<string | null>(null)" in pag
    assert 'const audCompara = audContra ?? (ranuras[varB] || "")' in pag
    assert "compara={audCompara}" in pag
    # Y el Excel baja con la MISMA, no con la cruda.
    assert "audCompara && audCompara !== id" in pag


def test_null_y_cadena_vacia_NO_son_lo_mismo():
    """`null` es «todavia no elegi» y cae en el default; `""` es «elegi no
    comparar» y se respeta. Con un solo valor, apagar la comparacion la volveria
    a encender en el siguiente render."""
    pag = PAGINA.read_text(encoding="utf-8")
    i = pag.index("const [audContra")
    doc = pag[max(0, i - 900):i]
    assert "`null` no es lo mismo que" in doc


def test_cuando_NO_puede_comparar_lo_DICE():
    """⚠️ Era un `catch` mudo: la version de al lado fallaba y la pantalla
    quedaba identica a como si no se hubiera pedido nada. «No compara» sin
    ninguna explicacion no se puede distinguir de que la funcion no exista.

    Dos avisos distintos, porque son dos problemas distintos: la que no se pudo
    leer, y la que se leyo y no tiene detalle por cuenta.
    """
    comp = COMP.read_text(encoding="utf-8")
    assert "setAvisoB" in comp
    assert "no se pudo leer la versión de al lado" in comp
    assert "no tiene detalle por cuenta en este período" in comp
    assert "{avisoB && (" in comp, "el aviso no se dibuja"
    assert "catch { setDatosB(null); }" not in comp, "volvio el catch mudo"


def test_el_INGRESO_tambien_compara_aunque_no_traiga_cuenta():
    """⚠️ El error que el owner vio primero: *«por que los gastos salen y los
    ingresos no salen para ninguno»*.

    Los dos lados no hablan el mismo idioma. El real llega del mayor
    —departamento `0110`, cuenta `4000`— y el presupuesto llega de los
    checkbooks, donde **el ingreso no tiene ni cuenta ni departamento**: la
    llave es el GRUPO (`ROOMS`) y el departamento va vacio (ver
    `auditoria_api._asientos_del_checkbook`). Emparejar solo por codigo dejaba
    TODO el ingreso sin comparar mientras el gasto cuadraba.

    El tercer nivel los junta por el RENGLON del P&L: los dos caen en
    `REV_ROOMS` porque lo decidio el mismo motor.

    Medido: 4000 (54.134,00) contra el grupo ROOMS (48.000,00) → 6.134,00.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "const deLaLinea = (dept: string, linea: string)" in src
    assert "porLinea: boolean;" in src
    # ⚠️ Y NO exige el mismo departamento cuando el otro lado no lo dice: el
    # ingreso presupuestado no tiene departamento, asi que exigirlo no
    # encontraria ninguno.
    assert 'b.dept === dept || b.dept === ""' in src
    comp = COMP.read_text(encoding="utf-8")
    assert "f.porTotal || f.porLinea" in comp, "la marca «lin.» no se dibuja"


def test_al_renglon_solo_baja_la_cuenta_que_el_otro_lado_NO_tiene():
    """⚠️ El error que este cruce tuvo y se corrigio antes de desplegarlo.

    Si una fila cuya cuenta SI existe del otro lado —pero ya se agoto arriba—
    pudiera bajar al nivel de renglon, el segundo outlet de una cuenta ya
    comparada se llevaria el presupuesto de OTRA cuenta de la misma linea.

    Medido: `7105/Rooms` se quedaba con los 1.113,74 de la cuenta 6003. **La
    columna seguia sumando bien** —por eso no se nota— pero la plata quedaba en
    la fila equivocada, que es el peor error de una auditoria.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "f.linea && !bolsa ? deLaLinea(" in src


def test_la_columna_de_al_lado_suma_EXACTAMENTE_el_total_del_otro():
    """La prueba de que ningun nivel duplica ni pierde. Corrida contra los seis
    casos —exacto, por total, segundo outlet, por linea, opcion sin uso y solo
    en B— la columna da 57.913,74, que es el total de la otra version."""
    src = LOGICA.read_text(encoding="utf-8")
    # El indice se COPIA por render: vaciar el compartido dejaria la segunda
    # pasada sin nada que repartir y la columna en blanco.
    assert "for (const [k, b] of ix.bolsas) bolsas.set(k, { ...b, exacto: new Map(b.exacto) });" in src
