/**
 * Planning Report: que los ORDINALES de cada fórmula apunten a la fila que suman.
 *
 * ## Por qué esto se corre de verdad y no se lee del código
 *
 * `suma_de` son índices: «esta fila es la suma de las filas 4, 5 y 6». El
 * checkbook arma dos pisos —cada departamento suma sus cuentas, y el TOTAL suma
 * los departamentos— sobre un arreglo que el modo compacto acorta. Un corrimiento
 * de uno no rompe nada que se vea: el exportador comprueba la fórmula contra el
 * número y, cuando no cuadra, **la descarta en silencio**. El reporte baja con
 * media hoja de números pegados y nadie se entera.
 *
 * Por eso acá se arman cuadros con datos sintéticos y se comprueba, celda por
 * celda y columna por columna, que `valores[suma_de]` suma exactamente lo que
 * dice la fila. Es la única manera de ver el corrimiento.
 *
 * Se corre con `node backend/tests/js/planning_report.js` (lo hace
 * `test_planning_report.py`). Sale distinto de cero si algo no cuadra.
 */
const fs = require("fs");
const path = require("path");

const RAIZ = path.resolve(__dirname, "../../../frontend");
const ts = require(path.join(RAIZ, "node_modules/typescript"));

/** Carga un módulo .ts del frontend borrándole los imports y pasándole lo que
 *  necesita por parámetro: no hay bundler acá y tampoco hace falta. */
function cargar(rel, inyecta = {}) {
  const src = fs.readFileSync(path.join(RAIZ, rel), "utf8")
    .replace(/^import[\s\S]*?from\s+"[^"]+";\s*$/gm, "");
  const js = ts.transpileModule(src, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const mod = { exports: {} };
  const nombres = Object.keys(inyecta);
  new Function("module", "exports", "require", ...nombres, js)(
    mod, mod.exports, require, ...nombres.map(n => inyecta[n]));
  return mod.exports;
}

const T = cargar("lib/tresCortes.ts");
const P = cargar("lib/planningReport.ts", {
  componentesDelPL: T.componentesDelPL,
  OPERANDOS_DE_LA_CASCADA: T.OPERANDOS_DE_LA_CASCADA,
  resultadosDelPL: T.resultadosDelPL,
  rotuloAmbito: T.rotuloAmbito,
  suma: T.suma,
});

let fallos = 0;
let checks = 0;
function ok(cond, que) {
  checks++;
  if (!cond) { fallos++; console.log(`  ✗ ${que}`); }
}
const CENT = 0.011;

/* ── Datos sintéticos ───────────────────────────────────────────────────── */

const SID = ["s0", "s1", "s2"];
const ESCENARIOS = SID.map((id, i) => ({
  id, type: "BUDGET", version: ["Working", "Final", "Draft"][i], year: 2027 - i,
}));
/** Doce meses reproducibles y distintos entre sí: un mes que vale lo mismo que
 *  otro esconde justo el corrimiento que esto busca. */
const serie = (semilla) =>
  Array.from({ length: 12 }, (_, m) => Math.round((semilla * 131 + m * 97) % 977) + m);

/* ── 1 · Las columnas ───────────────────────────────────────────────────── */

for (const n of [1, 2, 3]) {
  const nombre = (vi) => `v${vi}`;
  const par = P.parPorDefecto(n);
  const cols = P.columnasPlanning(n, nombre, par);
  ok(cols.length === 1 + 12 + n + (par ? 1 : 0),
     `columnas con ${n} versiones: ${cols.length}`);
  ok(JSON.stringify(cols[13].suma_cols) === JSON.stringify([1,2,3,4,5,6,7,8,9,10,11,12]),
     `el año de la principal suma sus doce meses (${n} versiones)`);
  for (let vi = 1; vi < n; vi++) {
    ok(!cols[13 + vi].suma_cols,
       `el año de la versión comparada ${vi} NO lleva fórmula`);
  }
  if (par) {
    const v = cols[cols.length - 1];
    ok(v.resta[0] === 13 + par[0] && v.resta[1] === 13 + par[1],
       `la variación resta las columnas de AÑO (${n} versiones)`);
    ok(cols[v.resta[0]].label === "Full Year" && cols[v.resta[1]].label === "Full Year",
       `y las dos a las que apunta son columnas de año (${n} versiones)`);
  } else {
    ok(!cols.some(c => c.resta), "con una sola versión no hay variación");
  }
}

/** Que cada fórmula de un cuadro cuadre: `suma_de` contra las filas que nombra,
 *  `combina_filas` con su signo, `resta` y `suma_cols` contra las columnas. */
function auditar(cuadro, etiqueta) {
  const nCols = cuadro.columnas.length - 1;
  for (const f of cuadro.filas) {
    if (f.suma_de) {
      for (let j = 0; j < nCols; j++) {
        const esperado = f.suma_de.reduce(
          (t, i) => t + (typeof cuadro.filas[i].valores[j] === "number"
            ? cuadro.filas[i].valores[j] : 0), 0);
        const real = typeof f.valores[j] === "number" ? f.valores[j] : 0;
        ok(Math.abs(esperado - real) < CENT,
           `${etiqueta} · «${f.label}» col ${j}: suma_de da ${esperado}, la fila dice ${real}`);
      }
      // Y que no se sume a sí misma ni a otro subtotal por accidente: contar dos
      // veces cuadra igual de bien con el número equivocado.
      ok(!f.suma_de.includes(cuadro.filas.indexOf(f)),
         `${etiqueta} · «${f.label}» se suma a sí misma`);
    }
    if (f.combina_filas) {
      for (let j = 0; j < nCols; j++) {
        const esperado = f.combina_filas.reduce(
          (t, [i, s]) => t + s * (typeof cuadro.filas[i].valores[j] === "number"
            ? cuadro.filas[i].valores[j] : 0), 0);
        const real = typeof f.valores[j] === "number" ? f.valores[j] : 0;
        ok(Math.abs(esperado - real) < CENT,
           `${etiqueta} · «${f.label}» col ${j}: combina da ${esperado}, la fila dice ${real}`);
      }
    }
  }
  // La columna del año contra sus doce meses, fila por fila.
  const anio = cuadro.columnas.findIndex(c => c.suma_cols);
  for (const f of cuadro.filas) {
    const v = f.valores[anio - 1];
    if (typeof v !== "number") continue;
    const meses = f.valores.slice(0, 12);
    if (!meses.every(x => typeof x === "number")) continue;
    const s = meses.reduce((a, b) => a + b, 0);
    if (f.formato === "pct" || f.formato === "num1" || f.esRazon) continue;
    ok(Math.abs(s - v) < CENT,
       `${etiqueta} · «${f.label}»: el año dice ${v} y sus meses suman ${s}`);
  }
}

/* ── 2 · El P&L ─────────────────────────────────────────────────────────── */

const PL = {
  year: 2027,
  versiones: SID.slice(0, 2).map(id => ({ scenario_id: id, escenario: id })),
  filas: [
    { tipo: "sec", rotulo: "REVENUES", series: [null, null] },
    { tipo: "det", rotulo: "Rooms", series: [serie(1), serie(2)] },
    { tipo: "det", rotulo: "Food", series: [serie(3), serie(4)] },
    { tipo: "det", rotulo: "Vacía", series: [Array(12).fill(0), Array(12).fill(0)] },
  ],
};
for (const compacto of [false, true]) {
  const c = P.cuadroPlanning(PL, ESCENARIOS, { ambito: "hotel", compacto });
  auditar(c, `P&L compacto=${compacto}`);
  ok(c.filas.length === (compacto ? 3 : 4),
     `el modo compacto saca la fila en cero (${c.filas.length} filas)`);
  ok(c.filas[0].valores.every(v => v === null),
     "el encabezado de sección va SIN números, no en cero");
}

/* ── 3 · Las aperturas ──────────────────────────────────────────────────── */

const GASTOS = SID.map((id, vi) => ({
  scenario_id: id, type: "BUDGET", version: "v", year: 2027,
  meses: [], nombres_cuenta: { 8040: "DEPRECIATION" },
  detalle: {
    opex: { "0110": serie(10 + vi), "0260": serie(20 + vi), "0999": Array(12).fill(0) },
    property: { 8040: serie(30 + vi) },
    revenue: { ROOMS: serie(40 + vi) },
  },
}));
const DEPTOS = { "0110": "Habitaciones", "0260": "Club Madresal" };
for (const compacto of [false, true]) {
  const c = P.cuadroApertura("opex", GASTOS, DEPTOS, ESCENARIOS, { ambito: "", compacto });
  auditar(c, `apertura opex compacto=${compacto}`);
  const total = c.filas[c.filas.length - 1];
  ok(total.es_total && total.suma_de.length === c.filas.length - 1,
     "el TOTAL de la apertura suma TODAS las filas que se ven");
  ok(c.filas.length === (compacto ? 3 : 4),
     `la apertura esconde la clave en cero (${c.filas.length} filas)`);
  ok(c.filas[0].label.startsWith("0110 ") || c.filas[0].label.startsWith("0260 "),
     "la fila lleva el código y el nombre del departamento");
}
const prop = P.cuadroApertura("property", GASTOS, DEPTOS, ESCENARIOS,
                              { ambito: "", compacto: true });
ok(prop.filas[0].label === "8040 · DEPRECIATION",
   `el gasto de propiedad se rotula con el NOMBRE de la cuenta: «${prop.filas[0].label}»`);

/* ── 4 · Los checkbooks ─────────────────────────────────────────────────── */
//
// Dos departamentos con dos cuentas cada uno, más una cuenta en cero: es el caso
// que corre los ordinales cuando el modo compacto la saca.

const DET = {
  clase: "opex", clave: "", rotulo: "Total Operating Expenses",
  versiones: SID.slice(0, 2).map(id => ({ scenario_id: id, escenario: id, fuente: "Auxiliar" })),
  filas: [
    { dept_code: "0110", dept_name: "Habitaciones", cuenta: "7065", nombre: "CLEANING",
      series: { s0: serie(51), s1: serie(52) } },
    { dept_code: "0110", dept_name: "Habitaciones", cuenta: "7350", nombre: "LINEN",
      series: { s0: serie(53), s1: serie(54) } },
    { dept_code: "0110", dept_name: "Habitaciones", cuenta: "7999", nombre: "VACÍA",
      series: { s0: Array(12).fill(0), s1: Array(12).fill(0) } },
    { dept_code: "0260", dept_name: "Club", cuenta: "7065", nombre: "CLEANING",
      series: { s0: serie(55), s1: serie(56) } },
  ],
};
for (const compacto of [false, true]) {
  const c = P.cuadroCheckbook(DET, ESCENARIOS, { ambito: "", compacto });
  auditar(c, `checkbook compacto=${compacto}`);
  const total = c.filas[c.filas.length - 1];
  const subs = c.filas
    .map((f, i) => [f, i])
    .filter(([f]) => f.es_total && f.label.startsWith("Total "))
    .map(([, i]) => i);
  ok(JSON.stringify(total.suma_de) === JSON.stringify(subs),
     "⚠️ el TOTAL suma los SUBTOTALES de departamento, no las cuentas");
  ok(subs.length === 2, `un subtotal por departamento (${subs.length})`);
  // La 7065 de Habitaciones y la 7065 del Club son dos filas, no una.
  const setenta = c.filas.filter(f => f.label.startsWith("7065 "));
  ok(setenta.length === 2,
     `la misma cuenta en dos departamentos son DOS filas (${setenta.length})`);
}
// Y el caso que de verdad corre los ordinales: la cuenta escondida está en el
// MEDIO del primer departamento.
const comp = P.cuadroCheckbook(DET, ESCENARIOS, { ambito: "", compacto: true });
ok(!comp.filas.some(f => f.label.startsWith("7999")),
   "el modo compacto saca la cuenta en cero del medio");

/* ── 5 · Las estadísticas ───────────────────────────────────────────────── */
//
// ⚠️ El año de una RAZÓN no es la suma de los doce meses. Acá se le dan al
// constructor doce ocupaciones del 50% y un año del 50%: si alguien lo hiciera
// sumar, el año saldría 600%.

const mes = (m) => ({
  year: 2027, escenario: "s0", desde: m, hasta: m,
  rooms_available: 100, rooms_occupied: 50, guests: 80,
  occupancy_pct: 0.5, rooms_revenue: 1000 + m, adr: 20, revpar: 10,
  revpar_bruto: 12, club_pagando: 100, club_revenue: 500, club_cuota_promedio: 5,
});
const EST = {
  meses: Array.from({ length: 12 }, (_, i) => mes(i + 1)),
  anios: [{ ...mes(1), desde: 1, hasta: 12, rooms_available: 1200,
            rooms_occupied: 600, guests: 960,
            rooms_revenue: Array.from({ length: 12 }, (_, i) => 1000 + i + 1)
              .reduce((a, b) => a + b, 0) }],
  versiones: [{ scenario_id: "s0", escenario: "s0" }],
};
const ce = P.cuadroEstadisticas(EST, ESCENARIOS, { ambito: "", compacto: false });
const porRotulo = Object.fromEntries(ce.filas.map(f => [f.label, f]));
ok(porRotulo["Ocupación %"].valores[12] === 0.5,
   `⚠️ la ocupación del AÑO viene del servidor, no de sumar: `
   + `${porRotulo["Ocupación %"].valores[12]}`);
ok(porRotulo["ADR"].valores[12] === 20, "el ADR del año tampoco se suma");
ok(porRotulo["Noches disponibles"].valores[12] === 1200,
   "las noches del año sí son el total del período");
ok(Math.abs(porRotulo["Ingreso de habitaciones"].valores[12]
            - porRotulo["Ingreso de habitaciones"].valores.slice(0, 12)
                .reduce((a, b) => a + b, 0)) < CENT,
   "el ingreso del año SÍ coincide con la suma de sus meses");
ok(porRotulo["Ocupación %"].formato === "pct", "la ocupación se mira como porcentaje");

// Una propiedad sin Club: las filas de Club no se dibujan en modo compacto.
const sinClub = { ...EST, anios: [{ ...EST.anios[0], club_pagando: null,
                                    club_revenue: null, club_cuota_promedio: null }] };
const ceSin = P.cuadroEstadisticas(sinClub, ESCENARIOS, { ambito: "", compacto: true });
ok(!ceSin.filas.some(f => f.label.startsWith("Club")),
   "sin Club, no hay filas de Club: `null` no es cero socios");

/* ── Cierre ─────────────────────────────────────────────────────────────── */

console.log(`${checks} comprobaciones · ${fallos} fallos`);
process.exit(fallos ? 1 : 0);
