# -*- coding: utf-8 -*-
"""Los perfiles de la app, y el que sólo mira.

Owner, 2026-08-26: *«revisemos el tema del perfil y permisos de vistas por
usuarios; para mí sería por perfil: editor, view, y con vistas limitadas por
perfil»*.

## Qué había y qué falta

| perfil | qué es hoy |
|---|---|
| `admin` | el coordinador — además de todo, los 12 endpoints de administración |
| `collaborator` | **el «editor»** que el owner nombra: escribe todo menos administración |
| `guillermo_approver` | aprueba excepciones (§9.5); no es un nivel de acceso |
| `viewer` | **lo que faltaba**: entra, ve, y no escribe nada |

El «editor» ya existía con otro nombre. Lo que no existía era el que sólo mira:
medido contra el repo, **197 endpoints escriben y sólo 27 exigen admin**, así que
cualquiera con sesión podía editar planilla, subir actuales o recalcular.

## Por qué UNA dependencia y no 197 ediciones

Es el mismo mecanismo que el candado del escenario (`app/candado.py`) y que el
registro de subidas: se engancha una vez en `_guard`, y **una ruta nueva queda
cubierta sin que nadie se acuerde de nada**. Un `if user.role == "viewer"`
repartido en 197 endpoints es la variante que falla abierta: la que se olvide
deja escribir, y no falla ruidosamente — deja pasar.

⚠️ **No es middleware.** Igual que el candado: un middleware tendría que
resolver esto para toda petición y falla de golpe; una dependencia falla de a
una ruta y la atrapan las pruebas.

## Lo que NO frena, a propósito

**Las preferencias de la persona.** `/me/locale` y `/me/tema` cuelgan de
`auth_router`, que va fuera de `_guard`. Un lector tiene que poder cambiar su
idioma y su paleta: son de él, no del libro contable.

**Las descargas.** Bajar un Excel es `GET`. Un perfil que ve el reporte en
pantalla pero no lo puede exportar sería una restricción sin sentido — el dato
ya lo tiene delante.

## Y esto sí es un permiso

Distinto de `tab_enablement`, que **esconde de la barra pero deja responder la
ruta**. Acá la ruta contesta 403 aunque se escriba la URL a mano. Las dos capas
se complementan y no se reemplazan: una ordena la vista, la otra impide el
cambio.
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.auth import get_current_user
from app.errores import ErrorApi
from app.models.user import User

#: Los métodos que modifican. Misma lista que el candado del escenario, y por la
#: misma razón: `GET` y `HEAD` nunca se frenan.
ESCRITURA = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Quién no escribe. Es una lista y no `role == "viewer"` para que agregar un
#: perfil de sólo lectura mañana —un auditor externo, un banco— sea una línea.
PERFILES_SIN_ESCRITURA = frozenset({"viewer"})


async def solo_lectura(request: Request,
                       user: User = Depends(get_current_user)) -> None:
    """403 si un perfil de sólo lectura intenta modificar algo."""
    if request.method not in ESCRITURA:
        return
    if user.role in PERFILES_SIN_ESCRITURA:
        raise ErrorApi(403, "auth.solo_lectura", perfil=user.role)
