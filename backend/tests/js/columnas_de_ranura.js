/**
 * ¿La fórmula apunta a la columna que de verdad tiene ese valor?
 *
 * Se arma la fila EXACTAMENTE como la arma la pantalla (`enOrden` para los
 * cuadros partidos, y la lista llana para los de variación al final), se marca
 * cada celda con la ranura que la llenó, y se comprueba que el índice que
 * devuelve la librería caiga sobre esa marca. Para TODAS las combinaciones de
 * ranuras ocupadas y TODOS los pares comparados.
 *
 * `tsc` no ve este error: los índices son números y todos tipan.
 */
const fs = require("fs");
const path = require("path");
// La raiz del frontend, relativa a este archivo: backend/tests/js -> frontend
const RAIZ = path.resolve(__dirname, "../../../frontend");
const ts = require(path.join(RAIZ, "node_modules/typescript"));

function cargar(rel) {
  let src = fs.readFileSync(path.join(RAIZ, rel), "utf8");
  src = src.replace(/^import[\s\S]*?from\s+"[^"]+";\s*$/gm, "");
  const js = ts.transpileModule(src, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", "require", js)(mod, mod.exports, require);
  return mod.exports;
}

const L = cargar("lib/columnasDeRanura.ts");
let casos = 0, malos = 0;

// Todas las combinaciones no vacías de las cuatro ranuras.
for (let mascara = 1; mascara < 16; mascara++) {
  const usadas = [];
  for (let i = 0; i < 4; i++) if (mascara & (1 << i)) usadas.push({ i, id: `s${i}` });
  for (const a of usadas) for (const b of usadas) {
    if (a.i === b.i) continue;
    const varA = a.i, varB = b.i;
    const trasVariacion = L.trasVariacionDe(usadas, varA, varB);

    // ── 1. El cuadro PARTIDO, tal como lo arma `enOrden` ──────────────────
    // [rótulo, ...usadas<T, Var$, Var%, ...usadas>=T]
    const fila = ["ROTULO",
      ...usadas.slice(0, trasVariacion).map(u => `r${u.i}`),
      "VAR$", "VAR%",
      ...usadas.slice(trasVariacion).map(u => `r${u.i}`)];
    for (const r of [varA, varB]) {
      casos++;
      const c = L.colDeRanuraPartida(usadas, trasVariacion, r);
      if (c === null || fila[c] !== `r${r}`) {
        malos++;
        console.log(`  ✗ partida  usadas=[${usadas.map(u => u.i)}] var=${varA}/${varB}`
          + ` ranura ${r} → col ${c} tiene «${fila[c]}», esperaba «r${r}»`);
      }
    }
    // La columna de variación tiene que estar DONDE la pantalla la pone.
    casos++;
    if (fila[1 + trasVariacion] !== "VAR$") {
      malos++;
      console.log(`  ✗ la Var $ no cayó en ${1 + trasVariacion}`);
    }

    // ── 2. El cuadro con la variación AL FINAL ────────────────────────────
    // [rótulo, ...usadas, Var$, Var%]
    const fila2 = ["ROTULO", ...usadas.map(u => `r${u.i}`), "VAR$", "VAR%"];
    for (const r of [varA, varB]) {
      casos++;
      const c = L.colDeRanuraAlFinal(usadas, r);
      if (c === null || fila2[c] !== `r${r}`) {
        malos++;
        console.log(`  ✗ al final  usadas=[${usadas.map(u => u.i)}] ranura ${r}`
          + ` → col ${c} tiene «${fila2[c]}»`);
      }
    }
  }
}

// Una ranura que NO está en uso no tiene columna: hay que decir `null`, no 0.
casos++;
if (L.colDeRanuraPartida([{ i: 0 }], 1, 3) !== null
    || L.colDeRanuraAlFinal([{ i: 0 }], 3) !== null) {
  malos++;
  console.log("  ✗ una ranura vacía devolvió una columna");
}

console.log(malos
  ? `\n${malos} FALLA(S) de ${casos} comprobaciones`
  : `\nOK — ${casos} comprobaciones, la fórmula siempre apunta a su columna`);
process.exit(malos ? 1 : 0);
