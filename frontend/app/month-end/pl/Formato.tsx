"use client";
/**
 * El P&L en el formato del owner: la cascada completa, un mes por columna.
 *
 * Owner, 2026-09-02, entregando `julio FORMAT 2026.xlsx`: *«uno para ver el
 * detalle tal cual el formato»*.
 *
 * **Qué lo distingue de los otros dos cuadros que ya existen.**
 *
 * | | qué compara | qué muestra |
 * |---|---|---|
 * | `12 meses` | una versión | 17 líneas de resumen |
 * | `P&L Detail Full` | hasta 4 versiones | la cascada, en UN corte |
 * | **este** | una versión | **la cascada, mes a mes** |
 *
 * Es el cuadro que el owner arma a mano cada cierre: marzo a julio uno al lado
 * del otro, con todos los renglones. Los otros dos no lo dan — el primero
 * pierde el detalle y el segundo pierde los meses.
 *
 * **Sale del mismo endpoint que `12 meses`** (`/pl/{id}/doce-meses/`), que ya
 * devuelve los doce meses con TODAS sus líneas. Pedir uno nuevo sería el mismo
 * dato por otra puerta.
 *
 * ⚠️ **Las columnas son los meses CON MOVIMIENTO, no los doce.** Amarena abrió
 * en marzo: cinco columnas en cero al principio y cuatro al final empujan lo
 * que importa fuera de la pantalla. Un mes con saldo aparece solo.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getPLDoceMeses, type PLDoceMeses, type Scenario } from "@/lib/api";

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

/** Un renglón del cuadro. `sec` = encabezado de bloque, `det` = detalle,
 *  `tot` = total fuerte, `sub` = subtotal, `esp` = aire. */
type Clase = "sec" | "det" | "tot" | "sub" | "esp";

/**
 * La cascada, en el orden del libro del owner.
 *
 * ⚠️ **Los códigos son los del MOTOR** (`REV_*`, `OPEXP_*`, `OVH_*`), no los de
 * `report_line_config`. Es lo que devuelve `/doce-meses/`, y mezclarlos daría
 * renglones vacíos sin ningún error visible.
 *
 * Los grupos de OVERHEAD incluyen **Cafetería y Lavandería**, que el reporte
 * viejo no dibujaba: ahí es donde sale el sobrante que no alcanzó a repartirse
 * (owner, 2026-08-28), y esconderlo era exactamente el bug de mayo a julio.
 */
const CASCADA: { clase: Clase; label: string; code?: string }[] = [
  { clase: "sec", label: "REVENUE" },
  { clase: "det", label: "Rooms", code: "REV_ROOMS" },
  { clase: "det", label: "F&B", code: "REV_FB" },
  { clase: "det", label: "SPA", code: "REV_SPA" },
  { clase: "det", label: "Tours", code: "REV_TOURS" },
  { clase: "det", label: "Retail-Gift Shop", code: "REV_RETAIL" },
  { clase: "det", label: "Tienda", code: "REV_TIENDA" },
  { clase: "det", label: "Private Bar", code: "REV_PRIVATE_BAR" },
  { clase: "det", label: "Transportation", code: "REV_TRANSPORT" },
  { clase: "det", label: "Laundry", code: "REV_LAUNDRY" },
  { clase: "det", label: "Innoceana", code: "REV_INNOCEANA" },
  { clase: "det", label: "Crowther Lab", code: "REV_CROWTHER" },
  { clase: "det", label: "Sustainability", code: "REV_SUSTAINABILITY" },
  { clase: "det", label: "Area Recreativa", code: "REV_AREC" },
  { clase: "det", label: "Miscellaneous", code: "REV_MISC_OTHER" },
  { clase: "det", label: "Club Madresal", code: "REV_CLUB" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "TOTAL INCOMES", code: "TOTAL_REVENUES" },
  { clase: "esp", label: "" },

  { clase: "sec", label: "Operating Expenses" },
  { clase: "det", label: "Rooms", code: "OPEXP_ROOMS" },
  { clase: "det", label: "F&B", code: "OPEXP_FB" },
  { clase: "det", label: "SPA", code: "OPEXP_SPA" },
  { clase: "det", label: "Tours", code: "OPEXP_TOURS" },
  { clase: "det", label: "Retail-Gift Shop", code: "OPEXP_RETAIL" },
  { clase: "det", label: "Tienda", code: "OPEXP_TIENDA" },
  { clase: "det", label: "Private Bar", code: "OPEXP_PRIVATE_BAR" },
  { clase: "det", label: "Transportation", code: "OPEXP_TRANSPORT" },
  { clase: "det", label: "Laundry", code: "OPEXP_LAUNDRY" },
  { clase: "det", label: "Innoceana", code: "OPEXP_INNOCEANA" },
  { clase: "det", label: "Crowther Lab", code: "OPEXP_CROWTHER" },
  { clase: "det", label: "Club Madresal", code: "OPEXP_CLUB" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "Total Operationg expenses", code: "TOTAL_OPEXP" },
  { clase: "esp", label: "" },

  { clase: "sec", label: "Operating Profit" },
  { clase: "det", label: "Rooms", code: "OPPROFIT_ROOMS" },
  { clase: "det", label: "F&B", code: "OPPROFIT_FB" },
  { clase: "det", label: "SPA", code: "OPPROFIT_SPA" },
  { clase: "det", label: "Tours", code: "OPPROFIT_TOURS" },
  { clase: "det", label: "Retail-Gift Shop", code: "OPPROFIT_RETAIL" },
  { clase: "det", label: "Tienda", code: "OPPROFIT_TIENDA" },
  { clase: "det", label: "Private Bar", code: "OPPROFIT_PRIVATE_BAR" },
  { clase: "det", label: "Transportation", code: "OPPROFIT_TRANSPORT" },
  { clase: "det", label: "Laundry", code: "OPPROFIT_LAUNDRY" },
  { clase: "det", label: "Innoceana", code: "OPPROFIT_INNOCEANA" },
  { clase: "det", label: "Crowther Lab", code: "OPPROFIT_CROWTHER" },
  { clase: "det", label: "Sustainability", code: "OPPROFIT_SUSTAINABILITY" },
  { clase: "det", label: "Area Recreativa", code: "OPPROFIT_AREC" },
  { clase: "det", label: "Miscellaneos", code: "OPPROFIT_MISC_OTHER" },
  { clase: "det", label: "Club Madresal", code: "OPPROFIT_CLUB" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "OPERATING PROFIT", code: "TOTAL_OP_PROFIT" },
  { clase: "esp", label: "" },

  { clase: "sec", label: "OVERHEAD EXPENSES" },
  { clase: "det", label: "Administrations", code: "OVH_ADMIN" },
  { clase: "det", label: "Sales & Marketing", code: "OVH_SALES" },
  { clase: "det", label: "Maintenance", code: "OVH_MAINTENANCE" },
  { clase: "det", label: "Information System", code: "OVH_IT" },
  { clase: "det", label: "Utilities", code: "OVH_UTILITIES" },
  // Los dos departamentos de reparto. Su línea es el SOBRANTE que no alcanzó a
  // repartirse; en cero no se dibuja, y con saldo tiene que verse.
  { clase: "det", label: "Cafeteria", code: "OVH_CAFETERIA" },
  { clase: "det", label: "Laundry", code: "OVH_LAUNDRY_OPS" },
  { clase: "det", label: "Area Recreativa", code: "OVH_AREC" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "TOTAL OVERHEAD EXPENSES", code: "TOTAL_OVERHEAD" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "TOTAL GROSS OPERATING PROFIT", code: "GOP" },
  { clase: "esp", label: "" },

  { clase: "det", label: "RENT", code: "RENT" },
  { clase: "det", label: "MANAGEMENT FEES (3%)", code: "MGMT_FEE" },
  { clase: "det", label: "MANAGEMENT FEES (5%) Royalties", code: "ROYALTIES" },
  { clase: "sub", label: "TOTAL RENTA AND MANAGEMENT FEES", code: "TOTAL_MGMT_FEES" },
  { clase: "esp", label: "" },
  { clase: "det", label: "PROPERTIES INSURANCE", code: "PROPERTIES_INSURANCE" },
  { clase: "esp", label: "" },
  { clase: "det", label: "OTHER EXPENSES", code: "OTHER_EXPENSES" },
  { clase: "esp", label: "" },
  { clase: "sub", label: "TOTAL Owners Expenses", code: "TOTAL_NON_OP" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "EBITDA", code: "EBITDA_BEFORE" },
  { clase: "esp", label: "" },
  { clase: "det", label: "CAPITAL RESERVE", code: "CAPITAL_RESERVE" },
  { clase: "det", label: "LARGE CAPITAL EXPENDITURE", code: "LARGE_CAPEX" },
  { clase: "sub", label: "CAPITAL EXPENSE", code: "CAPITAL_EXPENSE" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "EBITDA AFTER CAPITAL", code: "EBITDA_AFTER" },
  { clase: "esp", label: "" },

  // ⚠️ El motor NO abre los financieros en tres. `LEASINGS_RENTS` y
  // `FINANCIAL_LOSSES` son vocabulario del reporte de dueños, no líneas que
  // `calculate_full_pl` emita: comparten cajón con los intereses. Ponerlas acá
  // dejaba tres renglones en cero para siempre, sin ningún error.
  { clase: "det", label: "BANK INTEREST / PERDIDAS FINANCIERAS", code: "BANK_INTEREST" },
  { clase: "sub", label: "FINANCIAL EXPENSES", code: "FINANCIAL_EXPENSES" },
  { clase: "esp", label: "" },
  { clase: "det", label: "DEPRECIATION", code: "DEPRECIATION" },
  { clase: "sub", label: "TOTAL DEPRECIATIONS", code: "TOTAL_DEPRECIATIONS" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "EARNINGS BEFORE INCOME TAXES", code: "EBT" },
  { clase: "det", label: "Income Tax (30%)", code: "INCOME_TAXES" },
  { clase: "esp", label: "" },
  { clase: "tot", label: "EARNINGS AFTER INCOME TAXES", code: "NET_PROFIT" },
];

const usd = (n: number) =>
  Math.abs(n) < 0.005 ? "—"
    : (n < 0 ? "(" : "") + Math.abs(n).toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");

const TD: React.CSSProperties = {
  padding: "3px 9px", textAlign: "right", fontSize: 11.5, whiteSpace: "nowrap",
};

function primeroDe(escenarios: Scenario[], tipo: string): string {
  return escenarios.find(s => s.type === tipo)?.id || escenarios[0]?.id || "";
}

export default function Formato({ escenarios, inicial, compacto = true }: {
  escenarios: Scenario[];
  inicial?: string;
  /** Esconder las líneas en cero TODOS los meses. Lo manda la pantalla, así el
   *  interruptor es uno solo para todos los sub-tabs. */
  compacto?: boolean;
}) {
  const [scenarioId, setScenarioId] = useState("");
  const [datos, setDatos] = useState<PLDoceMeses | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Enseñar los doce meses aunque estén vacíos. Apagado por defecto: Amarena
   *  abrió en marzo y nueve columnas en cero no dejan leer las cinco que hay. */
  const [todosLosMeses, setTodosLosMeses] = useState(false);

  useEffect(() => {
    if (!escenarios.length) return;
    setScenarioId(x => x || inicial || primeroDe(escenarios, "ACTUAL"));
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

  /** {code: [12 valores]} */
  const serie = useMemo(() => {
    const out: Record<string, number[]> = {};
    for (const m of datos?.meses ?? []) {
      for (const l of m.lines) {
        (out[l.line_code] ||= Array(12).fill(0))[m.month - 1] = l.amount_usd;
      }
    }
    return out;
  }, [datos]);

  /** Qué meses se dibujan. Un mes cuenta como «con movimiento» si su ingreso o
   *  su gasto total se movió — no si CUALQUIER línea tiene algo, porque el
   *  impuesto y la reserva arrastran ceros calculados todo el año. */
  const columnas = useMemo(() => {
    const todos = Array.from({ length: 12 }, (_, i) => i);
    if (todosLosMeses) return todos;
    const conMovimiento = todos.filter(i =>
      Math.abs(serie.TOTAL_REVENUES?.[i] ?? 0) >= 0.005
      || Math.abs(serie.TOTAL_OPEXP?.[i] ?? 0) >= 0.005
      || Math.abs(serie.TOTAL_OVERHEAD?.[i] ?? 0) >= 0.005);
    return conMovimiento.length ? conMovimiento : todos;
  }, [serie, todosLosMeses]);

  const valor = (code: string | undefined, i: number) =>
    code ? (serie[code]?.[i] ?? 0) : 0;

  /** Una línea está vacía si es cero en TODOS los meses dibujados.
   *
   *  ⚠️ `every`, no `some`: una línea que sólo tuvo saldo en junio tiene que
   *  seguir viéndose. Esconder es para el ruido permanente, no para los huecos. */
  const vacia = useCallback((code?: string) =>
    !!code && columnas.every(i => Math.abs(valor(code, i)) < 0.005),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [columnas, serie]);

  /** Un encabezado de bloque cuyo detalle quedó todo escondido tampoco se
   *  dibuja: si no, quedan rótulos sueltos sobre la nada. */
  const visibles = useMemo(() => {
    if (!compacto) return CASCADA;
    const paso1 = CASCADA.filter(f =>
      f.clase === "sec" || f.clase === "esp" || !vacia(f.code));
    return paso1.filter((f, i) => {
      if (f.clase !== "sec") return true;
      for (let j = i + 1; j < paso1.length; j++) {
        if (paso1[j].clase === "sec") break;
        if (paso1[j].clase !== "esp") return true;
      }
      return false;
    });
  }, [compacto, vacia]);

  const total = (code: string | undefined) =>
    columnas.reduce((s, i) => s + valor(code, i), 0);

  const estilo = (clase: Clase): React.CSSProperties =>
    clase === "sec"
      ? { fontWeight: 800, fontSize: 12, textTransform: "uppercase",
          background: "var(--bg-surface)" }
      : clase === "tot"
        ? { fontWeight: 800, borderTop: "1px solid var(--border-medium)" }
        : clase === "sub"
          ? { fontWeight: 700 }
          : {};

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "center",
                    flexWrap: "wrap", marginBottom: 12 }}>
        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}
          style={{ padding: "5px 9px", fontSize: 12,
                   border: "1px solid var(--border-medium)", borderRadius: 5,
                   background: "var(--bg-surface)", color: "var(--text-primary)" }}>
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>
              {s.type} · {s.version} · {s.year}
            </option>
          ))}
        </select>
        <button onClick={() => setTodosLosMeses(x => !x)}
          title="Amarena abrió en marzo: los meses sin movimiento se esconden para que quepan los que hay"
          style={{ padding: "5px 11px", fontSize: 12, borderRadius: 5,
                   cursor: "pointer", background: "var(--bg-surface)",
                   color: "var(--text-secondary)",
                   border: "1px solid var(--border-medium)" }}>
          {todosLosMeses ? "☑ Los 12 meses" : "☐ Los 12 meses"}
        </button>
        {cargando && <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          cargando…
        </span>}
        {error && <span style={{ fontSize: 12, color: "var(--negative)" }}>{error}</span>}
      </div>

      <div className="fin-scroll-x">
        <table style={{ borderCollapse: "collapse", minWidth: 620 }}>
          <thead>
            <tr>
              <th style={{ ...TD, textAlign: "left", minWidth: 250,
                           position: "sticky", left: 0, zIndex: 1,
                           background: "var(--bg-page, var(--bg-surface))" }}>
                Grupo / Cuenta
              </th>
              {columnas.map(i => (
                <th key={i} style={{ ...TD, fontWeight: 700, minWidth: 108 }}>
                  {MESES[i]} {datos?.year} · Real
                </th>
              ))}
              <th style={{ ...TD, fontWeight: 800, minWidth: 118,
                           borderLeft: "2px solid var(--border-medium)" }}>
                Acumulado
              </th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((f, n) => f.clase === "esp" ? (
              <tr key={n}><td colSpan={columnas.length + 2} style={{ height: 7 }} /></tr>
            ) : (
              <tr key={n} style={estilo(f.clase)}>
                <td style={{ padding: "3px 10px", fontSize: 12,
                             paddingLeft: f.clase === "det" ? 22 : 10,
                             position: "sticky", left: 0,
                             background: "var(--bg-page, var(--bg-surface))" }}>
                  {f.label}
                </td>
                {columnas.map(i => (
                  <td key={i} style={TD}>
                    {f.clase === "sec" ? "" : usd(valor(f.code, i))}
                  </td>
                ))}
                <td style={{ ...TD, fontWeight: 700,
                             borderLeft: "2px solid var(--border-medium)" }}>
                  {f.clase === "sec" ? "" : usd(total(f.code))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ fontSize: 11.5, color: "var(--text-secondary)",
                  marginTop: 12, maxWidth: 780, lineHeight: 1.6 }}>
        ⚠️ <b>El acumulado suma las columnas que se ven.</b> Con los meses sin
        movimiento escondidos da lo mismo —son cero—, pero si algún día se
        esconde un mes con saldo, la suma cambia con él y no sería el año.
      </p>
    </div>
  );
}
