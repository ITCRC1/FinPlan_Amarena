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

import { type EstadisticasCierre } from "@/lib/api";
import { cortesDe, estadisticasDeLosCortes } from "@/lib/tresCortes";

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
  club?: boolean;
  fuerte?: boolean;
}[] = [
  { rotulo: "Total available Rooms", valor: d => num(d.rooms_available) },
  { rotulo: "Total Rooms Occupied", valor: d => num(d.rooms_occupied) },
  { rotulo: "Total Guests", valor: d => num(d.guests) },
  { rotulo: "% Occupancy", valor: d => pct(d.occupancy_pct), fuerte: true },
  { rotulo: "Average Daily Room Only", valor: d => usd(d.adr), fuerte: true },
  { rotulo: "Total RevPAR", valor: d => usd(d.revpar), fuerte: true },
  // El promedio de los meses con socios (owner, 2026-09-02). En un mes suelto
  // es el mes; en un YTD, el promedio — nunca la suma, que daría 516 donde hay
  // 72.
  { rotulo: "Socios pagando (Club)", club: true,
    valor: d => (d.club_meses_con_socios ?? 0) > 1
      ? `${num(d.club_pagando)} prom.` : num(d.club_pagando) },
  { rotulo: "Socios al cierre del mes", club: true,
    valor: d => num(d.club_pagando_cierre) },
  { rotulo: "Cuota promedio por socio", valor: d => usd(d.club_cuota_promedio),
    club: true, fuerte: true },
];

export default function Estadisticas({ scenarioIds, etiquetas, mes }: {
  /** Las versiones elegidas arriba, en su orden. Las vacías se ignoran. */
  scenarioIds: string[];
  etiquetas: string[];
  /** El mes del cierre: define el corte «mes» y hasta dónde llega el YTD. */
  mes: number;
}) {
  /** Por corte × versión. */
  const [datos, setDatos] = useState<(EstadisticasCierre | null)[][]>([]);
  const [error, setError] = useState<string | null>(null);

  const usadas = scenarioIds
    .map((id, i) => ({ id, rotulo: etiquetas[i] }))
    .filter(x => x.id);
  const clave = usadas.map(u => u.id).join(",");
  const cortes = useMemo(() => cortesDe(mes), [mes]);

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
  const brechas = (datos[0] ?? [])
    .map((d, i) => ({ e: usadas[i]?.rotulo || "",
                      dif: d ? d.adr_derivado - d.adr : 0 }))
    .filter(x => Math.abs(x.dif) >= 0.01);

  return (
    <div style={{ marginBottom: 16 }}>
      <div className="fin-scroll-x">
        <table style={{ borderCollapse: "collapse", minWidth: 420 }}>
          <thead>
            <tr>
              <th style={{ ...TDL, ...TH_ESTATICO, minWidth: 220 }} />
              {cortes.map((c, ci) => (
                <th key={c.clave} colSpan={usadas.length}
                    style={{ ...TD, ...TH_ESTATICO, textAlign: "center",
                             fontWeight: 800, color: "var(--brand)",
                             borderLeft: ci ? BL : undefined }}>
                  {c.titulo}
                </th>
              ))}
            </tr>
            <tr>
              <th style={{ ...TDL, ...TH_ESTATICO, textAlign: "left",
                           fontWeight: 800, minWidth: 220 }}>
                ESTADÍSTICAS
              </th>
              {cortes.flatMap((c, ci) => usadas.map((u, i) => (
                <th key={c.clave + u.id + i}
                    style={{ ...TD, ...TH_ESTATICO, fontWeight: 700,
                             color: "var(--text-secondary)", minWidth: 130,
                             borderLeft: ci && !i ? BL : undefined }}>
                  {u.rotulo}
                </th>
              )))}
            </tr>
          </thead>
          <tbody>
            {FILAS.filter(f => !f.club || hayClub).map((f, n) => (
              <tr key={f.rotulo}
                  style={{ background: n % 2 ? "transparent" : "var(--bg-surface)" }}>
                <td style={TDL}>{f.rotulo}</td>
                {cortes.flatMap((c, ci) => usadas.map((_u, i) => {
                  const d = datos[ci]?.[i] ?? null;
                  return (
                    <td key={c.clave + i}
                        style={{ ...TD, fontWeight: f.fuerte ? 800 : 600,
                                 borderLeft: ci && !i ? BL : undefined }}>
                      {d ? f.valor(d) : "—"}
                    </td>
                  );
                }))}
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
