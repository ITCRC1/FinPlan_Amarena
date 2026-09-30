"use client";
/**
 * Las estadísticas del cierre, UNA COLUMNA POR VERSIÓN.
 *
 * Owner, 2026-09-02: *«ponlo en todos los sub tabs, ya que es información
 * básica»*, *«ocupo que me derives el ADR y precio cobro promedio de
 * membresías»* y, mostrando el cuadro de P&L Detail, *«esta vista me gustaría
 * verla en casi todos los tabs»*.
 *
 * **Los rótulos son los MISMOS que en P&L Detail**, a propósito y en inglés.
 * Este cuadro lo van a ver los dueños, y ver «Total Rooms Occupied» en un
 * reporte y «Hab. ocupadas» en otro para el mismo número obliga a comprobar que
 * son lo mismo. Se copian los siete de allá y se agregan los dos del Club.
 *
 * **Se dibuja UNA vez, arriba de los sub-tabs, no una copia adentro de cada
 * uno.** El pedido era verla en todos; quince copias serían quince lugares
 * donde arreglar el día que cambie un cálculo, y bastaría olvidar una para que
 * dos sub-tabs muestren ocupaciones distintas del mismo mes.
 *
 * **Los TRES cortes a la vez.** Owner, 2026-09-29: *«si pero sólo para el mes,
 * yo quiero que tenga YTD y Full year también»*. La franja seguía el selector
 * de arriba y mostraba uno solo, así que para comparar el mes contra el año
 * había que cambiar el selector y perder de vista el anterior — que es
 * justamente la comparación que se hace en el cierre.
 *
 * ⚠️ Los cortes salen de `cortesDe`, el MISMO que arma el cuadro de abajo. Si
 * la franja definiera los suyos, un día el encabezado y el reporte estarían
 * mirando meses distintos y ninguno de los dos números se vería raro.
 *
 * **No calcula el corte.** Mes, YTD y año los agrega el backend en
 * `/pl/{id}/estadisticas/`, porque la ocupación, el ADR y la cuota **no son
 * aditivos**: se rederivan con el numerador y el denominador del período. Un
 * promedio simple de doce meses le daría el mismo peso a un mes lleno que a uno
 * cerrado, y Amarena tiene cinco meses sin operación.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { type EstadisticasCierre, type Scenario } from "@/lib/api";
import {
  ANCHO_DATO, ANCHO_ROTULO, cortesDe, estadisticasDeLosCortes, parDe, vistaDe,
} from "@/lib/tresCortes";

const num = (n: number | null | undefined) =>
  n === null || n === undefined || !n ? "—"
    : n.toLocaleString("en-US", { maximumFractionDigits: 0 });
const usd = (n: number | null | undefined) =>
  n === null || n === undefined || Math.abs(n) < 0.005 ? "—"
    : "$" + n.toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (n: number | null | undefined) =>
  !n ? "—" : (n * 100).toFixed(2) + "%";

const TD: React.CSSProperties = {
  padding: "4px 14px", textAlign: "right", fontSize: 12.5,
  whiteSpace: "nowrap", fontWeight: 600,
};
/** ⚠️ `position: static` pisa el `thead th { position: sticky }` que
 *  `globals.css` le pone a TODA tabla de la app.
 *
 *  Ese sticky existe para los cuadros largos —que la fila de meses siga
 *  visible al bajar cien líneas—. Acá son NUEVE filas: no hay nada que
 *  seguir, y en cambio el encabezado se despegaba y quedaba flotando sobre
 *  el reporte de abajo. Owner, 2026-09-03: «se ve enganchada arriba». */
const TH_ESTATICO: React.CSSProperties = { position: "static" };
/** La raya que separa un corte del siguiente. */
const BL = "2px solid var(--border-medium)";
const TDL: React.CSSProperties = {
  padding: "4px 12px", fontSize: 12.5, whiteSpace: "nowrap",
  color: "var(--text-secondary)",
};

/** Las filas del cuadro. `valor` saca el dato de una versión ya cargada.
 *
 *  ⚠️ `Average Daily Room Only` usa **`adr`** —el de las estadísticas del
 *  escenario— y NO el derivado del ingreso, que es lo contrario de lo que
 *  parecía razonable al principio.
 *
 *  Owner, 2026-09-02: *«puedes recalcular el ADR de Julio dejando por fuera
 *  esos 2500»*. `REV_ROOMS` consolida cuentas que no son noche vendida: en
 *  julio de Amarena, dentro de los $36.218,36 hay $2.500 de «Otros ingresos de
 *  operación» y $0,02 de sobrantes de caja. Derivar sobre el total da $274,38
 *  donde la tarifa real es $255,44 — y un ADR no tiene contra qué cuadrar, así
 *  que el error no se nota.
 *
 *  El derivado sigue viajando y se avisa abajo cuando difieren, para que la
 *  diferencia se pueda explicar en vez de descubrirse. */
const FILAS: {
  rotulo: string;
  valor: (d: EstadisticasCierre) => string;
  /** El número crudo, para poder RESTAR dos versiones. `valor` ya viene
   *  formateado y de un texto no se saca una diferencia. */
  crudo?: (d: EstadisticasCierre) => number | null;
  /** Cómo se escribe la diferencia. Un punto porcentual no es un dólar. */
  dif?: (n: number) => string;
  club?: boolean;
  fuerte?: boolean;
}[] = [
  { rotulo: "Total available Rooms", valor: d => num(d.rooms_available),
    crudo: d => d.rooms_available, dif: num },
  { rotulo: "Total Rooms Occupied", valor: d => num(d.rooms_occupied),
    crudo: d => d.rooms_occupied, dif: num },
  { rotulo: "Total Guests", valor: d => num(d.guests),
    crudo: d => d.guests, dif: num },
  { rotulo: "% Occupancy", valor: d => pct(d.occupancy_pct), fuerte: true,
    crudo: d => d.occupancy_pct,
    // ⚠️ Puntos porcentuales, no un porcentaje: la diferencia entre 40,73 %
    // y 25,00 % es 15,73 **pp**, y escribirla con `%` invita a leerla como
    // un crecimiento del 15,73 %, que es otra cosa.
    dif: n => (n * 100).toFixed(2) + "pp" },
  { rotulo: "Average Daily Room Only", valor: d => usd(d.adr), fuerte: true,
    crudo: d => d.adr, dif: usd },
  { rotulo: "Total RevPAR", valor: d => usd(d.revpar), fuerte: true,
    crudo: d => d.revpar, dif: usd },
  // El promedio de los meses con socios (owner, 2026-09-02). En un mes suelto
  // es el mes; en un YTD, el promedio — nunca la suma, que daría 516 donde hay
  // 72.
  { rotulo: "Socios pagando (Club)", club: true,
    valor: d => (d.club_meses_con_socios ?? 0) > 1
      ? `${num(d.club_pagando)} prom.` : num(d.club_pagando),
    crudo: d => d.club_pagando, dif: num },
  { rotulo: "Socios al cierre del mes", club: true,
    valor: d => num(d.club_pagando_cierre),
    crudo: d => d.club_pagando_cierre, dif: num },
  { rotulo: "Cuota promedio por socio", valor: d => usd(d.club_cuota_promedio),
    club: true, fuerte: true,
    crudo: d => d.club_cuota_promedio, dif: usd },
];

export default function Estadisticas({ scenarioIds, etiquetas, mes, anio,
                                      visibles, actualDelFullYear = "",
                                      escenarios = [] }: {
  /** Las versiones que se PIDEN, en su orden. Las vacías se ignoran.
   *
   *  ⚠️ No es lo mismo que las columnas: el Forecast Current viaja acá aunque
   *  no esté en ninguna ranura, porque es quien ocupa la primera columna del
   *  año completo. Ver `visibles`. */
  scenarioIds: string[];
  etiquetas: string[];
  /** El mes del cierre: define el corte «mes» y hasta dónde llega el YTD. */
  mes: number;
  /** El año, para que el rótulo diga «Agosto 2026» y no sólo «Agosto». El
   *  cuadro de abajo ya lo dice, y dos encabezados pegados que no coinciden se
   *  leen como dos períodos distintos. */
  anio?: number;
  /** Los ids que SON columna, en orden. Sin esto, todos los pedidos.
   *
   *  ⚠️ **Es lo que separa «se pide» de «se ve».** Sin esta lista, el Forecast
   *  Current volvería a aparecer como una columna más en los tres cortes. */
  visibles?: string[];
  /** Quién ocupa la primera columna del año completo: el Forecast Current.
   *
   *  ⚠️ **Sin esto la franja muestra el ACTUAL en el año completo** y el cuadro
   *  de abajo el Forecast — el mismo encabezado, en la misma pantalla,
   *  contestando dos cosas distintas. Owner, 2026-09-30, con las dos capturas:
   *  *«es full year pero esta versión dice Actual Final 2026; en realidad acá
   *  debe estar tal cual está en la vista de cierre»*. La franja decía 539
   *  noches —los ocho meses cargados— y la tabla 1.199, los doce del
   *  forecast. */
  actualDelFullYear?: string;
  /** Para saber qué par se resta en cada corte. ⚠️ El tipo sale de acá y no
   *  del rótulo: el rótulo es texto libre. Sin esto la franja no puede llevar
   *  su columna de varianza, y sin ella nunca cuadra con el cuadro de abajo,
   *  que sí la tiene. */
  escenarios?: Scenario[];
}) {
  /** Por corte × versión. */
  const [datos, setDatos] = useState<(EstadisticasCierre | null)[][]>([]);
  const [error, setError] = useState<string | null>(null);

  const usadas = scenarioIds
    .map((id, i) => ({ id, rotulo: etiquetas[i] }))
    .filter(x => x.id);
  const clave = usadas.map(u => u.id).join(",");
  const cortes = useMemo(() => cortesDe(mes, anio), [mes, anio]);
  /** ⚠️ La MISMA regla que el cuadro de abajo (`parDe`): en el full year se
   *  resta Forecast contra Budget, no Actual. Si la franja restara otro par,
   *  las dos varianzas de la misma columna dirían cosas distintas. */
  const versiones = useMemo(
    () => usadas.map(u => ({ scenario_id: u.id })), [clave]);   // eslint-disable-line react-hooks/exhaustive-deps
  /** Qué versión cae en cada columna de cada corte.
   *
   *  ⚠️ **La MISMA `vistaDe` que el cuadro de abajo.** La franja repartía sus
   *  columnas por su cuenta —una por versión pedida, en orden— y en el año
   *  completo eso deja al Actual en la primera, que son los meses cargados y
   *  nada más. Con la vista, las dos tablas nombran y leen la misma versión en
   *  la misma columna. */
  const visto = (visibles ?? []).join(",");
  const vista = useMemo(
    () => vistaDe(versiones, visibles, actualDelFullYear, escenarios),
    [versiones, visto, actualDelFullYear, escenarios]);          // eslint-disable-line react-hooks/exhaustive-deps
  const parDeCorte = useCallback(
    (c: typeof cortes[number]) => parDe(c, versiones, escenarios, vista),
    [versiones, escenarios, vista]);

  const cargar = useCallback(async () => {
    const ids = clave ? clave.split(",") : [];
    if (!ids.length) { setDatos([]); return; }
    setError(null);
    try {
      setDatos(await estadisticasDeLosCortes(
        cortes, ids.map(id => ({ scenario_id: id }))));
    } catch (e) {
      setError(e instanceof Error ? e.message : "no se pudieron cargar");
      setDatos([]);
    }
  }, [clave, cortes]);

  useEffect(() => { cargar(); }, [cargar]);

  if (error) {
    return (
      <div style={{ fontSize: 11.5, color: "var(--negative)", marginBottom: 10 }}>
        Estadísticas: {error}
      </div>
    );
  }
  const vivas = datos.flat().filter(Boolean) as EstadisticasCierre[];
  if (!vivas.length) return null;

  /** El Club sólo se dibuja si la propiedad lo tiene. Un cero se leería como
   *  «no hay socios» donde en realidad no hay Club. */
  const hayClub = vivas.some(d => d.club_pagando !== null);

  /** Aviso cuando las dos tarifas difieren: `REV_ROOMS` trae ingreso que no es
   *  noche vendida y la tarifa sale más alta sin que nada lo delate. */
  // ⚠️ Se mira SÓLO el corte del mes: con los tres, la misma versión saldría
  // tres veces en el aviso diciendo exactamente lo mismo.
  // ⚠️ Y sólo de las versiones que TIENEN columna: el Forecast Current viaja
  // sin columna propia, y nombrarlo acá señalaría algo que no está en pantalla.
  const brechas = vista.columnas
    .map((_c, col) => {
      const i = vista.vi(col, 0);
      const d = datos[0]?.[i] ?? null;
      return { e: usadas[i]?.rotulo || "", dif: d ? d.adr_derivado - d.adr : 0 };
    })
    .filter(x => Math.abs(x.dif) >= 0.01);

  return (
    <div style={{ marginBottom: 16 }}>
      <div className="fin-scroll-x">
        {/* ⚠️ `table-layout: fixed` + `colgroup`: es lo que hace que el
            navegador OBEDEZCA los anchos en vez de estirar la columna del texto
            más largo. Sin eso, esta tabla y la de abajo quedan corridas aunque
            tengan las mismas columnas — y corridas se leen como una sola, con
            cada número bajo el encabezado del vecino. */}
        <table style={{ borderCollapse: "collapse", tableLayout: "fixed",
                        minWidth: ANCHO_ROTULO + cortes.reduce(
                          (a, c) => a + (vista.columnas.length
                            + (parDeCorte(c) ? 1 : 0)) * ANCHO_DATO, 0) }}>
          <colgroup>
            <col style={{ width: ANCHO_ROTULO }} />
            {cortes.flatMap((c, ci) => [
              ...vista.columnas.map((_col, i) => (
                <col key={`${c.clave}-${i}`} style={{ width: ANCHO_DATO }} />)),
              ...(parDeCorte(c)
                ? [<col key={`${c.clave}-v`} style={{ width: ANCHO_DATO }} />] : []),
            ])}
          </colgroup>
          <thead>
            <tr>
              <th style={{ ...TDL, ...TH_ESTATICO }} />
              {cortes.map((c, ci) => (
                <th key={c.clave}
                    colSpan={vista.columnas.length + (parDeCorte(c) ? 1 : 0)}
                    style={{ ...TD, ...TH_ESTATICO, textAlign: "center",
                             fontWeight: 800, color: "var(--brand)",
                             borderLeft: ci ? BL : undefined }}>
                  {c.titulo}
                </th>
              ))}
            </tr>
            <tr>
              <th style={{ ...TDL, ...TH_ESTATICO, textAlign: "left",
                           fontWeight: 800 }}>
                ESTADÍSTICAS
              </th>
              {cortes.flatMap((c, ci) => [
                // ⚠️ El rótulo sale de la VISTA, no de `usadas[i]`: en el año
                // completo la primera columna es el Forecast Current, y con el
                // rótulo de la ranura diría «ACTUAL Final» encima de doce meses
                // de forecast.
                ...vista.columnas.map((_col, i) => (
                  <th key={c.clave + i}
                      style={{ ...TD, ...TH_ESTATICO, fontWeight: 700,
                               color: "var(--text-secondary)",
                               borderLeft: ci && !i ? BL : undefined }}>
                    {usadas[vista.vi(i, ci)]?.rotulo || ""}
                  </th>
                )),
                ...(parDeCorte(c) ? [
                  <th key={c.clave + "-var"}
                      style={{ ...TD, ...TH_ESTATICO, fontWeight: 700,
                               fontStyle: "italic",
                               color: "var(--text-secondary)" }}>
                    Var
                  </th>] : []),
              ])}
            </tr>
          </thead>
          <tbody>
            {FILAS.filter(f => !f.club || hayClub).map((f, n) => (
              <tr key={f.rotulo}
                  style={{ background: n % 2 ? "transparent" : "var(--bg-surface)" }}>
                <td style={TDL}>{f.rotulo}</td>
                {cortes.flatMap((c, ci) => {
                  const par = parDeCorte(c);
                  const celdas = vista.columnas.map((_col, i) => {
                    const d = datos[ci]?.[vista.vi(i, ci)] ?? null;
                    return (
                      <td key={c.clave + i}
                          style={{ ...TD, fontWeight: f.fuerte ? 800 : 600,
                                   borderLeft: ci && !i ? BL : undefined }}>
                        {d ? f.valor(d) : "—"}
                      </td>
                    );
                  });
                  if (!par) return celdas;
                  // ⚠️ La diferencia sale de los números CRUDOS, no del texto
                  // ya formateado. Y va vacía si a alguno de los dos le falta:
                  // restar de la nada daría el valor entero disfrazado de
                  // variación.
                  const xa = f.crudo && datos[ci]?.[par[0]]
                    ? f.crudo(datos[ci]![par[0]]!) : null;
                  const xb = f.crudo && datos[ci]?.[par[1]]
                    ? f.crudo(datos[ci]![par[1]]!) : null;
                  const v = xa === null || xb === null ? null : xa - xb;
                  return [...celdas, (
                    <td key={c.clave + "-var"}
                        style={{ ...TD, fontStyle: "italic",
                                 fontWeight: f.fuerte ? 800 : 600,
                                 color: v === null || Math.abs(v) < 1e-9
                                   ? "var(--text-disabled)" : undefined }}>
                      {v === null ? "" : (f.dif ?? num)(v)}
                    </td>
                  )];
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {brechas.length > 0 && (
        <div style={{ fontSize: 11, lineHeight: 1.55, marginTop: 6,
                      color: "var(--text-secondary)", maxWidth: 820 }}>
          ⚠️ <b>Average Daily Room Only</b> es la tarifa por noche vendida.
          Dividir TODO el ingreso de habitaciones entre las noches ocupadas
          daría más alto, porque ese total incluye cuentas que no son noche
          vendida —otros ingresos de operación, sobrantes de caja—:{" "}
          {brechas.map(b => `${b.e} daría +${usd(Math.abs(b.dif))}`).join(" · ")}.
        </div>
      )}
    </div>
  );
}
