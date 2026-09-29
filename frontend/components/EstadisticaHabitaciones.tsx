"use client";
import { useEffect, useMemo, useState } from "react";

import { getAnioRoomStats, type AnioMes, type AnioRoomStats, type Scenario } from "@/lib/api";

/**
 * La estadística de habitaciones del PMS, al pie del Dashboard.
 *
 * Owner, 2026-09-28: *«puedes agregar al final de este dashboard información
 * sobre las estadísticas. una por tab del excel y con datos del mes, ytd, full
 * year. dependiente lo que se escoja en la vista»*.
 *
 * Los tabs del Excel de segmentación que mantiene la propiedad son ocho. Acá
 * hay un bloque por cada uno, con las tres columnas juntas —Mes, YTD y Full
 * Year— y las filas abiertas por categoría o por canal.
 *
 * ## Por qué las tres columnas a la vez
 *
 * El selector del Dashboard elige UNA vista, pero un dato de estadística sin
 * su acumulado no se puede leer: 202 noches en agosto dice algo distinto según
 * si el año lleva 300 o 3.000. Mostrar las tres juntas evita que alguien
 * compare el mes de una pantalla contra el YTD de otra.
 *
 * ## ⚠️ El Full Year de un ACTUAL es lo cargado, no doce meses
 *
 * Con seis meses subidos, «Full Year» son esos seis. No se dividen por doce ni
 * se proyectan: el cartel dice cuántos meses hay dentro.
 *
 * ## ⚠️ El YTD de una TASA se recalcula, nunca se promedia
 *
 * El ADR del período es ingreso acumulado / noches acumuladas. Promediar los
 * ADR mensuales haría pesar igual a un mes de 20 noches y a uno de 202 — en
 * Amarena 2026 son $306.83 contra los $286.13 reales.
 */

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

type Unidad = "usd" | "num";

/** Un bloque = un tab del Excel. `saca` lee la medida de una fila cualquiera
 *  —categoría o canal—, que traen los mismos nombres de campo. */
interface Bloque {
  clave: string;
  titulo: string;
  unidad: Unidad;
  /** `null` = es una tasa y se calcula aparte; no se suma. */
  saca: ((r: Medible) => number) | null;
  nota?: string;
}

interface Medible {
  nights_occupied: number; pax: number; revenue: number;
  ingreso_ayb?: number; ingreso_otros?: number;
  hab_entradas?: number; cli_entradas?: number;
}

const BLOQUES: Bloque[] = [
  { clave: "hospedaje", titulo: "Ing. Hospedaje", unidad: "usd",
    saca: r => r.revenue },
  { clave: "ayb", titulo: "Ing. A y B", unidad: "usd",
    saca: r => r.ingreso_ayb ?? 0,
    nota: "El reporte del PMS no abre los puntos de venta por agencia." },
  { clave: "otros", titulo: "Ing. Otros", unidad: "usd",
    saca: r => r.ingreso_otros ?? 0 },
  { clave: "habEnt", titulo: "Hab. Entradas", unidad: "num",
    saca: r => r.hab_entradas ?? 0, nota: "Llegadas, no noches." },
  { clave: "habEst", titulo: "Hab. Estancias", unidad: "num",
    saca: r => r.nights_occupied, nota: "Noches ocupadas." },
  { clave: "cliEnt", titulo: "Clientes Entradas", unidad: "num",
    saca: r => r.cli_entradas ?? 0 },
  { clave: "cliEst", titulo: "Clientes Estancias", unidad: "num",
    saca: r => r.pax, nota: "Noches-huésped: es el «pax» del Room Stats." },
  { clave: "tarifa", titulo: "Tarifa Promedio", unidad: "usd", saca: null,
    nota: "Ingreso ÷ noches. El acumulado se recalcula, no se promedia." },
];

const usd = (v: number) =>
  "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: number) =>
  v.toLocaleString("es-CR", { maximumFractionDigits: 0 });

export default function EstadisticaHabitaciones({
  scenarioId, scenarios, month, dimension = "habitacion",
}: {
  /** El escenario de la vista principal. */
  scenarioId: string;
  /** Todos los escenarios, para poder caer al ACTUAL. Ver abajo. */
  scenarios: Scenario[];
  /** 0 = Full Year; 1..12 = ese mes. Es el mismo selector del Dashboard. */
  month: number;
  dimension?: "habitacion" | "canal";
}) {
  const [anio, setAnio] = useState<AnioRoomStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dim, setDim] = useState<"habitacion" | "canal">(dimension);
  const [abierto, setAbierto] = useState(true);
  /** true = lo que se muestra NO es el escenario principal. */
  const [prestado, setPrestado] = useState(false);

  /** ⚠️ La estadística del PMS vive en el escenario ACTUAL, y el Dashboard
   *  abre con el Budget en el principal.
   *
   *  Colgando el bloque del principal a secas, la vista por defecto mostraba
   *  «este escenario no tiene estadística» y los ocho cuadros no aparecían
   *  nunca — que es exactamente lo que el owner reportó: *«dónde quedaron los
   *  cuadros… no los veo»*.
   *
   *  Se prueba el principal primero —si alguien carga estadística en un
   *  Forecast, ese manda— y si no tiene, se cae al ACTUAL del mismo año. Lo
   *  que se está mostrando se dice siempre en el encabezado: leer el ACTUAL
   *  creyendo que es el Budget sería peor que no ver nada. */
  const candidatos = useMemo(() => {
    if (!scenarioId) return [];
    const principal = scenarios.find(s => s.id === scenarioId);
    const delAno = scenarios.filter(s => s.type === "ACTUAL"
      && (!principal || s.year === principal.year) && s.id !== scenarioId);
    return [scenarioId, ...delAno.map(s => s.id)];
  }, [scenarioId, scenarios]);

  useEffect(() => {
    if (!candidatos.length) { setAnio(null); return; }
    let vivo = true;
    setError(null);
    (async () => {
      let ultimo: AnioRoomStats | null = null;
      for (const id of candidatos) {
        try {
          const r = await getAnioRoomStats(id);
          ultimo = ultimo ?? r;
          if (r.meses_cargados.length) {
            if (vivo) { setAnio(r); setPrestado(id !== scenarioId); }
            return;
          }
        } catch (e) {
          if (id === scenarioId) {
            if (vivo) setError(e instanceof Error ? e.message : "error");
          }
        }
      }
      // Ninguno tiene: se muestra el principal, en vacío, con su cartel.
      if (vivo) { setAnio(ultimo); setPrestado(false); }
    })();
    return () => { vivo = false; };
  }, [candidatos, scenarioId]);

  const cargados = useMemo(() => anio?.meses.filter(m => m.cargado) ?? [], [anio]);

  /** Las filas de la dimensión elegida, en orden estable. */
  const claves = useMemo(() => {
    if (!anio) return [];
    return dim === "canal"
      ? [...new Set(anio.meses.flatMap(m => m.canales.map(c => c.canal_code)))]
      : anio.room_types.map(r => r.name);
  }, [anio, dim]);

  /** Las filas de un mes para una clave. Vacío = ese mes no tiene nada suyo. */
  function filasDe(m: AnioMes, clave: string): Medible[] {
    if (!m.cargado) return [];
    return dim === "canal"
      ? m.canales.filter(c => c.canal_code === clave)
      : m.categorias.filter(c => c.room_type_name === clave);
  }

  /** Suma una medida sobre un conjunto de meses. */
  function suma(meses: AnioMes[], clave: string | null, saca: (r: Medible) => number) {
    let t = 0;
    for (const m of meses) {
      const filas = clave === null
        ? (dim === "canal" ? m.canales : m.categorias)
        : filasDe(m, clave);
      for (const f of filas) t += saca(f);
    }
    return t;
  }

  if (!scenarioId) return null;
  if (error) {
    return (
      <Marco>
        <p style={{ margin: 0, padding: "14px 16px", fontSize: 12.5, color: "var(--negative)" }}>
          No se pudo leer la estadística: {error}
        </p>
      </Marco>
    );
  }
  if (!anio) {
    return (
      <Marco>
        <p style={{ margin: 0, padding: "14px 16px", fontSize: 12.5,
                    color: "var(--text-secondary)" }}>Cargando la estadística…</p>
      </Marco>
    );
  }
  if (!cargados.length) {
    return (
      <Marco escenario={anio.escenario}>
        <p style={{ margin: 0, padding: "14px 16px", fontSize: 12.5,
                    color: "var(--text-secondary)" }}>
          No hay estadística de habitaciones cargada para {anio.year} —{" "}
          ni en <b>{anio.escenario}</b> ni en el ACTUAL del año. Se sube en{" "}
          <b>Cierre de Mes · Estadística de habitaciones</b>.
        </p>
      </Marco>
    );
  }

  // ── Los tres períodos, en el orden en que se leen ───────────────────────
  const delMes = month > 0 ? cargados.filter(m => m.month === month) : [];
  const ytd = month > 0 ? cargados.filter(m => m.month <= month) : cargados;
  const full = cargados;
  const ultimo = cargados[cargados.length - 1].month;

  // ⚠️ En «Full Year» no hay un mes elegido, y una columna entera de «—» bajo
  // un encabezado «—» es ruido que además empuja las otras dos. Se saca.
  const hayMes = month > 0;
  const rotMes = hayMes ? MESES[month - 1] : "";
  const rotYtd = hayMes ? `YTD ${MESES[month - 1]}` : `YTD ${MESES[ultimo - 1]}`;
  const periodos: [string, AnioMes[]][] = [
    ...(hayMes ? [[rotMes, delMes] as [string, AnioMes[]]] : []),
    [rotYtd, ytd], ["Full Year", full],
  ];

  /** ⚠️ Las cuatro medidas que se empezaron a guardar el 2026-09-28. Una carga
   *  anterior las dejó en cero, y cero acá NO significa «el hotel no tuvo
   *  otros ingresos»: significa «esta carga es de antes». Cuatro cuadros
   *  llenos de $0.00 dicen lo primero, así que se avisa una vez. */
  const NUEVAS = ["ayb", "otros", "habEnt", "cliEnt"];
  const sinCargaNueva = NUEVAS.every(k => {
    const b = BLOQUES.find(x => x.clave === k);
    return b?.saca ? suma(full, null, b.saca) === 0 : true;
  });

  const fmt = (u: Unidad) => (u === "usd" ? usd : num);

  return (
    <Marco escenario={anio.escenario} abierto={abierto}
           alAbrir={() => setAbierto(a => !a)}
           dim={dim} alCambiarDim={setDim}
           prestado={prestado}
      pie={`${cargados.length} mes(es) cargado(s): ${
             cargados.map(m => MESES[m.month - 1]).join(" · ")}. «Full Year» es`
             + ` la suma de esos meses, no una proyección a doce.`
             + (month > 0 && !delMes.length
                ? `  ⚠️ ${MESES[month - 1]} no tiene estadística cargada:`
                  + ` la columna del mes va vacía, no en cero.`
                : "")}>
      {abierto && sinCargaNueva && (
        <div style={{ margin: "12px 14px 0", padding: "8px 12px", fontSize: 11.5,
                      lineHeight: 1.45, borderRadius: 6,
                      background: "rgba(245,158,11,.10)",
                      border: "1px solid rgba(245,158,11,.35)" }}>
          <b>Otros ingresos y Entradas están en cero porque la carga es
          anterior.</b> Hasta el 28/09 el sistema guardaba sólo noches, pax e
          ingreso de hospedaje; las otras cuatro columnas del reporte se leían
          y se descartaban. Volvé a subir el archivo del PMS —una vez, con
          «Guardar los N meses»— y estos cuadros se llenan. Un cero acá no
          significa que el hotel no los tuvo.
        </div>
      )}
      {abierto && (
        <div style={{ display: "grid", gap: 14, padding: "12px 14px 16px",
                      // `start`: cada tarjeta mide lo que su contenido. Con el
                      // `stretch` por defecto, las de encabezado corto quedaban
                      // estiradas y el `overflow:hidden` del borde redondeado
                      // les cortaba la primera fila.
                      alignItems: "start",
                      gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))" }}>
          {BLOQUES.map(b => {
            const f = fmt(b.unidad);
            /** Una celda: la medida del bloque para una clave y un período. */
            const celda = (meses: AnioMes[], clave: string | null) => {
              if (!meses.length) return null;
              if (b.saca === null) {
                // ⚠️ Tasa: se recalcula sobre los totales del período.
                const ing = suma(meses, clave, r => r.revenue);
                const noc = suma(meses, clave, r => r.nights_occupied);
                return noc ? ing / noc : 0;
              }
              return suma(meses, clave, b.saca);
            };
            return (
              <div key={b.clave} style={{ border: "1px solid var(--border-medium)",
                                          borderRadius: 7,
                                          background: "var(--bg-surface)" }}>
                <div style={{ padding: "7px 11px", background: "var(--bg-elevated)",
                              borderBottom: "1px solid var(--border-medium)" }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700 }}>{b.titulo}</div>
                  {b.nota && <div style={{ fontSize: 10.5, marginTop: 1,
                                           color: "var(--text-secondary)" }}>{b.nota}</div>}
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={TH}>{dim === "canal" ? "Canal" : "Categoría"}</th>
                      {periodos.map(([rot]) => (
                        <th key={rot} style={{ ...TH, textAlign: "right" }}>{rot}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {claves.map(k => (
                      <tr key={k}>
                        <td style={TD_ROT} title={k}>{k}</td>
                        {periodos.map(([rot, ms]) => {
                          const v = celda(ms, k);
                          return <td key={rot} className="mono" style={TD}>
                            {v === null ? "—" : f(v)}
                          </td>;
                        })}
                      </tr>
                    ))}
                    <tr>
                      <td style={{ ...TD_ROT, fontWeight: 700,
                                   borderTop: "1px solid var(--border-medium)" }}>TOTAL</td>
                      {periodos.map(([rot, ms]) => {
                        const v = celda(ms, null);
                        return <td key={rot} className="mono"
                                   style={{ ...TD, fontWeight: 700,
                                            borderTop: "1px solid var(--border-medium)" }}>
                          {v === null ? "—" : f(v)}
                        </td>;
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      )}
    </Marco>
  );
}

const TH: React.CSSProperties = {
  padding: "5px 9px", fontSize: 10.5, fontWeight: 600, textAlign: "left",
  textTransform: "uppercase", letterSpacing: ".03em",
  color: "var(--text-secondary)", borderBottom: "1px solid var(--border-subtle)",
};
const TD: React.CSSProperties = {
  padding: "4px 9px", textAlign: "right", whiteSpace: "nowrap",
};
/** ⚠️ El rótulo NO se corta con puntos suspensivos.
 *
 *  Amarena tiene «Garden View Deluxe-Tented Villa» y «Garden View
 *  Deluxe-Tented Villa · Accesible»: cortadas a 150px las dos se leen
 *  «Garden View Deluxe-Tente…» y no hay forma de saber cuál fila es cuál. */
const TD_ROT: React.CSSProperties = {
  padding: "4px 9px", color: "var(--text-secondary)",
  lineHeight: 1.25, wordBreak: "break-word",
};

function Marco({ children, escenario, pie, abierto, alAbrir, dim, alCambiarDim,
                 prestado }: {
  children: React.ReactNode; escenario?: string; pie?: string;
  abierto?: boolean; alAbrir?: () => void;
  dim?: "habitacion" | "canal";
  alCambiarDim?: (d: "habitacion" | "canal") => void;
  /** El escenario que se está leyendo NO es el principal del Dashboard. */
  prestado?: boolean;
}) {
  return (
    <div style={{ marginTop: 16, background: "var(--bg-elevated)",
                  border: "1px solid var(--border-medium)", borderRadius: 8,
                  overflow: "hidden" }}>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-medium)",
                    background: "rgba(36,83,196,.06)", display: "flex",
                    alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 13, fontWeight: 700 }}>
            Estadística de habitaciones · PMS
          </div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
            Un cuadro por tab del reporte de segmentación
            {escenario ? <> — <b style={{ color: "var(--text-primary)" }}>{escenario}</b></> : null}
            {prestado ? (
              <span style={{ marginLeft: 6, padding: "1px 6px", borderRadius: 3,
                             fontSize: 10, fontWeight: 600,
                             background: "rgba(245,158,11,.16)",
                             color: "var(--warning)" }}>
                no es la versión principal
              </span>
            ) : null}
          </div>
        </div>
        {alCambiarDim && (
          <div style={{ display: "flex", gap: 2 }}>
            {([["habitacion", "Por habitación"], ["canal", "Por canal"]] as const)
              .map(([k, r]) => (
                <button key={k} onClick={() => alCambiarDim(k)}
                  style={{ padding: "4px 10px", fontSize: 11.5, cursor: "pointer",
                           borderRadius: 4, border: "1px solid var(--border-medium)",
                           background: dim === k ? "var(--brand)" : "transparent",
                           color: dim === k ? "#fff" : "var(--text-secondary)" }}>
                  {r}
                </button>
              ))}
          </div>
        )}
        {alAbrir && (
          <button onClick={alAbrir}
            style={{ padding: "4px 10px", fontSize: 11.5, cursor: "pointer",
                     borderRadius: 4, border: "1px solid var(--border-medium)",
                     background: "transparent", color: "var(--text-secondary)" }}>
            {abierto ? "Ocultar" : "Mostrar"}
          </button>
        )}
      </div>
      {children}
      {pie && (
        <div style={{ padding: "8px 16px", fontSize: 11,
                      color: "var(--text-secondary)",
                      borderTop: "1px solid var(--border-subtle)" }}>
          {pie}
        </div>
      )}
    </div>
  );
}
