"use client";
import { useCallback, useEffect, useState, CSSProperties } from "react";
import { useTranslations } from "next-intl";
import { elegir } from "@/lib/escenarioPreferido";
import { HOTEL_ID } from "@/lib/hotel";
import { useHotel } from "@/lib/useHotel";
import { bajarCuadros, type FilaCuadro } from "@/lib/exportCuadro";
import {
  getScenarios, getResumenAnual, resumenAnualWordUrl,
  type Scenario, type ResumenAnual, type ResumenFila,
} from "@/lib/api";

/**
 * Resumen ejecutivo — un año contra otro, con los doce meses a la vista.
 *
 * Owner, 2026-11-04: «forecast 2026 full year versus budget 2027 full year…
 * debe haber una forma de que este reporte se actualice en forma automática o
 * un botón para darle refresh».
 *
 * **Se actualiza solo porque no guarda nada.** Cada vez que se abre, el
 * backend lo calcula desde el mismo motor que alimenta el P&L y el Dashboard.
 * El botón ↻ no recalcula en la base: vuelve a pedirlo. Por eso nunca puede
 * mostrar un número distinto al del P&L — es el mismo número, leído una vez.
 *
 * La narrativa la arma el backend con los números del cuadro. Describe lo que
 * se movió; no dice si está bien. Esa parte sigue siendo del que lo lee.
 */
const HOTEL = HOTEL_ID;

const th: CSSProperties = { color: "var(--text-secondary)", fontWeight: 600, fontSize: 11, textAlign: "left", padding: "7px 10px", borderBottom: "1px solid var(--border-medium)", textTransform: "uppercase", letterSpacing: "0.04em", background: "var(--bg-elevated)", position: "sticky", top: 0 };
const thNum: CSSProperties = { ...th, textAlign: "right", textTransform: "none", letterSpacing: 0 };
const td: CSSProperties = { padding: "5px 10px", fontSize: 12.5, borderBottom: "1px solid var(--border-subtle)" };
const tdNum: CSSProperties = { ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" };
const boton: CSSProperties = { padding: "5px 14px", fontSize: 12.5, fontWeight: 700, borderRadius: 6, cursor: "pointer", background: "transparent", color: "var(--text-primary)", border: "1px solid var(--border-medium)" };

const money = (v: number) =>
  v === 0 ? "—" : "$" + Math.round(v).toLocaleString("en-US");
const pct = (v: number | null) => (v === null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`);

/** El color de una variación lo decide el backend (`favorable`): en un gasto,
 *  subir no es bueno, y si cada pantalla lo resolviera sola alguna lo pintaría
 *  al revés tarde o temprano. */
const colorVar = (f: ResumenFila) =>
  f.favorable === null ? "var(--text-secondary)"
    : f.favorable ? "var(--positive)" : "var(--negative)";

const TYPE_LABEL: Record<string, string> = { ACTUAL: "Actual", BUDGET: "Budget", FORECAST: "Forecast" };
function scnLabel(s: Scenario) {
  const t = TYPE_LABEL[s.type] ?? s.type;
  return (!s.version || ["actual", "from-xlsx"].includes(s.version))
    ? `${t} ${s.year}` : `${t} ${s.year} · ${s.version}`;
}

export default function ResumenAnualPage() {
  const hotel = useHotel();
  const tc = useTranslations("common");
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [baseId, setBaseId] = useState("");
  const [compId, setCompId] = useState("");
  const [d, setD] = useState<ResumenAnual | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [verMeses, setVerMeses] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const all = await getScenarios(HOTEL);
        if (!all.length) { setError(tc("noScenarios", { hotel: hotel.id })); return; }
        setScenarios(all);
        // El año que termina se lee del FORECAST, no del Actual: un Actual con
        // meses sin cargar contra doce de presupuesto da un derrumbe que sólo
        // dice que el año no terminó.
        const fc = elegir(all, "forecast") ?? all.find(s => s.type === "FORECAST");
        const bu = elegir(all, "budget");
        if (fc) setBaseId(fc.id);
        if (bu) setCompId(bu.id);
      } catch (e) { setError(e instanceof Error ? e.message : tc("error")); }
    })();
  }, [tc, hotel.id]);

  const cargar = useCallback(async (a: string, b: string) => {
    if (!a || !b) return;
    setCargando(true); setError("");
    try { setD(await getResumenAnual(a, b)); }
    catch (e) { setError(e instanceof Error ? e.message : tc("error")); setD(null); }
    finally { setCargando(false); }
  }, [tc]);

  useEffect(() => { cargar(baseId, compId); }, [baseId, compId, cargar]);

  const filas = (xs: ResumenFila[]): FilaCuadro[] => xs.map(x => ({
    label: x.nombre,
    valores: verMeses
      ? [...x.base_meses, x.base, ...x.comp_meses, x.comp, x.var]
      : [x.base, x.comp, x.var],
  }));

  async function bajarExcel() {
    if (!d) return;
    const cols = verMeses
      ? [{ label: "Concepto", ancho: 30, formato: "texto" as const },
         ...d.meses.map(m => ({ label: `${m} ${d.base.anio}`, ancho: 11, formato: "usd" as const })),
         { label: `Año ${d.base.anio}`, ancho: 14, formato: "usd" as const },
         ...d.meses.map(m => ({ label: `${m} ${d.comparado.anio}`, ancho: 11, formato: "usd" as const })),
         { label: `Año ${d.comparado.anio}`, ancho: 14, formato: "usd" as const },
         { label: "Variación", ancho: 14, formato: "usd" as const }]
      : [{ label: "Concepto", ancho: 30, formato: "texto" as const },
         { label: `${d.base.anio}`, ancho: 15, formato: "usd" as const },
         { label: `${d.comparado.anio}`, ancho: 15, formato: "usd" as const },
         { label: "Variación", ancho: 15, formato: "usd" as const }];
    try {
      await bajarCuadros("Resumen_Ejecutivo", [{
        titulo: `Resumen ejecutivo · ${d.base.anio} contra ${d.comparado.anio}`,
        subtitulo: `${d.base.tipo} ${d.base.version} ${d.base.anio}  vs  ${d.comparado.tipo} ${d.comparado.version} ${d.comparado.anio}`,
        hoja: "Resumen",
        columnas: cols,
        filas: [
          { label: "INGRESOS", es_total: true, valores: [] },
          ...filas(d.ingresos),
          { label: "GASTO POR CLASE", es_total: true, valores: [] },
          ...filas(d.clases),
          { label: "RESULTADO", es_total: true, valores: [] },
          ...filas(d.resultado),
        ],
      }]);
    } catch (e) { setError(e instanceof Error ? e.message : tc("error")); }
  }

  const bloque = (titulo: string, xs: ResumenFila[], fuerte = false) => (
    <>
      <tr>
        <td colSpan={verMeses ? 28 : 4}
          style={{ ...td, fontWeight: 800, fontSize: 11, letterSpacing: "0.05em",
                   textTransform: "uppercase", color: "var(--brand)",
                   background: "var(--bg-elevated)", paddingTop: 10 }}>
          {titulo}
        </td>
      </tr>
      {xs.map(x => (
        <tr key={x.code}>
          <td style={{ ...td, fontWeight: fuerte ? 700 : 400 }}>{x.nombre}</td>
          {verMeses && x.base_meses.map((v, i) => (
            <td key={`a${i}`} style={{ ...tdNum, color: "var(--text-secondary)" }}>{money(v)}</td>
          ))}
          <td style={{ ...tdNum, fontWeight: 700 }}>{money(x.base)}</td>
          {verMeses && x.comp_meses.map((v, i) => (
            <td key={`b${i}`} style={{ ...tdNum, color: "var(--text-secondary)" }}>{money(v)}</td>
          ))}
          <td style={{ ...tdNum, fontWeight: 700 }}>{money(x.comp)}</td>
          <td style={{ ...tdNum, fontWeight: 700, color: colorVar(x) }}>{money(x.var)}</td>
          <td style={{ ...tdNum, color: colorVar(x) }}>{pct(x.var_pct)}</td>
        </tr>
      ))}
    </>
  );

  return (
    <div className="pag pag-ancha" style={{ padding: "24px 20px 60px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, margin: 0 }}>Resumen ejecutivo</h1>
        <select value={baseId} onChange={e => setBaseId(e.target.value)}
          style={{ padding: "5px 10px", fontSize: 12.5, borderRadius: 6, background: "var(--bg-input)", color: "var(--text-primary)", border: "1px solid var(--border-medium)" }}>
          {scenarios.map(s => <option key={s.id} value={s.id}>{scnLabel(s)}</option>)}
        </select>
        <span style={{ color: "var(--text-secondary)" }}>contra</span>
        <select value={compId} onChange={e => setCompId(e.target.value)}
          style={{ padding: "5px 10px", fontSize: 12.5, borderRadius: 6, background: "var(--bg-input)", color: "var(--text-primary)", border: "1px solid var(--border-medium)" }}>
          {scenarios.map(s => <option key={s.id} value={s.id}>{scnLabel(s)}</option>)}
        </select>
        <div style={{ flex: 1 }} />
        <button onClick={() => setVerMeses(v => !v)} style={boton}>
          {verMeses ? "Solo totales" : "Ver meses"}
        </button>
        <button onClick={bajarExcel} disabled={!d} style={boton}>⬇ Excel</button>
        <a href={d ? resumenAnualWordUrl(baseId, compId) : undefined}
          style={{ ...boton, textDecoration: "none", opacity: d ? 1 : 0.5,
                   pointerEvents: d ? "auto" : "none" }}>⬇ Word</a>
        <button onClick={() => cargar(baseId, compId)} disabled={cargando}
          style={{ ...boton, background: "var(--brand)", color: "#fff", border: "none" }}>
          {cargando ? "Actualizando…" : "↻ Refresh"}
        </button>
      </div>

      <p style={{ color: "var(--text-secondary)", fontSize: 12.5, maxWidth: 1000, marginTop: 8 }}>
        Se calcula en vivo cada vez que se abre: no hay nada guardado, así que no
        puede quedar viejo. El botón ↻ vuelve a pedirlo — útil si alguien acaba
        de tocar un checkbook en otra pestaña.
      </p>
      {error && <p style={{ color: "var(--negative)", fontSize: 13 }}>{error}</p>}
      {cargando && !d && <p style={{ color: "var(--text-secondary)" }}>{tc("loading")}</p>}

      {d && (
        <>
          {/* ── KPIs ───────────────────────────────────────────────── */}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", margin: "16px 0 6px" }}>
            {([["Ocupación", `${(100 * d.kpis.base.ocupacion).toFixed(1)}%`, `${(100 * d.kpis.comp.ocupacion).toFixed(1)}%`],
               ["Noches", d.kpis.base.ocupadas.toLocaleString("en-US"), d.kpis.comp.ocupadas.toLocaleString("en-US")],
               ["Pax", d.kpis.base.pax.toLocaleString("en-US"), d.kpis.comp.pax.toLocaleString("en-US")],
               ["ADR", `$${d.kpis.base.adr.toFixed(2)}`, `$${d.kpis.comp.adr.toFixed(2)}`],
               ["RevPAR", `$${d.kpis.base.revpar.toFixed(2)}`, `$${d.kpis.comp.revpar.toFixed(2)}`],
              ] as [string, string, string][]).map(([lab, a, b]) => (
              <div key={lab} style={{ flex: "1 1 150px", padding: "10px 14px", borderRadius: 8,
                                      background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.05em",
                              color: "var(--text-secondary)" }}>{lab}</div>
                <div style={{ fontSize: 20, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>{b}</div>
                <div style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
                  {d.base.anio}: {a}
                </div>
              </div>
            ))}
          </div>

          {/* ── Narrativa ──────────────────────────────────────────── */}
          <div style={{ margin: "14px 0", padding: "12px 16px", borderRadius: 8,
                        background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em",
                          color: "var(--text-secondary)", marginBottom: 6 }}>
              Lectura del año
            </div>
            {d.narrativa.map((f, i) => (
              <p key={i} style={{ margin: "0 0 5px", fontSize: 13, lineHeight: 1.5 }}>{f}</p>
            ))}
          </div>

          {/* ── El cuadro ──────────────────────────────────────────── */}
          <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", minWidth: verMeses ? 2100 : 620 }}>
              <thead>
                <tr>
                  <th style={{ ...th, minWidth: 210 }}>Concepto</th>
                  {verMeses && d.meses.map(m => (
                    <th key={`a${m}`} style={thNum}>{m} {String(d.base.anio).slice(2)}</th>
                  ))}
                  <th style={thNum}>Año {d.base.anio}</th>
                  {verMeses && d.meses.map(m => (
                    <th key={`b${m}`} style={thNum}>{m} {String(d.comparado.anio).slice(2)}</th>
                  ))}
                  <th style={thNum}>Año {d.comparado.anio}</th>
                  <th style={thNum}>Var $</th>
                  <th style={thNum}>Var %</th>
                </tr>
              </thead>
              <tbody>
                {bloque("Ingresos", d.ingresos)}
                {bloque("Gasto por clase", d.clases)}
                {bloque("Resultado", d.resultado, true)}
                {bloque("Utilidad por departamento",
                        d.departamentos.map(x => x.utilidad))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
