# Replicar el cierre mensual en otra propiedad

Guía para llevar a **otra instalación de FinPlan** —Oxigen— todo lo que se
construyó para Amarena entre el 27-ago y el 3-sep de 2026: **104 commits,
145 archivos, 4.160 pruebas**. Todo — las pantallas, las mejoras y cada
defecto corregido. El objetivo es que Oxigen quede exactamente como está
Amarena hoy.

Está escrita para ejecutarse en orden. Cada bloque dice **qué archivos**, **qué
decisión de diseño lo sostiene** y **qué se rompe si se hace de otra manera** —
porque casi todos los defectos de este período no fallaban: daban un número
creíble y equivocado.

---

## 0-bis · La forma más segura de llevarlo: portar el código

⚠️ **Leer esto antes de escribir una línea.**

Esta guía es el **mapa**, no el territorio. Los 145 archivos llevan sus
comentarios con el porqué y con los números medidos en producción —«eran 38
celdas», «$2.058,69 en el total y en ningún renglón»—. Reescribir desde la guía
pierde eso, y con eso se pierde la razón por la que cada decisión está donde
está.

### Si Oxigen sale del MISMO repositorio

Es el caso fácil, y hay que agotarlo antes de considerar el otro:

```bash
# El rango completo del período, en orden
git log --oneline c0b4301..HEAD   # c0b4301 = el último commit ANTES del período

# Portar todo de una
git cherry-pick <primer-commit>..<último-commit>

# O el diff de un bloque suelto
git diff <antes>..<después> -- backend/app/api/auditoria_api.py
```

Después: correr la suite, aplicar la migración, y **rehacer sólo lo que es de
Amarena** (§12).

### Si Oxigen es una instalación separada

Copiar los archivos del **Anexo B** en el orden del §11, empezando por los
cimientos. Cada archivo compila solo salvo por sus importaciones, y los
comentarios explican qué espera de su entorno.

⚠️ **Las pruebas van con el código, no después.** Las 56 de `backend/tests/`
del Anexo B no son un extra: la mitad son guardias estructurales que leen el
código fuente y fallan cuando alguien reintroduce un defecto. Portar la
funcionalidad sin ellas deja a Oxigen sin la red que a Amarena le encontró
catorce cosas.

---

## 0 · Antes de empezar: qué tiene que existir ya

Esto NO se replica, se da por hecho. Si Oxigen no lo tiene, hay que resolverlo
primero o nada de lo de abajo cierra.

| Pieza | Por qué es requisito |
|---|---|
| `pl_engine` con `linea_de_fila`, `group_for_dept`, `consolidate_dept` | Toda la auditoría y los desgloses clasifican **con el motor**. Reimplementar la clasificación da un reporte que cuadra consigo mismo y aprueba justo cuando el P&L está mal |
| `report_line_config` + `account_mapping` | El catálogo GL por departamento y los nombres de cuenta. Son tablas, editables sin desplegar |
| `department_catalog` | Los códigos y nombres de departamento |
| `scenario_stats` | Ocupación, ADR y socios del Club. Sin esto la franja de estadísticas queda vacía |
| `annotations` | Los comentarios del cierre |
| `actuals_through` en `scenarios` | El corte del rolling forecast |

⚠️ **Verificar los códigos de departamento antes que nada.** En Amarena el
catálogo mezcla cuatro dígitos (`0110`) con tres (`260`, `270`, `280`), y esa
mezcla causó dos defectos. Ver §7.

---

## 1 · Cimientos: una sola verdad por número

Antes de cualquier pantalla. Estos tres archivos son la base de todo lo demás.

**`backend/app/nombres_cuenta.py`** — cómo se llama una cuenta, nunca vacío.

* `account_name_example` acumula todas las variantes vistas en el mayor
  (`"DEPRECIATION1 | DEPRECIATION2 | DEPRECIATION"`). Como rótulo son sesenta
  caracteres donde caben veinte.
* Se elige la variante **sin sufijo numérico**, no la primera: la primera suele
  ser justo la que lo tiene.
* Cadena de respaldo: nombre del asiento → `account_mapping` → conceptos de
  planilla → `"Cuenta 6023"`.

**`backend/app/departamentos.py`** — el cero de adelante, en el ORM.

* `110` → `0110`, y `0260` → `260`. **Las dos direcciones.**
* Va en un listener `before_flush`, no en cada importador: hay **cuatro** rutas
  que escriben un `dept_code` sin pasar por el importador del GL.
* Cuáles son de tres dígitos se le pregunta al catálogo, no a una lista.

**`backend/app/perfiles.py`** — el perfil de sólo lectura.

* Una dependencia sobre las rutas de escritura, con una lista `SIN_EFECTO` para
  los POST que no escriben (exportar a Excel es un POST).
* Compara contra `request.scope["route"].path` —la plantilla— y no contra la
  URL, o los `{scenario_id}` nunca calzan.

---

## 2 · El P&L Detail en tres ámbitos

**`backend/app/api/pl_detail_api.py`** · `frontend/app/month-end/pl-detail/`

La plantilla `CONSOLIDADO` es una lista de tuplas `(tipo, rótulo, códigos)` con
cinco tipos: `sec` (sección), `det` (renglón), `sub` (subtotal), `tot` (total),
`esp` (blanco). **Todo lo demás la reusa** — la Auditoría, el Word, el Excel.

Tres ámbitos: Consolidado, Hotel y Club. **El Hotel es el Consolidado menos el
Club, en tres restas** — no una consulta aparte.

⚠️ Cada renglón de overhead suma `OH_*` **y** `COH_*`. En Amarena faltaba el
`COH_` y $937,33 estaban en el total y en ningún renglón.

---

## 3 · Cierre de Mes: la pantalla y sus sub-tabs

**`frontend/app/month-end/pl/page.tsx`** (el orquestador) y sus componentes:
`Auditoria.tsx` · `Estadisticas.tsx` · `Formato.tsx` · `DoceMeses.tsx` ·
`ResumenDoceMeses.tsx` · `VistasVisibles.tsx` · `DetalleCelda.tsx`

**Cuatro ranuras libres**, cada una con cualquier escenario de cualquier año.
No atadas a un rol: comparar dos versiones del mismo budget es una pregunta
legítima.

**El orden de los sub-tabs es el del cierre**, no el de cómo se construyeron:
se abre con el estado de resultados, se comprueba que cuadre, se mira el año, y
después las aperturas por departamento.

⚠️ **La vista inicial sale de `VISTAS[0]`, no de un texto.** Con el valor
escrito a mano, reordenar deja la pantalla abriendo en el sub-tab que quedó
último. No falla; abre en el cuadro equivocado.

**Panel de Vistas** (`VistasVisibles.tsx`): esconder y mostrar sub-tabs, menús y
sub-menús. Sparse matrix `tab_enablement`, default-ON, con un centinela `""` en
la columna `perfil` — dos NULL no colisionan en un UNIQUE de Postgres.

---

## 4 · La Auditoría

**`backend/app/api/auditoria_api.py`** · `frontend/app/month-end/pl/Auditoria.tsx`

Tres bloques, tres preguntas: **¿cuadra?**, **¿de qué está hecho?**, **¿cómo se
reparte?**

### Reglas que hacen válida una auditoría

1. **Clasificar con el motor.** `pl_engine.linea_de_fila`, que reusa las mismas
   funciones que arman el P&L.
2. **El cuadre es por RENGLÓN del reporte, no por código suelto.** Un total no
   tiene detalle propio, y el vocabulario canónico parte el gasto de un
   departamento en varias líneas. Comparar códigos sueltos dio **37 descuadres
   falsos** en el primer intento.
3. **Los renglones derivados no se auditan** (`codigos_atribuibles`): Operating
   Profit es ingreso menos gasto, no se compone de asientos. Otros **6 falsos**.
4. **Los totales y subtotales se muestran con `detalle = null`, no cero.** Cero
   contra un total da un descuadre por el monto entero.
5. **Cobertura**: cuántos asientos, cuántos con monto, cuánto suma. Sin eso, un
   reporte al que le falta media hoja se ve igual que uno completo.

### Cómo se lee

Secciones como banda, subtotales con regla simple, hitos con **regla doble**
(Total Revenues, Operating Profit, GOP, EBITDA, Net Profit). Los hitos se
marcan por `line_code` en el backend, no por rótulo en la pantalla: el texto
cambia y comparar textos deja de resaltar sin que nada falle.

En el detalle: dentro de cada departamento, agrupado por naturaleza en orden de
P&L; lo que se movió primero y de mayor a menor; las cuentas disponibles del
catálogo al final, separadas y sólo donde el departamento **sí se movió** en esa
naturaleza.

---

## 5 · Ver de qué está hecho un número

**`backend/app/api/detalle_celda_api.py`** ·
`frontend/app/month-end/pl/DetalleCelda.tsx`

Un endpoint: dado `(clase, clave)` devuelve las cuentas que suman esa celda,
por versión, con los doce meses. Lo usan **tres** cosas: el desplegable, la
pantalla de Checkbooks y su Excel.

### Los cinco invariantes

1. **La llave es `(departamento, cuenta)`.** Con la cuenta sola, la 7065 de
   Habitaciones y la del Club caen en la misma fila y el resultado no es de
   nadie — y las dos se llaman «Cleaning Supplies».
2. **La fuente se elige con `lo_subido_manda`**, la misma pregunta que hace el
   cuadro. Un presupuesto no tiene mayor cargado pero **sí está conectado al
   GL**: cada línea del checkbook lleva su `account_code` y los 17 conceptos de
   planilla SON cuentas del mayor.
3. **El departamento sube EN CADENA.** `consolidate_dept` resuelve un escalón y
   hay cadenas de dos (`0132 → 0130 → 0140`).
4. **El reparto entra como opex**, en las dos ramas: el 49xx del mayor y
   `AllocationEntry` del checkbook. Los asientos de reparto van **por mes**, no
   en doce columnas.
5. **Un forecast vivo MEZCLA**: hasta `actuals_through` manda el ACTUAL
   enlazado, de ahí en adelante el propio escenario. Cada mes de **una sola**
   fuente.

### Cómo se prueba

Para cada `(clase, clave)` de `gasto_por_clase(detalle=True)`, la suma de doce
meses del detalle tiene que dar la celda. En Amarena: **120 celdas, 0
descuadres**.

### La ventana

* Sale del árbol con un **portal a `document.body`**. La animación de página
  (`.pag-entra`, `animation … both`) deja un `transform` aplicado, y un ancestro
  con transform se vuelve el bloque contenedor de sus descendientes `fixed`: la
  ventana aparecía siempre arriba por más que se le pasara la posición del clic.
* Sin fondo oscuro: con velo, poder arrastrarla no sirve de nada.
* Abre junto al clic y se acomoda sola si no entra, en `useLayoutEffect`.

---

## 6 · Documentos

**`backend/app/export/cierre_word.py`** · `cuadro_excel.py` ·
`frontend/lib/exportCuadro.ts`

**Un registro de capítulos**, recorrido con la misma lista de sub-tabs. No una
secuencia escrita a mano: con eso hay que acordarse de agregar cada sub-tab
nuevo, y **olvidarse no falla** — el capítulo simplemente no sale. En Amarena
cubría 9 de 17.

Reglas:

* **Sólo las vistas activas**, resuelto con lo que la pantalla ya usa para
  dibujar. Una segunda lectura de la misma decisión es una segunda oportunidad
  de que difieran.
* **Un cuadro sin un solo número NO entra**, y se dice cuál quedó afuera y por
  qué —en el aviso y en la portada del documento—. Un cuadro en cero se lee
  como «no hubo movimiento», que es una afirmación.
* **No se baja con la pantalla a medio cargar**: la mitad de los capítulos lee
  el estado y la otra mitad pide lo suyo con `await`.
* **El P&L Statement sale en sus dos vistas** (Totales y Departamental).

### Forma del Word

Sin rejilla: **reglas horizontales**, una bajo el encabezado y una sobre cada
total. Márgenes de celda de 108 → 60/14 twips (eso es lo que de verdad achica
el cuadro). Anchos por columna desde el payload. Y ojo con el run vacío que
deja `celda.text = ""`: hereda 10 pt y fija la altura de la fila.

### Forma del Excel

Índice adelante cuando hay más de una hoja, con el **nombre real** de la pestaña
—Excel corta en 31 caracteres y desambigua los repetidos—. Jerarquía con la
**sangría de Excel**, no con espacios en el texto.

⚠️ **Todo campo nuevo del payload hay que declararlo en el modelo Pydantic.**
Pydantic descarta en silencio lo que no conoce: pasó con los comentarios y con
la franja de estadísticas, y en los dos casos el documento salió sin ellos sin
que nada fallara.

---

## 7 · Los importadores

**`gl_detail_importer.py`** · `actual_pl_importer.py` · `codificacion_importer.py`

⚠️ **El defecto más caro de todo el período, porque no falla.**

`_CODIGO_AL_INICIO` acepta tres o cuatro dígitos —el Club (260) es de tres de
verdad—, así que un `110 · Habitaciones` pasa el filtro y se guarda como `110`.
Y `110` no está en el catálogo:

```
group_for_dept("0110") -> ROOMS
group_for_dept("110")  -> OTHER_OVERHEAD
```

El gasto de Habitaciones sale como Overhead, **el P&L cuadra igual**, y nada
avisa.

Tres cosas que hay que revisar en Oxigen:

1. **La regla es estructural**: tres dígitos que no sean un departamento de tres
   es un cuatro dígitos al que le falta el cero. El conjunto de los de tres se
   **deriva**, no se escribe.
2. **El error inverso existe**: `zfill(4)` sin condición convierte el `260` en
   `0260`.
3. **Dos importadores no pueden tener dos tablas de palabras clave.** En Amarena
   el resumen mandaba «Misceláneos» a un código inexistente y el detalle al
   bueno, y ninguno de los dos conocía el Club.

---

## 8 · Meses cerrados y candados

**`frontend/lib/mesesCerrados.ts`** · `backend/app/candado_meses.py`

* El candado vive en el ORM (`before_flush`), no en los endpoints: son 109
  rutas de escritura y sólo 9 llevan el mes en la URL.
* **Sólo el FORECAST cierra meses.** Un budget no tiene actuales; un actual se
  corrige, que es otra conversación.
* La pantalla **pregunta al backend** cuáles están cerrados. Copiar la regla en
  el front es la segunda verdad de siempre.
* Los campos van **`readOnly`, no `disabled`**: un mes cerrado se sigue
  consultando y `disabled` no deja ni copiar el número.

**Un escenario enllavado congela sus DATOS, no el caché de su reporte.**
`pl_lines` es el resultado de una cuenta, no algo que alguien escribió. En
Amarena el BUDGET Final tenía **0 líneas** guardadas y tres pantallas mostraban
cero.

---

## 9 · Pantallas de consulta

`frontend/app/month-end/checkbooks/page.tsx` ·
`frontend/app/month-end/revenue-plan/page.tsx`

Para quien no tiene acceso a Planning. **De sólo lectura, sin un solo campo** —
no se resuelve escondiendo el botón de guardar: un formulario de sólo lectura
sigue mandando lo que se escriba si alguien encuentra la ruta.

* **Checkbooks**: los cuatro libros, por departamento, doce meses. Reusa
  `detalle-de-celda`.
* **Armado de ingresos**: las ocho vistas de Planning. Seis salen de
  `/revenue/by-room-type/`, que las calcula con la misma función del motor.

⚠️ **Las razones no se suman.** Ocupación y net rate son cocientes: el año se
rederiva con su numerador y su denominador. El renglón TOTAL sólo aparece donde
sumar significa algo.

---

---

## 9-bis · Inventario completo de lo que hay que dejar en pie

Ésta es la lista de comprobación: Oxigen tiene que terminar con todo esto.

### Pantallas y rutas NUEVAS

| Ruta | Qué es |
|---|---|
| `/month-end/pl` | Cierre de Mes — el orquestador, 17 sub-tabs |
| `/month-end/pl-detail` | P&L Detail Full, copia con pantalla propia |
| `/month-end/checkbooks` | Los cuatro checkbooks, sólo consulta |
| `/month-end/revenue-plan` | Armado de ingresos, ocho vistas, sólo consulta |
| `/reports/pl-detail` | Los tres P&L Detail del libro del owner |
| `/reports/pl-by-dept` | P&L por departamento |
| `/reports/pl-full-detail` | Full P&L ejecutivo |
| `/admin/tabs` | Panel de Vistas — esconder menús y sub-tabs |
| `/nonop/management-fees` | Los tres fees, con opción manual |

### Sub-tabs de Cierre de Mes (17, en orden)

P&L Statement · Auditoría · Resumen 12m · 12 meses · Revenue x Depto ·
Payroll x Depto · Cost x Depto · Opex x Depto · Property x Cuenta · Formato ·
Consulta GL · Flow Through · Simplified P&L · Monthly Summary · Revenue Detail ·
F&B Cost Detail · P&L

### Endpoints nuevos

| Endpoint | Para qué |
|---|---|
| `GET /pl/{id}/auditoria/?mes=` | El cuadre, el detalle y la matriz por departamento |
| `GET /gasto-por-clase/detalle-de-celda/` | Las cuentas que suman una celda |
| `GET/PUT /pl/{id}/comentarios/` | Los comentarios del cierre, por mes |
| `GET /reports/pl-detail/{ambito}/` | Los tres ámbitos del P&L Detail |
| `GET /pl/{id}/doce-meses/` | Los doce meses sin agregar |
| `GET /pl/{id}/estadisticas/` | Ocupación, ADR, RevPAR, socios |
| `POST /export/cuadros/word/` | El documento de cierre |
| `GET /scenarios/{id}/meses-cerrados/` | Qué meses no se editan |

### Componentes y librería del front

`Auditoria` · `Estadisticas` · `Formato` · `DoceMeses` · `ResumenDoceMeses` ·
`VistasVisibles` · `DetalleCelda` · `Checkbooks` · `BloqueSeguro` ·
`NivelDeDetalle` · `app/error.tsx`
`lib/`: `mesesCerrados` · `perfil` · `tabsVisibles` · `imprimirEnUnaHoja` ·
`escenarioPreferido` · `exportCuadro`

### Exportadores

`cierre_word.py` · `cuadro_excel.py` · `pl_detail_excel.py` ·
`conceptos_por_depto_excel.py`

---

## 9-ter · Todos los defectos corregidos

Los catorce del §resumen son los más caros. Ésta es la lista completa, por
familia, para que en Oxigen se revise cada una.

### Números que estaban mal y no fallaban

* El **P&L por Departamento no veía el ingreso**.
* El **costo de ventas leía un ingreso que no existe**.
* El **tab de ingreso del cierre salía vacío** y no decía lo mismo que el P&L.
* **Cafetería y lavandería**: el saldo se descartaba en vez de verse en overhead.
* **El origen del reparto** mostraba cero o todo, en vez de su residuo.
* El **Resumen 12m** perdía el sobrante del reparto — 1.361 a 1.493 por mes.
* Un **FORECAST** mostraba presupuesto en meses cerrados, en dos lugares
  distintos (el Resumen y el desplegable).
* El **ADR** se derivaba sobre ingreso que no es noche vendida.
* **Socios pagando** en un período se sumaba, cuando es un promedio.
* Los **P&L Detail leían una foto** en vez de calcular.
* El **gasto de propiedad** tenía dos fuentes y cada pantalla leía una.
* El **BUDGET Final** tenía cero líneas de P&L guardadas.
* La **comisión de tarjeta** tenía línea propia cuando va en A&G.
* **Rent y Properties Insurance** faltaban en el auxiliar.
* Faltaban **`COH_*`** en los renglones de overhead.

### Datos que entraban mal

* **Departamento sin el cero** (`110` → Overhead) — cuatro rutas de escritura.
* **El inverso**: `zfill(4)` volvía `0260` al Club Madresal.
* **Dos importadores con dos tablas** de palabras clave que no coincidían.
* **Misceláneos** iba a un código que no existe.
* El **OPEX** no se recalculaba al tipo de cambio del budget.
* Un **cero calculado borraba un dato digitado**.
* El **push** no respetaba lo digitado.

### Guardados que no guardaban

* **Cuatro guardados devolvían 405**: el front mandaba PUT y la ruta era POST.
* La **fila en blanco** del reparto se guardaba.
* No se podía **borrar una fila** de la matriz de reparto.
* Una **respuesta sin cuerpo** se parseaba como JSON y reventaba después de
  haber funcionado.
* **`Working-VIEJO`** era imborrable por comparar subcadenas.

### La pantalla se caía o mentía

* Un **cuadro que revienta** se llevaba la pantalla entera (`BloqueSeguro` +
  `app/error.tsx`).
* La **red de seguridad no atrapaba nada** porque la condición corría afuera.
* El **escenario 2035** volvía por dos caminos distintos.
* La **ventana de detalle** quedaba siempre arriba por un ancestro con
  `transform`.
* El **rótulo se montaba encima de los montos** en una tabla de ancho fijo.

### Documentos incompletos

* El **Word cubría 9 de 17** sub-tabs.
* Las **notas y la franja de estadísticas se caían en el modelo Pydantic**.
* La **Auditoría bajaba sólo su primer bloque**.
* **Revenue Detail y F&B** bajaban sólo el acumulado.
* El **Excel bajaba una sola hoja**.
* Los **cuadros vacíos** entraban y se leían como «no hubo movimiento».

## 10 · Cómo verificar en Oxigen

El método que encontró los catorce defectos:

```bash
# Leer y descartar, contra la base real
MSYS_NO_PATHCONV=1 railway ssh --service <backend> "python3 -" < script.py
```

El script tiene que: `import app.main` (engancha los listeners), usar el
intérprete de la app (`os.readlink("/proc/1/exe")`), tomar `LD_LIBRARY_PATH` de
`/proc/1/environ`, y **hacer `rollback` siempre**.

### Las tres comprobaciones que valen

1. **El detalle suma la celda.** Recorrer todas las `(clase, clave)` de
   `gasto_por_clase(detalle=True)` y comparar contra `detalle_de_celda`.
2. **El resumen suma el P&L.** Comparar `gasto_por_clase` contra
   `_monthly_results` mes a mes, por escenario.
3. **Ningún código de departamento fuera del catálogo.** Recorrer las tablas con
   `dept_code`.

⚠️ **Incluir SIEMPRE un forecast con corte.** La comprobación de 120 celdas de
Amarena usó los tres primeros escenarios y el forecast —el cuarto, y el único
que mezcla actuales con proyectado— quedó afuera. Ahí sobrevivieron **38
descuadres** a una prueba que parecía exhaustiva.

---

## 11 · Orden sugerido

| # | Bloque | Depende de |
|---|---|---|
| 1 | Requisitos del §0 y revisión de códigos de departamento | — |
| 2 | Cimientos (§1) | §0 |
| 3 | Importadores (§7) | §1 |
| 4 | `pl_detail_api` y la plantilla (§2) | §0 |
| 5 | Cierre de Mes y sus sub-tabs (§3) | §2 |
| 6 | Auditoría (§4) | §2, §4 |
| 7 | `detalle-de-celda` y la ventana (§5) | §4 |
| 8 | Documentos (§6) | §3 a §5 |
| 9 | Meses cerrados (§8) | — |
| 10 | Pantallas de consulta (§9) | §5 |

**Después de cada bloque, correr las tres comprobaciones del §10.** No al final:
los defectos de este período se encontraron cotejando, no leyendo código.

---

## 12 · Qué NO copiar tal cual

* **Los nombres de departamento y las palabras clave de los importadores.** Son
  de Amarena. En Oxigen hay que rehacer la tabla contra su catálogo.
* **`PREFERENCIA`** en `escenarioPreferido.ts`: los años del ciclo de
  planificación los decide el owner de esa propiedad.
* **Los tres de tres dígitos** (260, 270, 280). Se derivan del catálogo.
* **`REVENUE_LINE_ACCOUNT`**: el par (departamento, cuenta) de las líneas de
  ingreso que SON una cuenta. Cambia por propiedad.
* **La bitácora** (`BITACORA_AMARENA.md`): es el registro de Amarena. Oxigen
  necesita la suya.

---

## Referencia

* **`docs/BITACORA_AMARENA.md`** — qué se hizo, y los catorce defectos con sus
  montos.
* Los mensajes de commit del 27-ago al 3-sep: cada uno lleva el porqué y, donde
  hubo, el número medido en producción.

---

# Anexo A · Los 104 commits, en orden

Cada uno lleva en su mensaje el porqué y, donde hubo, el número medido
en producción. Ésta es la lista completa para que no falte nada.


## 2026-08-27 — 30 commits

* La planilla 2026 de Amarena: puesto, persona y salario por departamento
* El motor sí corre por railway ssh: le faltaba el LD_LIBRARY_PATH
* El corte del mixer es por instalación: Amarena arranca en 2026
* Package Components: decir qué hacer cuando no hay experiencias
* El Room Revenue no depende de los drivers de pax para poder llenarse
* Un cero calculado no borra un dato digitado
* Recalcular el OPEX al tipo de cambio del budget
* El costo de ventas leía un ingreso que no existe
* El below-GOP se abre por cuenta y por departamento
* La comision de tarjeta vuelve a A&G, sin linea aparte
* Rent y Properties Insurance: abrir los dos renglones que faltaban en /nonop
* Cuatro guardados que devolvian 405: el front mandaba PUT y la ruta era POST
* Corrige el nombre de la funcion en un comentario
* Opcion manual para los tres fees, rotulada, y que le gane al porcentaje
* El impuesto de renta tambien se digita, y lo digitado manda
* El P&L por Departamento no veia el ingreso
* El renglon manual va en la pantalla de Management Fees, que es donde se ocupa
* Sumatorias por columna en el P&L por Departamento
* El origen del reparto muestra su residuo, no cero y no todo
* El P&L por Departamento sale en UNA hoja: en papel y en Excel
* Los 17 conceptos de planilla ya calculados, un tab por departamento
* El mismo P&L en tres niveles de detalle, a un clic
* Las posiciones que componen el S&W, justo arriba de la fila que las suma
* El tab de ingreso del cierre deja de salir vacio, y dice lo mismo que el P&L
* Socios del Club y cuota promedio, junto a la ocupacion y el ADR
* Los socios del Club, tambien en la presentacion a la Junta
* Los tres P&L Detail del libro del owner: Consolidado, Hotel y Club
* P&L Detail: las estadisticas del Excel, corte por mes/YTD/año y comparacion
* El cuadro de cierre del owner: mes, YTD y año lado a lado
* Hasta cuatro versiones escogibles, y un Excel con la forma del cuadro

## 2026-09-01 — 9 commits

* Cafeteria y lavanderia: el saldo se ve en overhead, no se descarta
* Cierre de Mes: un sub-tab con los doce meses de una version
* Los P&L Detail calculan, no leen una foto
* 12 meses: dos paneles, Actual y Budget, cada uno con su version
* El panel de 12 meses Budget queda editable — los parametros, no los montos
* «Full P&L ejecutivo» pasa de Reportes a Cierre de Mes
* «P&L Detail Full (consolidado)» tambien entra por Cierre de Mes
* Copia de «P&L Detail Full» con pantalla propia bajo Cierre de Mes
* Cierre de Mes: modo compacto — se esconde lo vacio, no se borra

## 2026-09-02 — 33 commits

* Perfiles: el que solo mira, y vistas limitadas por perfil
* Solo lectura: los tres POST que no escriben quedan exentos
* Cierre de Mes: sub-tabs «Formato» y «Auditoria»
* Formato y Auditoria: los codigos tienen que ser los del MOTOR
* Cotejo contra el libro de julio: dos vocabularios y un total que mentia
* Auditoria: el cuadre es por RENGLON, no por codigo suelto
* Auditoria: los renglones DERIVADOS no se auditan
* Cierre de Mes: estadisticas en todos los sub-tabs, y 12 meses con su version
* ADR de julio sin lo que no es noche vendida, y estadisticas en Formato
* Socios pagando: en un periodo es el PROMEDIO, no la suma ni el saldo
* Revenue x Depto: el ingreso en UNA linea por concepto
* P&L Statement: un click lo lleva de totales a departamental
* Gasto por depto: el sub-departamento del checkbook sube a su padre
* Cierre de Mes: quitar y poner sub-tabs sin borrarlos
* Panel de Vistas: menu, sub-menu y sub-tabs desde un solo lugar
* Resumen 12 meses: Actual y Budget a la vez, y el generador de Word
* Boton Word en Cierre de Mes: un capitulo por sub-tab activo
* Word: entran el P&L Statement y el Resumen 12m, sin copiar su calculo
* Word: entra el Monthly Summary — nueve capitulos
* Reparto de lavanderia: la fila en blanco no se guarda mas
* Arreglo: el return nuevo se habia ido a la funcion de CAFETERIA
* Repartos: un cuadro que revienta ya no se lleva la pantalla
* Repartos: la red no atrapaba nada porque la condicion corre AFUERA
* Repartos: el crash era `monthly`, que el endpoint dejo de mandar
* Gasto de propiedad: una sola fuente, la que lee el P&L
* Below-GOP: las dos tablas NO eran un duplicado — se cierra la revision
* Repartos: ya se puede borrar una fila de la matriz
* Una respuesta SIN cuerpo no se parsea como JSON
* Checkbook de Opex: los meses cerrados se ven grises y no se editan
* Los cinco checkbooks muestran en gris el mes que ya está cerrado
* `Working-VIEJO` se puede borrar: la protección compara el nombre completo
* Los tres escenarios de 2026 fijos, y la Auditoría subdividida por naturaleza
* Un escenario cerrado congela sus DATOS, no el caché de su reporte

## 2026-09-03 — 33 commits

* El importador le devuelve el cero al departamento que viene sin él
* Corrige la explicación del 280: es puro ingreso, no overhead
* El cero del departamento se arregla en el ORM, no en cada importador
* Property x Cuenta: cada cuenta con su nombre, y que quepa en su celda
* El Cuadre de la Auditoría se lee como un P&L formal
* El Resumen y el P&L dejan de contar dos historias del mismo gasto
* El Cuadre se lee como un estado de resultados impreso
* El P&L Statement muestra las TRES versiones, no dos
* Los sub-tabs de Cierre de Mes, en el orden en que se miran
* El Word trae todas las vistas activas, en el orden de la pantalla
* El Word: sin cuadros vacíos, y con forma de estado impreso
* Tocar una línea abre las cuentas que la suman, sin salir de la pantalla
* La celda que se puede abrir ahora SE VE
* El detalle: mes y acumulado, en una ventana que se mueve
* La ventana de detalle abre junto a la línea que se tocó
* La ventana de detalle sale del árbol: por eso quedaba siempre arriba
* El desplegable suma exactamente la celda: 120 de 120
* Comentarios del cierre: la columna, la nota del desplegable y el Word
* Ningún punto puede olvidarse el mes de la nota
* La nota dice si está guardada, y tiene botón
* Las notas del Word se caían en el modelo, y el documento ahora dice qué falta
* Un solo Excel con TODOS los sub-tabs, una hoja cada uno
* El botón de Excel baja todos los tabs, en el orden de la pantalla
* El Excel del cierre: índice adelante y pestañas que se distinguen
* Auditoría completa, y las estadísticas en cada cuadro
* El detalle por departamento de la Auditoría vuelve a leerse
* La hoja «Auditoría Detalle» se agrupa por departamento y naturaleza
* Sub-tab «Checkbooks»: los cuatro libros, para consultar sin Planning
* Checkbooks sale del cierre y pasa al menú, junto a Full P&L Ejecutivo
* Los checkbooks se separan por departamento, y el selector se llena
* El forecast vivo: actuales hasta el corte, proyectado después
* Armado de ingresos: las ocho vistas de Planning, para consultar
* Bitácora de Amarena: qué se construyó desde los actuales de marzo-julio

---

# Anexo B · Los 145 archivos tocados

⚠️ **La forma más segura de replicar es portar estos archivos**, no
reescribirlos: cada uno lleva sus comentarios con el porqué y las
trampas medidas. La guía de arriba es el mapa; esto es el territorio.


## Backend · lógica nueva (4)

* `backend/app/api/catalogo_departamentos_api.py`
* `backend/app/departamentos.py`
* `backend/app/nombres_cuenta.py`
* `backend/app/perfiles.py`

## Backend · API (17)

* `backend/app/api/_apagados.py`
* `backend/app/api/allocation_api.py`
* `backend/app/api/auditoria_api.py`
* `backend/app/api/comentario_pl_api.py`
* `backend/app/api/costs_api.py`
* `backend/app/api/detalle_celda_api.py`
* `backend/app/api/estadisticas_api.py`
* `backend/app/api/export_api.py`
* `backend/app/api/gasto_por_clase_api.py`
* `backend/app/api/nonop_api.py`
* `backend/app/api/opex_api.py`
* `backend/app/api/payroll_api.py`
* `backend/app/api/pl_api.py`
* `backend/app/api/pl_detail_api.py`
* `backend/app/api/provisioning_api.py`
* `backend/app/api/revenue_api.py`
* `backend/app/api/scenarios_api.py`

## Backend · motor (3)

* `backend/app/engine/mixer_canales.py`
* `backend/app/engine/pl_engine.py`
* `backend/app/engine/recalculate.py`

## Backend · exportadores (4)

* `backend/app/export/cierre_word.py`
* `backend/app/export/conceptos_por_depto_excel.py`
* `backend/app/export/cuadro_excel.py`
* `backend/app/export/pl_detail_excel.py`

## Backend · importadores (3)

* `backend/app/importers/actual_pl_importer.py`
* `backend/app/importers/codificacion_importer.py`
* `backend/app/importers/gl_detail_importer.py`

## Backend · modelos y varios (8)

* `backend/app/errores.py`
* `backend/app/main.py`
* `backend/app/models/mapping.py`
* `backend/app/models/tab_enablement.py`
* `backend/app/models/user.py`
* `backend/app/seed_data/mapping_pl.json`
* `backend/app/seed_data/owners_q.json`
* `backend/app/seed_owners_q.py`

## Backend · migraciones (1)

* `backend/alembic/versions/137_tab_enablement_por_perfil.py`

## Backend · pruebas (56)

* `backend/tests/test_actuals_pl.py`
* `backend/tests/test_armado_de_ingresos.py`
* `backend/tests/test_auditoria_detalle.py`
* `backend/tests/test_candado_del_escenario.py`
* `backend/tests/test_candado_no_tapa_el_reporte.py`
* `backend/tests/test_capital_reserve_no_duplica.py`
* `backend/tests/test_checkbooks_de_consulta.py`
* `backend/tests/test_comentarios_del_cierre.py`
* `backend/tests/test_comision_tarjeta_va_en_ag.py`
* `backend/tests/test_conceptos_por_depto_excel.py`
* `backend/tests/test_costo_ventas_lee_el_checkbook.py`
* `backend/tests/test_cuadro_excel.py`
* `backend/tests/test_cuentas_de_reparto.py`
* `backend/tests/test_dept_normalizado_en_todo_camino.py`
* `backend/tests/test_dept_sin_cero_inicial.py`
* `backend/tests/test_detalle_de_celda.py`
* `backend/tests/test_el_tab_se_puede_abrir_por_la_url.py`
* `backend/tests/test_escenario_por_defecto.py`
* `backend/tests/test_estructura.py`
* `backend/tests/test_excel_todos_los_tabs.py`
* `backend/tests/test_franja_kpis_en_documentos.py`
* `backend/tests/test_gl_allocation.py`
* `backend/tests/test_honorarios_administracion.py`
* `backend/tests/test_impresion_en_una_hoja.py`
* `backend/tests/test_ingreso_por_linea_en_el_cierre.py`
* `backend/tests/test_lo_digitado_le_gana_al_porcentaje.py`
* `backend/tests/test_mapeo_coherente.py`
* `backend/tests/test_meses_cerrados_en_pantalla.py`
* `backend/tests/test_mixer_canales.py`
* `backend/tests/test_niveles_de_detalle_del_pl.py`
* `backend/tests/test_nombre_de_cuenta.py`
* `backend/tests/test_nonalloc_por_departamento.py`
* `backend/tests/test_nonop_por_linea_no_borra_el_resto.py`
* `backend/tests/test_opex_recalcular_tc.py`
* `backend/tests/test_orden_de_subtabs.py`
* `backend/tests/test_owners_q.py`
* `backend/tests/test_perfil_solo_lectura.py`
* `backend/tests/test_pl_detail_tres_ambitos.py`
* `backend/tests/test_pl_por_depto_ve_el_ingreso.py`
* `backend/tests/test_push_respeta_lo_digitado.py`
* `backend/tests/test_rent_y_seguro_en_el_auxiliar.py`
* `backend/tests/test_renta_digitada.py`
* `backend/tests/test_reparto_lavanderia.py`
* `backend/tests/test_respuesta_sin_cuerpo.py`
* `backend/tests/test_siembra_de_versiones.py`
* `backend/tests/test_socios_del_club_como_estadistico.py`
* `backend/tests/test_solo_se_excluye_lo_que_se_reparte.py`
* `backend/tests/test_statement_todas_las_ranuras.py`
* `backend/tests/test_subtabs_de_cierre.py`
* `backend/tests/test_sumatorias_pl_por_depto.py`
* `backend/tests/test_tabs_por_perfil.py`
* `backend/tests/test_una_sola_fuente_belowgop.py`
* `backend/tests/test_verbos_del_front_y_del_back.py`
* `backend/tests/test_version_protegida.py`
* `backend/tests/test_word_estetica.py`
* `backend/tests/test_word_todas_las_vistas.py`

## Backend · scripts (1)

* `backend/scripts/cargar_planilla_amarena_2026.py`

## Frontend · Cierre de Mes (13)

* `frontend/app/month-end/checkbooks/page.tsx`
* `frontend/app/month-end/pl-detail/Cierre.tsx`
* `frontend/app/month-end/pl-detail/page.tsx`
* `frontend/app/month-end/pl/Auditoria.tsx`
* `frontend/app/month-end/pl/Checkbooks.tsx`
* `frontend/app/month-end/pl/DetalleCelda.tsx`
* `frontend/app/month-end/pl/DoceMeses.tsx`
* `frontend/app/month-end/pl/Estadisticas.tsx`
* `frontend/app/month-end/pl/Formato.tsx`
* `frontend/app/month-end/pl/ResumenDoceMeses.tsx`
* `frontend/app/month-end/pl/VistasVisibles.tsx`
* `frontend/app/month-end/pl/page.tsx`
* `frontend/app/month-end/revenue-plan/page.tsx`

## Frontend · pantallas (20)

* `frontend/app/admin/import-actuals/page.tsx`
* `frontend/app/admin/tabs/page.tsx`
* `frontend/app/admin/users/page.tsx`
* `frontend/app/allocations/config/page.tsx`
* `frontend/app/costs/checkbook/page.tsx`
* `frontend/app/error.tsx`
* `frontend/app/globals.css`
* `frontend/app/nonop/checkbook/page.tsx`
* `frontend/app/nonop/management-fees/page.tsx`
* `frontend/app/opex/checkbook/page.tsx`
* `frontend/app/payroll/checkbook/page.tsx`
* `frontend/app/pl/simplified/page.tsx`
* `frontend/app/reports/junta/bloques.tsx`
* `frontend/app/reports/pl-by-dept/page.tsx`
* `frontend/app/reports/pl-detail/Cierre.tsx`
* `frontend/app/reports/pl-detail/page.tsx`
* `frontend/app/reports/pl-full-detail/page.tsx`
* `frontend/app/revenue/checkbook/page.tsx`
* `frontend/app/revenue/package-components/page.tsx`
* `frontend/app/scenarios/page.tsx`

## Frontend · componentes y librería (12)

* `frontend/components/BloqueSeguro.tsx`
* `frontend/components/NivelDeDetalle.tsx`
* `frontend/components/TopNav.tsx`
* `frontend/lib/api.ts`
* `frontend/lib/escenarioPreferido.ts`
* `frontend/lib/exportCuadro.ts`
* `frontend/lib/imprimirEnUnaHoja.ts`
* `frontend/lib/mesesCerrados.ts`
* `frontend/lib/perfil.ts`
* `frontend/lib/tabsVisibles.ts`
* `frontend/messages/en.json`
* `frontend/messages/es.json`

## Documentación (1)

* `docs/BITACORA_AMARENA.md`

## Otros (2)

* `CLAUDE.md`
* `backend/requirements.txt`
