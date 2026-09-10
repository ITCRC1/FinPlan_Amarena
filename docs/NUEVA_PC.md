# Montar FinPlan en una PC nueva

Owner, 2026-09-10: *«me compré una computadora nueva… ¿qué debo llevar de acá
para allá para que la compu conozca, instale, logre autorización, para que pueda
trabajar con un click?»*.

Esta guía es para la máquina **nueva**. Todo lo que dice está verificado contra
la PC vieja el 2026-09-10, no supuesto.

---

## Lo primero: casi nada hay que llevar

Desde el **2026-09-09** los cuatro repos están completos en GitHub. Antes de esa
fecha había 63 commits que vivían en un solo disco y había que copiar carpetas;
ahora no. La máquina nueva **clona**.

Lo que sí viaja a mano son cinco cosas, y sólo dos son secretos:

| Qué | Dónde está en la PC vieja | Por qué no se puede clonar |
|---|---|---|
| `.env` de Amarena | `C:\dev\FinPlan_Amarena\backend\.env` | trae `SECRET_KEY` |
| `.env` de CWL | `C:\dev\FinPlan_CWL\backend\.env` | trae `SECRET_KEY` |
| Clave SSH *(opcional)* | `%USERPROFILE%\.ssh\id_ed25519` y `.pub` | se puede generar una nueva |
| Memoria de Claude | `C:\Users\<vos>\.claude\projects\C--dev-Ventanas\memory\` | son 33 notas de contexto |
| Este documento | ya está en GitHub, dentro de FinPlan_Amarena | — |

Oxygen y Ojochal **no tienen `.env` local**: no hace falta llevarles nada.

### ⚠️ Lo que NO hay que llevar

**La credencial de GitHub guardada en Windows.** En la PC vieja quedó
almacenada la cuenta `Bismark1973`, que tiene permiso en Amarena y **no** en los
otros tres repos. Eso produjo un día entero de errores 403 el 2026-09-09: los
commits salían firmados como `ITCRC1` —el dueño— pero se enviaban con otra
cuenta, y GitHub los rechazaba.

En la máquina nueva se empieza limpio y se inicia sesión como **ITCRC1**. Es la
oportunidad de que el problema no se herede.

---

## El camino de un solo comando

1. Instalar **Git** (si la PC no lo trae): <https://git-scm.com/download/win>

2. Abrir PowerShell y clonar el repo de referencia:

   ```powershell
   mkdir C:\dev; cd C:\dev
   git clone https://github.com/ITCRC1/FinPlan_Amarena.git
   ```

3. Correr el guion, que hace todo lo demás:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass -Force
   .\FinPlan_Amarena\docs\NUEVA_PC.ps1
   ```

   Instala las herramientas, clona los otros tres repos, arma los cuatro
   entornos de Python y los cuatro de Node, y al final imprime lo único que no
   puede hacer solo.

---

## Las tres autorizaciones que sólo podés dar vos

Ningún guion puede iniciar sesión por vos. Son tres, y toman un minuto cada una.

### 1 · GitHub

La primera vez que hagas `git push`, Windows abre el navegador.

> ⚠️ Entrá con **ITCRC1** (`Finance@thecostaricacollection.com`). Verificá arriba
> a la derecha que diga ese nombre antes de autorizar.

Comprobalo sin subir nada:

```powershell
cd C:\dev\FinPlan_Oxygen
git push --dry-run origin HEAD
```

Si responde con algo tipo `abc123..def456  HEAD -> main`, quedó bien. Si dice
`403`, la sesión quedó con la cuenta equivocada.

### 2 · Railway

```powershell
railway login
```

Abre el navegador una sola vez. La cuenta es `brodriguez7301@gmail.com`.

### 3 · Clave SSH

Hace falta **sólo** para entrar a las bases de producción (`railway ssh`), que es
como se leen y corrigen datos sin contraseñas. Todo lo demás funciona sin ella.

Recomendado — generar una nueva en la PC nueva:

```powershell
ssh-keygen -t ed25519 -C "pc-nueva"
type $env:USERPROFILE\.ssh\id_ed25519.pub
```

y pegar esa línea en Railway → **Account Settings → SSH Keys**.

La alternativa es copiar la de la PC vieja (allá está registrada como
`ventanas-pc-claude`). Generar una nueva es más limpio: si algún día se pierde
una máquina, se revoca sólo su llave.

---

## Lo que hace que baste *una sola instrucción*

Esta es la parte que no es obvia. La máquina nueva puede tener todo instalado y
aun así no saber trabajar en esto, porque **el conocimiento del sistema no está
en el código**: está en dos lugares.

**1 · Los `CLAUDE.md` de cada repo.** Vienen con el clon. Traen las
convenciones, las reglas de negocio y las trampas conocidas.

**2 · La memoria de Claude.** No está en Git. Son 33 notas con lo aprendido a
los golpes:

- los nombres exactos de los servicios de Railway en cada propiedad (`FinPlan_Oxygen Backend` lleva espacio, `FinPlan_Gardens_Backend` lleva guión bajo);
- que el front de Oxygen se sube desde la **raíz** del repo y el de Ojochal desde `frontend/` — y que no hay regla por propiedad, es por servicio;
- que `recalculate_scenario` hace su propio `commit`, así que **una corrida «en seco» que recalcula ya escribió**;
- el descarte silencioso del mapeo, que mueve plata de departamento sin que ningún total cambie;
- que `orden_plantilla.json` es idéntico en las cuatro propiedades, así que **no dice qué opera cada hotel**.

Copiala entera:

```
C:\Users\<vos>\.claude\projects\C--dev-Ventanas\memory\
```

Sin eso, la máquina nueva sabe programar pero no conoce *este* sistema, y vas a
tener que volver a explicar cada trampa.

---

## «Antes ejecutabas sin problemas y ahora no puedo»

Owner, 2026-09-10, desde la máquina nueva. No es que se haya perdido acceso: la
PC vieja tenía cuatro cosas que una máquina recién comprada no trae, y **tres no
dan error** — simplemente hacen que nada se ofrezca.

**1 · Las carpetas que Claude tiene permitidas.** Claude Code sólo puede tocar
los directorios que se le abrieron. Si lo abrís parado en otra carpeta, no
alcanza `C:\dev\FinPlan_*`: no es que no quiera, es que no los ve. En la PC
vieja la sesión tenía habilitado `C:\dev\FinPlan_Amarena` **además** del
proyecto principal, y por eso podía saltar de una propiedad a otra.
→ Abrí Claude parado en `C:\dev`, o agregale las carpetas de los cuatro FinPlan.

**2 · El modo de permisos.** Por omisión pide aprobación comando por comando.
Las corridas largas de la PC vieja iban con permisos amplios, y por eso podía
decir *«¿lo aplico en los otros tres?»* y hacerlo de corrido.
→ Si querés ese ritmo, hay que habilitarlo en la máquina nueva.

**3 · La memoria.** Sin las 33 notas, Claude no sabe que existen las otras tres
propiedades, ni cómo se llaman sus servicios en Railway, ni desde qué carpeta
sube cada una. Por eso **deja de ofrecer** replicar los cambios: no sabe a dónde.

**4 · Las herramientas y las sesiones.** Railway CLI, la clave SSH, los venv.
Éstas sí dan error, y son las fáciles.

Para saber cuál de las cuatro te está frenando, corré en la PC nueva:

```powershell
.\FinPlan_Amarena\docs\DIAGNOSTICO_PC.ps1
```

No instala ni cambia nada: sólo mide y te dice qué falta, punto por punto.

---

## Comprobación final

Las cuatro suites tienen que dar verde:

```powershell
cd C:\dev\FinPlan_Amarena\backend; .\.venv\Scripts\python.exe -m pytest -q
cd C:\dev\FinPlan_Oxygen\backend;  .\.venv\Scripts\python.exe -m pytest -q
cd C:\dev\FinPlan_Gardens\backend; .\.venv\Scripts\python.exe -m pytest -q
cd C:\dev\FinPlan_CWL\backend;     .\.venv\Scripts\python.exe -m pytest -q
```

Al 2026-09-10 dan **4.327 · 4.320 · 4.319 · 3.946**.

Si una falla por `ModuleNotFoundError`, es el Python equivocado — ver abajo.

---

## Tres trampas que te van a ahorrar una tarde

**Python 3.12, no el más nuevo.** El Python del sistema en la PC vieja era 3.14,
pero los cuatro venv están en **3.12** y varias dependencias todavía no publican
rueda para 3.14: `pip install` se pone a compilar desde fuente y falla. El guion
busca el 3.12 explícitamente.

**El despliegue no sale de GitHub.** Producción se sube con `railway up` desde
la carpeta local, no con un push. Empujar a GitHub pone el código a salvo, pero
**no despliega nada** — son dos gestos distintos.

**Cada servicio tiene su raíz.** No hay una regla por propiedad:

| Servicio | Desde dónde se sube |
|---|---|
| `FinPlan_Amarena-Backend` | `backend/` |
| `FinPlan-Amarena-Frontend` | `frontend/` |
| `FinPlan_Oxygen Backend` | `backend/` |
| `FinPlan_Oxygen` (front) | **la raíz del repo** |
| `FinPlan_Gardens_Backend` | **la raíz del repo** |
| `FinPlan_Gardens_Frontend` | `frontend/` |
| `FinPlan_CWL_Backend` | `backend/` |
| `FinPlanCWL_Frontend` | `frontend/` |

Subir desde la carpeta equivocada falla con `railpack prepare exited with an
error`, que no menciona directorios y cuesta encontrar. El despliegue anterior
sigue sirviendo mientras tanto, así que el error es ruidoso pero no rompe nada.

---

## Y cuando todo esté

No borres las carpetas de la PC vieja hasta que hayas hecho **un despliegue
completo** desde la nueva y lo hayas visto en vivo. El código ya está en GitHub,
pero la primera corrida de punta a punta es la única prueba de que la máquina
nueva quedó bien.
