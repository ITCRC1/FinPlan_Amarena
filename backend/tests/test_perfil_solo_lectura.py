# -*- coding: utf-8 -*-
"""El perfil `viewer` ve todo y no escribe nada.

Owner, 2026-08-26: *«sería por perfil: editor, view»*.

Son pruebas **estructurales**: leen el código fuente en vez de levantar la app.
La razón es la misma que en las demás guardas del repo — lo que hay que blindar
no es «este endpoint contesta 403» sino **«la guarda sigue enganchada en la
única puerta»**. Una prueba de integración pasa igual el día que alguien monte
un router nuevo sin `_guard`; ésta no.
"""
import inspect

from fastapi import FastAPI

from app import main, perfiles
from app.models.user import ROLES


def test_viewer_es_un_rol_asignable():
    """Sin esto, crear el usuario devolvería 422 y el perfil no existiría."""
    assert "viewer" in ROLES
    assert "viewer" in perfiles.PERFILES_SIN_ESCRITURA


def test_la_guarda_esta_en_la_unica_puerta():
    """`solo_lectura` tiene que ir en `_guard`, no repartido por endpoint.

    Es la misma lección del candado del escenario: 197 `if` sueltos son 197
    oportunidades de olvidarse, y el olvido **deja escribir** en vez de fallar.
    """
    fuente = inspect.getsource(main)
    assert "Depends(solo_lectura)" in fuente, (
        "la guarda de sólo lectura salió de _guard: un `viewer` volvería a "
        "poder editar planilla, subir actuales y recalcular")


def test_todo_router_de_datos_lleva_la_guarda_completa():
    """Ningún router de datos puede montarse sin `_guard`.

    Se cuenta sobre el fuente y no sobre `app.routes` porque lo que importa es
    cómo se monta, no qué rutas quedaron: un `include_router` sin
    `dependencies=_guard` es exactamente el agujero que esto vigila.
    """
    fuente = inspect.getsource(main)
    sin_guarda = [
        ln.strip() for ln in fuente.splitlines()
        if ln.strip().startswith("app.include_router(")
        and "dependencies=_guard" not in ln
    ]
    # Los públicos a propósito: login, el consolidado (tiene su propia llave)
    # y los que declaran su guarda aparte.
    permitidos = ("auth_router", "consolidado_router")
    for ln in sin_guarda:
        assert any(p in ln for p in permitidos), (
            f"router montado sin _guard y no está en la lista de públicos: {ln}")


def test_no_frena_las_lecturas():
    """`GET` y `HEAD` nunca se bloquean: un lector tiene que poder leer."""
    assert "GET" not in perfiles.ESCRITURA
    assert "HEAD" not in perfiles.ESCRITURA
    assert perfiles.ESCRITURA == {"POST", "PUT", "PATCH", "DELETE"}


def test_las_preferencias_de_la_persona_quedan_fuera():
    """Idioma y paleta son del usuario, no del libro contable.

    Cuelgan de `auth_router`, que va sin `_guard`. Si algún día se mudaran a un
    router con guarda, un `viewer` no podría cambiar su propio idioma — y ésta
    es la prueba que lo diría.
    """
    fuente = inspect.getsource(main)
    linea = next(ln for ln in fuente.splitlines()
                 if "include_router(auth_router" in ln)
    assert "dependencies=_guard" not in linea


def test_el_403_dice_cual_es_el_perfil():
    """Un 403 pelado manda a leer logs. El mensaje nombra el perfil."""
    from app.errores import MENSAJES

    assert "auth.solo_lectura" in MENSAJES
    for idioma in ("es", "en"):
        assert "{perfil}" in MENSAJES["auth.solo_lectura"][idioma]


def test_el_admin_no_se_toco():
    """Agregar un perfil no puede ampliar quién administra.

    Misma regla que con `guillermo_approver`: un rol nuevo NO hereda los
    endpoints de administración por estar en la lista.
    """
    from app.auth import get_current_admin

    assert '!= "admin"' in inspect.getsource(get_current_admin)
