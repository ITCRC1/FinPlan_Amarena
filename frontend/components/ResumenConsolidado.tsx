"use client";
import { useEffect, useMemo, useState } from "react";

import { getAnioRoomStats, type AnioRoomStats, type Scenario } from "@/lib/api";
import { bajarCuadros, type Cuadro, type FilaCuadro } from "@/lib/exportCuadro";
import {
  cuadroResumenConsolidado, RENGLONES, type Ctx, type Formato,
} from "@/lib/resumenConsolidado";

/**
 * El Resumen Consolidado del reporte del PMS, al pie del Dashboard.
 *
 * Owner, 2026-09-29: *«quiero que pegues este reporte aca en el dashboard y lo
 * pongas al final de aca»*, con el cuadro que la propiedad arma a mano.
 *
 * Es la hoja «Resumen» del Excel de segmentación: un renglón por indicador y
 * una columna por mes, con el acumulado al final.
 *
 * ## ⚠️ Las tres noches, y cuál alimenta los indicadores
 *
 * Pagadas, cortesías y el total —que es la suma de las dos— van como tres
 * renglones separados. Los indicadores salen de las **pagadas**, igual que el
 * cierre; las cifras del archivo del PMS quedan al pie, en gris, para poder
 * cuadrar contra el papel.
 *
 * ## ⚠️ Disponibles y bloqueadas sólo vienen del PDF
 *
 * No se calculan: son un hecho operativo del mes. Un mes cargado desde la base
 * plana —o cargado antes de que se guardaran— los deja vacíos, y con ellos la
 * «% Ocupación sobre disponibles». Vacío, no cero: cero diría que el hotel
 * tuvo todo el inventario en servicio.
 *
 * ## ⚠️ El acumulado de una TASA se recalcula
 *
 * ADR, RevPAR y las dos ocupaciones se rehacen sobre los totales del período.
 * Promediar las columnas haría pesar igual a marzo (51 noches) y a agosto
 * (218) — $235.36 contra $196.02.
 */

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

const usd = (v: number) =>
  v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: number) => v.toLocaleString("es-CR", { maximumFractionDigits: 0 });
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

const fmt = (v: number | null, f: Formato) =>
  v === null ? "" : f === "usd" ? usd(v) : f === "pct" ? pct(v) : num(v);

export default function ResumenConsolidado({ scenarioId, scenarios, month }: {
  scenarioId: string;
  scenarios: Scenario[];
  /** 0 = Full Year; 1..12 = ese mes. Sólo resalta la columna: el cuadro es la
   *  serie completa, que es lo que se manda a los dueños. */
  month: number;
}) {
  const [anio, setAnio] = useState<AnioRoomStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState(true);

  /** Mismo criterio que el otro bloque: el principal primero, y si no tiene
   *  estadística, el ACTUAL del mismo año. La estadística vive en el ACTUAL y
   *  el Dashboard abre con el Budget. */
  const candidatos = useMemo(() => {
    if (!scenarioId) return [];
    const principal = scenarios.find(s => s.id === scenarioId);
    return [scenarioId, ...scenarios
      .filter(s => s.type === "ACTUAL" && s.id !== scenarioId
        && (!principal || s.year === principal.year)).map(s => s.id)];
  }, [scenarioId, scenarios]);

  useEffect(() => {
    if (!candidatos.length) { setAnio(null); return; }
    let vivo = true;
    (async () => {
      let ultimo: AnioRoomStats | null = null;
      for (const id of candidatos) {
        try {
          const r = await getAnioRoomStats(id);
          ultimo = ultimo ?? r;
          if (r.meses_cargados.length) { if (vivo) setAnio(r); return; }
        } catch (e) {
          if (id === scenarioId && vivo) {
            setError(e instanceof Error ? e.message : "error");
          }
        }
      }
      if (vivo) setAnio(ultimo);
    })();
    return () => { vivo = false; };
  }, [candidatos, scenarioId]);

  const cargados = useMemo(() => anio?.meses.filter(m => m.cargado) ?? [], [anio]);
  const unidades = useMemo(
    () => (anio?.room_types ?? []).reduce((a, r) => a + r.units, 0), [anio]);
  const ctx: Ctx = { unidades };

  /** Meses que no trajeron el resumen del hotel: sin ellos no hay disponibles
   *  ni ocupación sobre disponibles, y hay que decirlo. */
  const sinResumen = cargados.filter(m => !m.resumen);

  /** ⚠️ El cuadro lo arma `lib/resumenConsolidado`: el mismo que usa el
   *  paquete del cierre. Dos armados del mismo cuadro se separan en el primer
   *  arreglo que alguien hace de un lado. */
  async function bajar() {
    if (!anio) return;
    try { await bajarCuadros(`ResumenConsolidado_${anio.year}`,
                             [cuadroResumenConsolidado(anio)]); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudo generar el Excel"); }
  }

  if (!scenarioId) return null;

  const cuerpo = () => {
    if (error) return <P tono="err">No se pudo leer la estadística: {error}</P>;
    if (!anio) return <P>Cargando el resumen…</P>;
    if (!cargados.length) {
      return <P>
        No hay estadística de habitaciones cargada para {anio.year}. Se sube en{" "}
        <b>Cierre de Mes · Estadística de habitaciones</b>.
      </P>;
    }
    return (
      <>
        <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 12.5, minWidth: "100%" }}>
            <thead>
              <tr>
                <th style={{ ...TH, textAlign: "left", minWidth: 280 }}>Indicador</th>
                {cargados.map(m => (
                  <th key={m.month} style={{ ...TH,
                        ...(m.month === month ? ACTUAL : {}) }}>
                    {MESES[m.month - 1]}
                  </th>
                ))}
                <th style={{ ...TH, ...TOTAL }}>Total / Prom.</th>
              </tr>
            </thead>
            <tbody>
              {RENGLONES.map(r => (
                <tr key={r.clave} style={{
                      ...(r.banda ? { background: "rgba(36,83,196,.06)" } : {}),
                      ...(r.espacioAntes
                        ? { borderTop: "10px solid transparent" } : {}) }}>
                  <td style={{ ...TD, textAlign: "left",
                               fontWeight: r.banda ? 700 : 400,
                               color: r.tenue ? "var(--text-secondary)" : undefined }}>
                    {r.rotulo}
                  </td>
                  {cargados.map(m => (
                    <td key={m.month} className="mono"
                        style={{ ...TD, fontWeight: r.banda ? 700 : 400,
                                 color: r.tenue ? "var(--text-secondary)" : undefined,
                                 ...(m.month === month ? ACTUAL : {}) }}>
                      {fmt(r.valor([m], ctx), r.formato)}
                    </td>
                  ))}
                  <td className="mono" style={{ ...TD, ...TOTAL,
                        fontWeight: r.banda ? 700 : 600 }}>
                    {fmt(r.valor(cargados, ctx), r.formato)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ padding: "10px 16px", fontSize: 11, lineHeight: 1.5,
                      color: "var(--text-secondary)",
                      borderTop: "1px solid var(--border-subtle)" }}>
          <b>Los indicadores salen de las noches pagadas</b>, igual que el
          cierre: las cortesías no entran. El total con cortesías está arriba
          como renglón propio, y las dos cifras del archivo del PMS —ocupación
          y ADR con cortesías— al pie del cuadro, para poder cuadrar contra el
          papel. · El acumulado de ADR, RevPAR y las ocupaciones se{" "}
          <b>recalcula</b> sobre los totales, nunca se promedia.
          {sinResumen.length > 0 && (
            <>
              {" "}· <b style={{ color: "var(--warning)" }}>
                {sinResumen.length === 1
                  ? `${MESES[sinResumen[0].month - 1]} no trae`
                  : `${sinResumen.map(m => MESES[m.month - 1]).join(", ")} no traen`}
                {" "}el resumen del hotel
              </b>, así que las habitaciones disponibles y bloqueadas —y la
              ocupación sobre disponibles— van en blanco. Sólo vienen en el PDF
              del PMS: volvé a subir el PDF de esos meses para llenarlas.
            </>
          )}
        </div>
      </>
    );
  };

  return (
    <div style={{ marginTop: 16, background: "var(--bg-elevated)",
                  border: "1px solid var(--border-medium)", borderRadius: 8,
                  overflow: "hidden" }}>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-medium)",
                    background: "rgba(36,83,196,.06)", display: "flex",
                    alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 230 }}>
          <div style={{ fontSize: 13, fontWeight: 700 }}>Resumen consolidado · PMS</div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
            {anio ? <>{anio.escenario} · {cargados.length} mes(es) cargado(s)</>
                  : "Estadística de explotación del hotel"}
          </div>
        </div>
        {anio && cargados.length > 0 && (
          <button onClick={bajar}
            style={{ padding: "5px 12px", fontSize: 12, fontWeight: 600,
                     borderRadius: 5, border: "none", cursor: "pointer",
                     background: "var(--accent-excel)", color: "#fff" }}>
            ⬇ Excel
          </button>
        )}
        <button onClick={() => setAbierto(a => !a)}
          style={{ padding: "4px 10px", fontSize: 11.5, cursor: "pointer",
                   borderRadius: 4, border: "1px solid var(--border-medium)",
                   background: "transparent", color: "var(--text-secondary)" }}>
          {abierto ? "Ocultar" : "Mostrar"}
        </button>
      </div>
      {abierto && cuerpo()}
    </div>
  );
}

const TH: React.CSSProperties = {
  padding: "6px 10px", fontSize: 10.5, fontWeight: 600, textAlign: "right",
  textTransform: "uppercase", letterSpacing: ".03em", whiteSpace: "nowrap",
  color: "var(--text-secondary)", borderBottom: "1px solid var(--border-medium)",
};
const TD: React.CSSProperties = {
  padding: "4px 10px", textAlign: "right", whiteSpace: "nowrap",
  borderBottom: "1px solid var(--border-subtle)",
};
const ACTUAL: React.CSSProperties = { background: "rgba(36,83,196,.09)" };
const TOTAL: React.CSSProperties = {
  background: "rgba(36,83,196,.05)", borderLeft: "1px solid var(--border-medium)",
};

function P({ children, tono }: { children: React.ReactNode; tono?: "err" }) {
  return <p style={{ margin: 0, padding: "14px 16px", fontSize: 12.5,
                     color: tono === "err" ? "var(--negative)" : "var(--text-secondary)" }}>
    {children}
  </p>;
}
