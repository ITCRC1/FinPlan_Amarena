# Bitácora — FinPlan Amarena

Desde la carga de los actuales de **marzo a julio 2026** (27-ago) hasta el
3-sep-2026. **108 commits.**

No es una lista de commits: es qué cambió, por qué, y qué se descubrió al
hacerlo. El detalle técnico de cada punto está en el mensaje de su commit.

---

## 1 · El cierre mensual, de cero a un reporte completo

**Sub-tabs de Cierre de Mes** (hoy 17, en el orden en que se miran): P&L
Statement · Auditoría · Resumen 12m · 12 meses · las cinco aperturas por
departamento · Formato · y siete más.

* **Hasta cuatro versiones a la vez**, cada una libre — no atadas a un rol.
* **Estadísticas** (ocupación, ADR, RevPAR, socios del Club) como cabecera del
  reporte, no como panel suelto.
* **Panel de Vistas**: esconder y mostrar sub-tabs, menús y sub-menús sin
  borrarlos. Para presentar a los dueños sólo lo que corresponde.
* **Modo compacto**: se esconde lo que está en cero en todas las versiones.

## 2 · La Auditoría: probar que el P&L cuadra

Nació de cotejar contra tu libro de julio y encontrar **dos vocabularios de
línea** que hacían que los totales cerraran y el detalle saliera en cero.

* **Cuadre** por renglón del P&L —no por código suelto— contra la suma de su
  detalle. Los primeros intentos reportaron 37 y luego 6 descuadres **falsos**;
  hoy son cero falsos.
* **Detalle** por departamento y naturaleza, con las cuentas disponibles del
  catálogo GL marcadas aparte.
* **Cobertura**: cuántos asientos hay, cuántos con monto, cuánto suma. Sin eso,
  un reporte al que le falta media hoja se ve igual que uno completo.
* Se lee como un **estado de resultados impreso**: secciones, subtotales,
  hitos con regla doble.

## 3 · Los tres P&L Detail del libro del owner

Consolidado, Hotel y Club. El Hotel es el Consolidado menos el Club, en tres
restas. Con estadísticas, corte por mes / YTD / año y comparación.

## 4 · Documentos que salen solos

* **Word de cierre**: un capítulo por sub-tab activo, en el orden de la
  pantalla, con espacio para comentar cada cuadro. El P&L Statement sale en sus
  dos vistas (Totales y Departamental).
* **Excel**: todos los sub-tabs en un archivo, una hoja cada uno, con índice
  adelante.
* **Comentarios**: la columna del P&L y una nota por celda, guardadas **con el
  mes**, y se imprimen dentro del recuadro del Word.

## 5 · Ver de qué está hecho un número, sin salir de la pantalla

Tocás una línea y se abre una ventana —movible— con las cuentas que la suman,
mes y acumulado, las tres versiones lado a lado.

Comprobado: **120 celdas, 0 descuadres** contra el cuadro. Un presupuesto
también se abre por cuenta: cada línea de su checkbook lleva la suya.

## 6 · Dos pantallas de consulta, para quien no entra a Planning

* **Checkbooks** — Opex, Salarios, Costo de ventas y Gastos de propiedad, por
  departamento, doce meses. De sólo lectura.
* **Armado de ingresos** — inventario, noches por categoría, rack rates,
  ocupación, pax, canales, net rate y total revenue.

## 7 · Perfiles y candados

* **Perfil de sólo lectura** y vistas limitadas por perfil.
* **Meses cerrados**: al subir un actual, ese mes queda gris y no se edita en
  los cinco checkbooks. El candado ya existía en el ORM; lo que faltaba era
  verlo antes de chocar contra él.
* **Escenario enllavado**: congela sus datos, no el caché de su reporte.

---

# Lo que se encontró mientras se construía

Esto es lo que más vale de la bitácora: **catorce defectos que no fallaban**.
Ninguno rompía nada — todos daban un número creíble y equivocado.

| Qué pasaba | Cuánto era |
|---|---|
| El **Resumen 12m** perdía el sobrante del reparto de lavandería | ACTUAL may 2.090 · jun 4.147 · jul 1.121; BUDGET 1.361–1.493 **todos los meses** |
| Un **FORECAST** mostraba presupuesto en meses ya cerrados en el Resumen | mar/abr/may en 0 contra 12.189 / 25.851 / 56.027 |
| El **desplegable** no aplicaba esa mezcla | **38 celdas** del forecast |
| El **BUDGET Final 2026** tenía 0 líneas de P&L guardadas | 1.369 líneas faltantes; Resumen, Consulta y Cuadre en cero |
| Los **dos vocabularios de línea**: totales cuadraban, detalle en cero | $2.058,69 en el total y en ningún renglón |
| El **ADR de julio** incluía lo que no es noche vendida | $274,38 donde la tarifa real es $255,44 |
| El **P&L Statement** ignoraba el tercer escenario | el Forecast no salía |
| Un **departamento sin el cero** (`110`) caía en Overhead | el gasto de Habitaciones, y el P&L cuadraba igual |
| El **inverso**: `_pad4` volvía `0260` al Club Madresal | el departamento más grande del hotel |
| **Misceláneos** iba a un código inexistente en un importador y al bueno en otro | según por dónde se cargara |
| El **Word** cubría 9 de 17 sub-tabs, y las notas se caían en el modelo | Pydantic descarta en silencio lo que no declara |
| **`Working-VIEJO`** era imborrable | la regla comparaba por subcadena |
| El defecto del **escenario 2035** volvía por dos caminos | uno era una llave de memoria con puntos |
| Un **$6.000 de diferencia** en el budget | una segunda línea «Manual-madresal fee» de $16.337,08 |

---

# Cómo se verifica

Cada cosa se comprobó **contra producción**, leyendo y descartando
(`railway ssh` + rollback). Y quedó fijada con pruebas: **4.160 verdes** hoy.

⚠️ **Una lección de método, de la que hay que acordarse:** la comprobación de
120 celdas usó los tres primeros escenarios y el FORECAST —el cuarto, y el
único que mezcla actuales con proyectado— quedó afuera. Ahí sobrevivieron 38
descuadres a una prueba que parecía exhaustiva. **Al verificar, incluir siempre
un forecast con corte.**

---

# Lo que sigue abierto

Son datos, no código:

* **Nadie tiene perfil `viewer`** — 2 admin, 6 collaborator. Mientras los dueños
  entren como collaborator van a poder editar.
* **Estadísticas de agosto**: al subir el actual hay que cargarlas aparte, o el
  ADR sale con la ocupación presupuestada.
* **Club Madresal**: sólo `pagando` tiene datos; `total`, `condicionados` y
  `acuerdo_pago` en cero.
* **Work Risk Policy (6022)**: ACTUAL $721,16 · Budget y Forecast $0.
* **Cuentas 49xx Distribución**: 0 filas en los actuales.
* **La cuenta contable local** (`61011101`) en la Auditoría: necesita que el
  importador la conserve — hoy el GL entra en códigos USALI de cuatro dígitos y
  la cuenta local no se guarda junto al monto.
