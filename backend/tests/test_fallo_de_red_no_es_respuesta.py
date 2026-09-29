# -*- coding: utf-8 -*-
"""Un fallo de RED no es una respuesta del servidor, y no se trata igual.

Owner, 2026-09-29, con el P&L de julio en pantalla: *«Failed to fetch»* en
rojo sobre una tabla que tenia datos, y el backend contestando 200 a todo. La
peticion nunca llego: es lo que le pasa a lo que este en vuelo mientras
Railway cambia el contenedor por un despliegue, y dura segundos.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
API = FRONT / "lib/api.ts"
PL = FRONT / "app/month-end/pl/page.tsx"


def test_una_lectura_que_no_llega_se_reintenta():
    """⚠️ `fetch` solo RECHAZA por red, CORS o abort. Un 500 no rechaza: llega
    como respuesta. Reintentar un 500 seria repetir el mismo error tres veces;
    reintentar lo que no llego es lo que hace invisible un despliegue."""
    src = API.read_text(encoding="utf-8")
    assert "const REINTENTOS_DE_RED" in src
    assert "function esFalloDeRed" in src
    assert "e instanceof TypeError" in src
    assert "if (!res.ok) {" in src, "se perdio el manejo de las respuestas de error"


def test_solo_se_reintentan_las_LECTURAS():
    """⚠️ Un POST o un PUT reintentado a ciegas puede guardar dos veces: no se
    sabe si el servidor lo recibio y se corto la respuesta, o si nunca lo vio.

    En esta app el guardado del cierre REEMPLAZA el mes entero, asi que un
    reintento a destiempo puede pisar lo que la primera llamada ya escribio.
    """
    src = API.read_text(encoding="utf-8")
    assert 'metodo === "GET" || metodo === "HEAD"' in src
    assert "esLectura && esFalloDeRed(e)" in src


def test_el_mensaje_dice_que_paso_y_no_Failed_to_fetch():
    """«Failed to fetch» no le dice nada a nadie."""
    src = API.read_text(encoding="utf-8")
    assert "No se pudo conectar con el servidor" in src
    assert "despliegue en curso" in src
    assert '"red.sin_conexion"' in src


def test_si_la_carga_falla_no_quedan_cifras_viejas_en_pantalla():
    """⚠️ El modo de falla que este proyecto persigue, con agravante.

    El error se pintaba arriba y la tabla se quedaba con la carga anterior:
    cambiar de julio a agosto y que fallara dejaba las cifras de JULIO bajo el
    encabezado de AGOSTO. Nadie mira el renglon rojo cuando la tabla de abajo
    tiene numeros que se ven bien, y aca eso invita a decidir sobre el mes
    equivocado.
    """
    src = PL.read_text(encoding="utf-8")
    i = src.index("} catch (e: unknown) {\n      // ⚠️ Se DESCARTA")
    bloque = src[i:i + 900]
    assert "setDatos([])" in bloque
    assert "setGastos([])" in bloque
    assert bloque.index("setDatos([])") < bloque.index("setError(")


def test_el_error_trae_con_que_reintentar():
    """Sin boton, la unica salida era recargar la pagina entera — y con ella el
    mes, las versiones y la vista que la persona ya habia elegido."""
    src = PL.read_text(encoding="utf-8")
    assert "onClick={() => cargar()}" in src
    assert "Reintentar" in src
