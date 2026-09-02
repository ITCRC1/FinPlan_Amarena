"use client";
/**
 * El P&L de UNA versión, mes a mes, en el tab de Cierre de Mes.
 *
 * Owner, 2026-08-28: *«necesito meter en el tab Cierre de mes un sub tab que
 * tenga 12 meses, y una versión para escoger»*.
 *
 * **Por qué una sola versión y no las cuatro ranuras del resto de la pantalla.**
 * Los demás sub-tabs comparan versiones en UN período; éste hace lo contrario:
 * una versión a lo largo del año. Meterle las cuatro daría 48 columnas y
 * dejaría de leerse — que es justo lo que este cuadro sirve para evitar.
 *
 * **De dónde sale.** `/pl/{id}/doce-meses/`, que devuelve los doce SIN agregar.
 * No es `/pl/compare-range/` doce veces: ése agrega el rango en una columna, y
 * el ADR y el impuesto no son aditivos, así que sumar o restar columnas ya
 * armadas daría un número que no es de nadie.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getPLDoceMeses, type PLDoceMeses, type Scenario } from "@/lib/api";

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

/** Las líneas del cuadro, en el orden del P&L. Es el mismo esqueleto que usa el
 *  resumen mensual: totales, no el detalle por departamento — para eso están
 *  los otros sub-tabs. */
const FILAS: { code: string; label: string; fuerte?: boolean; sangria?: boolean }[] = [
  { code: "K_ROOMS_AVAIL", label: "Total Rooms Available" },
  { code: "K_ROOMS_OCC", label: "Total Rooms Occupied" },
  { code: "K_OCC", label: "Occupancy %" },
  { code: "K_ADR", label: "ADR" },
  { code: "K_REVPAR", label: "RevPAR" },
  { code: "TOTAL_REVENUES", label: "Total Revenue", fuerte: true },
  { code: "TOTAL_OPEXP", label: "Total Operating Expenses", sangria: true },
  { code: "TOTAL_OP_PROFIT", label: "Operating Profit", fuerte: true },
  { code: "TOTAL_OVERHEAD", label: "Total Overhead", sangria: true },
  { code: "GOP", label: "GOP", fuerte: true },
  { code: "TOTAL_NON_OP", label: "Total Non-Op Expenses", sangria: true },
  { code: "EBITDA_BEFORE", label: "EBITDA before Capital", fuerte: true },
  { code: "CAPITAL_EXPENSE", label: "Capital Expense", sangria: true },
  { code: "EBITDA_AFTER", label: "EBITDA after Capital", fuerte: true },
  { code: "EBT", label: "Earnings before Taxes", fuerte: true },
  { code: "INCOME_TAXES", label: "Income Taxes", sangria: true },
  { code: "NET_PROFIT", label: "Net Profit", fuerte: true },
];

const KPI = new Set(["K_ROOMS_AVAIL", "K_ROOMS_OCC", "K_OCC", "K_ADR", "K_REVPAR"]);

const usd = (n: number) =>
  Math.abs(n) < 0.005 ? "—"
    : (n < 0 ? "(" : "") + "$" + Math.abs(n).toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");
const num = (n: number) => (n ? n.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "—");
const pct = (n: number) => (n ? (n * 100).toFixed(1) + "%" : "—");

const TD: React.CSSProperties = {
  padding: "3px 8px", textAlign: "right", fontSize: 11.5, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = { padding: "3px 10px", fontSize: 12 };

/** El primero de un tipo, para arrancar en lo obvio sin quitarle la opción de
 *  cambiar. Owner, 2026-08-28: «siempre aparece actual y el otro budget, pero
 *  con opción a cambiar». */
function primeroDe(escenarios: Scenario[], tipo: string): string {
  return escenarios.find(s => s.type === tipo)?.id || escenarios[0]?.id || "";
}

export default function DoceMeses({ escenarios, inicial }: {
  escenarios: Scenario[];
  /** El escenario que la pantalla ya tenía elegido, para no arrancar en blanco. */
  inicial?: string;
}) {
  /** Dos paneles, no dos pantallas: el de ACTUAL y el de BUDGET. Cada uno
   *  recuerda SU versión, así cambiar de panel no pierde lo que se eligió en el
   *  otro — que es lo que pasaría con un solo selector compartido. */
  const [panel, setPanel] = useState<"actual" | "budget">("actual");
  const [vActual, setVActual] = useState("");
  const [vBudget, setVBudget] = useState("");
  const scenarioId = panel === "actual" ? vActual : vBudget;
  const setScenarioId = panel === "actual" ? setVActual : setVBudget;
  const [datos, setDatos] = useState<PLDoceMeses | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!escenarios.length) return;
    setVActual(x => x || primeroDe(escenarios, "ACTUAL"));
    setVBudget(x => x || inicial || primeroDe(escenarios, "BUDGET"));
  }, [escenarios, inicial]);

  const cargar = useCallback(async () => {
    if (!scenarioId) return;
    setCargando(true); setError(null);
    try {
      setDatos(await getPLDoceMeses(scenarioId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el año");
      setDatos(null);
    } finally { setCargando(false); }
  }, [scenarioId]);

  useEffect(() => { cargar(); }, [cargar]);

  /** {code: [12 valores]} — los KPI salen de `kpis`, el resto de las líneas. */
  const serie = useMemo(() => {
    const out: Record<string, number[]> = {};
    for (const f of FILAS) out[f.code] = Array(12).fill(0);
    for (const m of datos?.meses ?? []) {
      const i = m.month - 1;
      out.K_ROOMS_AVAIL[i] = m.kpis.rooms_available;
      out.K_ROOMS_OCC[i] = m.kpis.rooms_occupied;
      out.K_OCC[i] = m.kpis.occupancy_pct;
      out.K_ADR[i] = m.kpis.adr;
      out.K_REVPAR[i] = m.kpis.revpar;
      for (const l of m.lines) {
        if (l.line_code in out && !KPI.has(l.line_code)) {
          out[l.line_code][i] = l.amount_usd;
        }
      }
    }
    return out;
  }, [datos]);

  /**
   * El total del año. ⚠️ **La ocupación, el ADR y el RevPAR NO se suman: son
   * razones.** Se rederivan con los doce meses de numerador y denominador —
   * promediarlos le daría el mismo peso a un mes lleno que a uno cerrado.
   */
  const anual = useCallback((code: string) => {
    const s = serie[code] ?? [];
    const av = (serie.K_ROOMS_AVAIL ?? []).reduce((a, b) => a + b, 0);
    const oc = (serie.K_ROOMS_OCC ?? []).reduce((a, b) => a + b, 0);
    if (code === "K_OCC") return av ? oc / av : 0;
    if (code === "K_ADR" || code === "K_REVPAR") {
      // El ingreso de habitaciones del año, reconstruido de ADR × noches.
      const rev = (serie.K_ADR ?? []).reduce(
        (t, adr, i) => t + adr * ((serie.K_ROOMS_OCC ?? [])[i] ?? 0), 0);
      return code === "K_ADR" ? (oc ? rev / oc : 0) : (av ? rev / av : 0);
    }
    return s.reduce((a, b) => a + b, 0);
  }, [serie]);

  const fmt = (code: string, v: number) =>
    code === "K_OCC" ? pct(v)
      : code === "K_ROOMS_AVAIL" || code === "K_ROOMS_OCC" ? num(v)
        : usd(v);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                    marginBottom: 12 }}>
        <nav aria-label="Panel" style={{ display: "inline-flex", borderRadius: 6,
             overflow: "hidden", border: "1px solid var(--border-medium)" }}>
          {([["actual", "12 meses Actual"], ["budget", "12 meses Budget"]] as const)
            .map(([k, r], i) => (
              <button key={k} onClick={() => setPanel(k)} style={{
                padding: "5px 13px", fontSize: 12, fontWeight: 600, border: "none",
                borderLeft: i ? "1px solid var(--border-medium)" : "none",
                cursor: panel === k ? "default" : "pointer",
                background: panel === k ? "var(--brand)" : "var(--bg-surface)",
                color: panel === k ? "#fff" : "var(--text-primary)",
              }}>{r}</button>
            ))}
        </nav>

        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)" }}>
          VERSIÓN
        </span>
        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}
          className="fin-input" style={{ fontSize: 12.5, padding: "5px 8px" }}>
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>{s.year} · {s.type} {s.version}</option>
          ))}
        </select>
        {datos && (
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {datos.escenario} · los doce meses · USD
          </span>
        )}
      </div>

      {error && (
        <div style={{ padding: 10, borderRadius: 5, fontSize: 12.5, marginBottom: 12,
                      background: "var(--bg-warning)" }}>{error}</div>
      )}
      {cargando && (
        <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Cargando…</div>
      )}

      {!cargando && datos && (
        <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
          <table className="fin-table" style={{ minWidth: 1250 }}>
            <thead>
              <tr>
                <th style={{ ...TDL, textAlign: "left" }}>INDICADOR</th>
                {MESES.map(m => <th key={m} style={TD}>{m}</th>)}
                <th style={{ ...TD, fontWeight: 800,
                             borderLeft: "2px solid var(--border-medium)" }}>Año</th>
              </tr>
            </thead>
            <tbody>
              {FILAS.map(f => {
                const s = serie[f.code] ?? [];
                const tot = anual(f.code);
                return (
                  <tr key={f.code} style={{
                    background: f.fuerte ? "var(--bg-subtle)" : undefined,
                  }}>
                    <td style={{ ...TDL, fontWeight: f.fuerte ? 700 : 500,
                                 paddingLeft: f.sangria ? 24 : 10 }}>{f.label}</td>
                    {s.map((v, i) => (
                      <td key={i} className="mono" style={{ ...TD,
                        fontWeight: f.fuerte ? 700 : 400,
                        color: v < 0 ? "var(--negative)" : undefined,
                      }}>{fmt(f.code, v)}</td>
                    ))}
                    <td className="mono" style={{ ...TD, fontWeight: 800,
                      borderLeft: "2px solid var(--border-medium)",
                      color: tot < 0 ? "var(--negative)" : undefined,
                    }}>{fmt(f.code, tot)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
