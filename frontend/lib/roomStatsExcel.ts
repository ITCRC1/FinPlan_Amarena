import type { AnioMes, AnioMesCanal, AnioRoomStats } from "@/lib/api";
import type { ColumnaCuadro, Cuadro, FilaCuadro, FormatoCol } from "@/lib/exportCuadro";

/**
 * El año entero de estadística del PMS, en un solo Excel.
 *
 * Owner, 2026-09-11: *«como se podria construir un excel donde se pueda bajar
 * todo esta informacion por mes, un tab por mes, con todos los sub tabs y uno
 * final donde este consolidado y se vaya actualizando conforme se van
 * agregando mas meses»*.
 *
 * ## Una hoja por mes trae las TRES vistas, no una
 *
 * En la pantalla «Por canal», «Por habitación» y «Canal × habitación» son tres
 * cuadros. En Excel una hoja es UNA tabla, así que copiarlos tal cual pedía
 * tres hojas por mes — 18 pestañas para seis meses, que es justo lo que el
 * pedido evita.
 *
 * No hacen falta tres: **la matriz las contiene a las dos**. Con los canales
 * en filas y las categorías en columnas, sumar una fila da «Por canal»,
 * sumar una columna da «Por habitación», y la celda es «Canal × habitación».
 * Acá esa matriz se abre en bloques —noches, pax, ingreso, ADR— para que cada
 * bloque tenga una sola unidad y se pueda sumar sin pensar.
 *
 * ## Los números salen como número
 *
 * Nunca `"$1,234.00"` ya formateado. Un Excel con las cifras en texto no se
 * puede sumar ni graficar, que es exactamente para lo que se baja.
 *
 * ## ⚠️ Un mes sin cargar va en BLANCO, no en cero
 *
 * `null` deja la celda vacía. Un cero dice «ese mes el hotel no vendió» y es
 * una afirmación distinta de «todavía no subimos el archivo» — con el
 * acumulado a la vista, la diferencia cambia el ADR del año.
 *
 * ## ⚠️ El YTD de una TASA se recalcula, no se promedia
 *
 * El ADR del año es ingreso acumulado / noches acumuladas. Promediar los ADR
 * mensuales haría pesar igual a un mes de 20 noches y a uno de 202 — en
 * Amarena 2026 eso son $290 contra $255.
 */

const MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

/** noches, pax, ingreso. */
type T3 = [number, number, number];
const cero = (): T3 => [0, 0, 0];
const mas = (a: T3, b: T3): T3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const adr = (v: T3) => (v[0] ? v[2] / v[0] : 0);

/** ¿Este código del PMS entra a la base de los indicadores? */
export type Dentro = (c: { canal_code: string; cuenta_para_kpis: boolean }) => boolean;

/** Los códigos que aparecen en el año, en orden estable y sin repetir. */
function codigosDelAnio(anio: AnioRoomStats): AnioMesCanal[] {
  const vistos = new Map<string, AnioMesCanal>();
  anio.meses.forEach(m => m.canales.forEach(c => {
    if (!vistos.has(c.canal_code)) vistos.set(c.canal_code, c);
  }));
  return [...vistos.values()];
}

/** El rótulo de un canal dice si quedó fuera de la base. Sin esto, la hoja
 *  suelta no explica por qué el TOTAL no es la suma de las filas. */
const rotulo = (c: AnioMesCanal, dentro: Dentro) =>
  dentro(c) ? c.canal_code : `${c.canal_code} · fuera de la base`;

/* ══════════════════════════ Una hoja por mes ═════════════════════════════ */

function hojaDelMes(
  anio: AnioRoomStats, m: AnioMes, dentro: Dentro,
): Cuadro {
  const cats = anio.room_types.map(r => r.name);
  const canales = codigosDelAnio(anio)
    .filter(c => m.canales.some(x => x.canal_code === c.canal_code));

  /** Lo que un canal hizo en una categoría ese mes. */
  const cel = (code: string, cat: string): T3 => m.canales
    .filter(x => x.canal_code === code && x.room_type_name === cat)
    .reduce<T3>((a, x) => mas(a, [x.nights_occupied, x.pax, x.revenue]), cero());

  /** La columna de una categoría, sumando los canales que se le pidan. */
  const col = (cat: string, filtro: (c: AnioMesCanal) => boolean): T3 =>
    canales.filter(filtro).reduce<T3>((a, c) => mas(a, cel(c.canal_code, cat)), cero());

  const base = cats.map(cat => col(cat, c => dentro(c)));
  const todo = cats.map(cat => col(cat, () => true));
  const baseTot = base.reduce(mas, cero());
  const todoTot = todo.reduce(mas, cero());

  const filas: FilaCuadro[] = [];
  const vacias = cats.map(() => null).concat([null]);
  const banda = (t: string) => filas.push({ label: t, es_total: true, valores: vacias });

  /** Un bloque = una unidad. Noches, pax e ingreso se suman; el ADR no. */
  const bloque = (titulo: string, i: 0 | 1 | 2, formato: FormatoCol) => {
    banda(titulo);
    canales.forEach(c => {
      const v = cats.map(cat => cel(c.canal_code, cat)[i]);
      filas.push({ label: rotulo(c, dentro), nivel: 1, formato,
                   valores: [...v, v.reduce((a, x) => a + x, 0)] });
    });
    filas.push({ label: "TOTAL (base de indicadores)", es_total: true, formato,
                 valores: [...base.map(v => v[i]), baseTot[i]] });
    if (canales.some(c => !dentro(c))) {
      filas.push({ label: "Con todos los canales (PDF)", nivel: 1, formato,
                   valores: [...todo.map(v => v[i]), todoTot[i]] });
    }
  };

  bloque("NOCHES OCUPADAS", 0, "num");
  bloque("PAX", 1, "num");
  bloque("INGRESO", 2, "usd2");

  // El ADR no se suma: se recalcula en cada celda.
  banda("ADR");
  canales.forEach(c => {
    const v = cats.map(cat => adr(cel(c.canal_code, cat)));
    const t = cats.reduce<T3>((a, cat) => mas(a, cel(c.canal_code, cat)), cero());
    filas.push({ label: rotulo(c, dentro), nivel: 1, formato: "usd2",
                 valores: [...v, adr(t)] });
  });
  filas.push({ label: "TOTAL (base de indicadores)", es_total: true, formato: "usd2",
               valores: [...base.map(adr), adr(baseTot)] });
  if (canales.some(c => !dentro(c))) {
    filas.push({ label: "Con todos los canales (PDF)", nivel: 1, formato: "usd2",
                 valores: [...todo.map(adr), adr(todoTot)] });
  }

  // El inventario no tiene apertura por canal: es del hotel, no de quien vendió.
  const disp = cats.map(cat => m.categorias
    .filter(c => c.room_type_name === cat)
    .reduce((a, c) => a + c.nights_available, 0));
  const dispTot = disp.reduce((a, v) => a + v, 0);
  banda("INVENTARIO E INDICADORES");
  filas.push({ label: "Noches disponibles", nivel: 1, formato: "num",
               valores: [...disp, dispTot] });
  filas.push({ label: "% Ocupación", nivel: 1, formato: "pct",
               valores: [...base.map((v, i) => disp[i] ? v[0] / disp[i] : null),
                         dispTot ? baseTot[0] / dispTot : null] });
  filas.push({ label: "RevPAR", nivel: 1, formato: "usd2",
               valores: [...base.map((v, i) => disp[i] ? v[2] / disp[i] : null),
                         dispTot ? baseTot[2] / dispTot : null] });

  const columnas: ColumnaCuadro[] = [
    { label: "Canal", ancho: 34, formato: "texto" },
    ...cats.map(c => ({ label: c, ancho: 20, formato: "num" as FormatoCol })),
    { label: "TOTAL", ancho: 18, formato: "num" },
  ];

  return {
    titulo: `${MESES[m.month - 1]} ${anio.year} · Estadística de habitaciones`,
    subtitulo: `${anio.escenario} · canales en filas, categorías en columnas —`
      + ` sumar una fila da «Por canal», sumar una columna da «Por habitación»`,
    hoja: `${MES3[m.month - 1]} ${anio.year}`,
    columnas, filas,
  };
}

/* ═══════════════════════ La hoja consolidada ═════════════════════════════ */

function hojaAcumulada(anio: AnioRoomStats, dentro: Dentro): Cuadro {
  const cats = anio.room_types.map(r => r.name);
  const canales = codigosDelAnio(anio);
  const cargados = anio.meses.filter(m => m.cargado);
  const ultimo = cargados.length ? cargados[cargados.length - 1].month : 0;

  /** ⚠️ `null` para el mes que no está: el blanco dice «no lo sabemos» y el
   *  cero diría «no hubo». Con doce columnas a la vista, no es lo mismo. */
  const porMes = <T,>(f: (m: AnioMes) => T) =>
    anio.meses.map(m => (m.cargado ? f(m) : null));

  const catDe = (m: AnioMes, cat: string): T3 => m.categorias
    .filter(c => c.room_type_name === cat)
    .reduce<T3>((a, c) => mas(a, [c.nights_occupied, c.pax, c.revenue]), cero());

  /** La base de una categoría sale de su apertura por canal. ⚠️ Sin apertura
   *  no se puede filtrar: se usa el total y no se descuenta «lo que suele ser
   *  cortesía», que sería inventar un número. */
  const baseCat = (m: AnioMes, cat: string): T3 => {
    const abre = m.canales.filter(c => c.room_type_name === cat);
    return abre.length
      ? abre.reduce<T3>((a, c) => dentro(c) ? mas(a, [c.nights_occupied, c.pax, c.revenue]) : a, cero())
      : catDe(m, cat);
  };
  const baseMes = (m: AnioMes): T3 => m.canales.length
    ? m.canales.reduce<T3>((a, c) => dentro(c) ? mas(a, [c.nights_occupied, c.pax, c.revenue]) : a, cero())
    : m.categorias.reduce<T3>((a, c) => mas(a, [c.nights_occupied, c.pax, c.revenue]), cero());
  const todoMes = (m: AnioMes): T3 => m.categorias
    .reduce<T3>((a, c) => mas(a, [c.nights_occupied, c.pax, c.revenue]), cero());
  const dispMes = (m: AnioMes) => m.categorias.reduce((a, c) => a + c.nights_available, 0);
  const canalMes = (m: AnioMes, code: string): T3 => m.canales
    .filter(c => c.canal_code === code)
    .reduce<T3>((a, c) => mas(a, [c.nights_occupied, c.pax, c.revenue]), cero());

  const ytd = (f: (m: AnioMes) => T3): T3 =>
    cargados.reduce<T3>((a, m) => mas(a, f(m)), cero());
  const ytdDisp = cargados.reduce((a, m) => a + dispMes(m), 0);

  const filas: FilaCuadro[] = [];
  const vacias = anio.meses.map(() => null).concat([null]);
  const banda = (t: string) => filas.push({ label: t, es_total: true, valores: vacias });

  /** Un bloque de doce meses + YTD para una medida que SE SUMA. */
  const suma = (label: string, f: (m: AnioMes) => T3, i: 0 | 1 | 2,
                formato: FormatoCol, nivel = 1, total = false) =>
    filas.push({ label, nivel, formato, es_total: total,
                 valores: [...porMes(m => f(m)[i]), ytd(f)[i]] });

  /** Igual, pero para una TASA. ⚠️ El YTD se recalcula sobre los acumulados,
   *  nunca promediando las doce celdas. */
  const tasa = (label: string, f: (m: AnioMes) => T3, i: 0 | 2,
                divisor: (m: AnioMes) => number, ytdDiv: number,
                formato: FormatoCol) =>
    filas.push({ label, nivel: 1, formato,
                 valores: [...porMes(m => { const d = divisor(m); return d ? f(m)[i] / d : null; }),
                           ytdDiv ? ytd(f)[i] / ytdDiv : null] });

  banda("NOCHES OCUPADAS · POR CATEGORÍA");
  cats.forEach(c => suma(c, m => baseCat(m, c), 0, "num"));
  suma("TOTAL", baseMes, 0, "num", 0, true);

  banda("INGRESO · POR CATEGORÍA");
  cats.forEach(c => suma(c, m => baseCat(m, c), 2, "usd2"));
  suma("TOTAL", baseMes, 2, "usd2", 0, true);

  banda("ADR · POR CATEGORÍA");
  cats.forEach(c => filas.push({
    label: c, nivel: 1, formato: "usd2",
    valores: [...porMes(m => adr(baseCat(m, c))), adr(ytd(m => baseCat(m, c)))],
  }));
  filas.push({ label: "TOTAL", es_total: true, formato: "usd2",
               valores: [...porMes(m => adr(baseMes(m))), adr(ytd(baseMes))] });

  if (canales.length) {
    banda("NOCHES OCUPADAS · POR CANAL");
    canales.forEach(c => suma(rotulo(c, dentro), m => canalMes(m, c.canal_code), 0, "num"));
    banda("INGRESO · POR CANAL");
    canales.forEach(c => suma(rotulo(c, dentro), m => canalMes(m, c.canal_code), 2, "usd2"));
  }

  banda("INDICADORES DEL HOTEL");
  filas.push({ label: "Noches disponibles", nivel: 1, formato: "num",
               valores: [...porMes(dispMes), ytdDisp] });
  suma("Noches ocupadas", baseMes, 0, "num");
  tasa("% Ocupación", baseMes, 0, dispMes, ytdDisp, "pct");
  suma("Ingreso", baseMes, 2, "usd2");
  filas.push({ label: "ADR", nivel: 1, formato: "usd2",
               valores: [...porMes(m => adr(baseMes(m))), adr(ytd(baseMes))] });
  tasa("RevPAR", baseMes, 2, dispMes, ytdDisp, "usd2");

  // La otra base, para cuadrar contra el PMS sin abrir la app.
  if (canales.some(c => !dentro(c))) {
    banda("CON TODOS LOS CANALES (PDF) · lo que dice el archivo");
    suma("Noches ocupadas", todoMes, 0, "num");
    suma("Ingreso", todoMes, 2, "usd2");
    filas.push({ label: "ADR", nivel: 1, formato: "usd2",
                 valores: [...porMes(m => adr(todoMes(m))), adr(ytd(todoMes))] });
  }

  const columnas: ColumnaCuadro[] = [
    { label: "Concepto", ancho: 38, formato: "texto" },
    ...anio.meses.map(m => ({ label: MES3[m.month - 1], ancho: 14,
                              formato: "num" as FormatoCol })),
    { label: ultimo ? `YTD ${MES3[ultimo - 1]}` : "YTD", ancho: 16, formato: "num" },
  ];

  return {
    titulo: `Acumulado ${anio.year} · Estadística de habitaciones`,
    subtitulo: `${anio.escenario} · ${cargados.length} mes(es) cargado(s)`
      + ` — las columnas en blanco son meses sin subir, no meses en cero`,
    hoja: `Acumulado ${anio.year}`,
    columnas, filas,
  };
}

/* ═════════════════════════════ La entrada ════════════════════════════════ */

/**
 * Las hojas del año: una por mes cargado, y el consolidado al final.
 *
 * Se arma con lo que la base tiene HOY, así que sumar un mes y volver a bajar
 * el archivo alcanza para que el consolidado lo incluya — no hay nada que
 * mantener en el Excel.
 */
export function cuadrosDelAnio(anio: AnioRoomStats, dentro: Dentro): Cuadro[] {
  const meses = anio.meses.filter(m => m.cargado);
  return [...meses.map(m => hojaDelMes(anio, m, dentro)), hojaAcumulada(anio, dentro)];
}
