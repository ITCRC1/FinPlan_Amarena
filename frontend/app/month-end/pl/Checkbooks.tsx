"use client";
/**
 * Los checkbooks, para CONSULTAR: sin entrar a Planning y sin poder editar.
 *
 * Owner, 2026-09-03: *«algunos usuarios no van a tener acceso a Planning por
 * obvias razones; necesito un sub-tab en Cierre mensual para poder generar los
 * checkbooks, la misma vista de Planning pero para visualizar qué hay en los
 * checkbooks a modo de reportes: opex por departamento, salario por
 * departamento, costo y gastos de propietario»*.
 *
 * ## Es de LECTURA, y eso es la mitad del pedido
 *
 * La pantalla de Planning es un formulario: cada celda es un campo que guarda.
 * Acá no hay un solo `input`. Quien no debe tocar el presupuesto entra igual y
 * ve lo mismo, y no hay forma de que un clic distraído cambie un número — que
 * es exactamente por lo que no tiene acceso a Planning.
 *
 * ⚠️ Y no se resuelve escondiendo el botón de guardar: un formulario de sólo
 * lectura sigue mandando lo que se escriba si alguien encuentra la ruta. Acá el
 * único endpoint que se toca es un `GET`.
 *
 * ## De dónde salen los números
 *
 * De `/gasto-por-clase/detalle-de-celda/`, el mismo que abre el desplegable al
 * tocar una línea del P&L. Reusarlo no es ahorro: es lo que garantiza que lo
 * que se ve acá **suma exactamente** la línea del reporte. Un endpoint propio
 * sería una segunda aritmética, y el día que difiera no habría cómo saber cuál
 * de las dos tiene razón.
 *
 * Por eso también hereda su honestidad: cada versión declara si su detalle sale
 * del **mayor** o del **auxiliar** —un presupuesto no tiene mayor cargado, pero
 * cada línea de su checkbook lleva su cuenta—.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getDetalleDeCelda, type DetalleCelda, type Scenario } from "@/lib/api";

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

/** Los cuatro checkbooks que el owner pidió, con el nombre que usa él. */
const LIBROS = [
  { clase: "opex", rotulo: "Opex" },
  { clase: "payroll", rotulo: "Salarios" },
  { clase: "cost", rotulo: "Costo de ventas" },
  { clase: "property", rotulo: "Gastos de propiedad" },
] as const;

const usd = (n: number) =>
  Math.abs(n) < 0.005 ? "—"
    : (n < 0 ? "(" : "") + Math.abs(n).toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");

const TD: React.CSSProperties = {
  padding: "4px 9px", textAlign: "right", fontSize: 11.5, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = { padding: "4px 10px", fontSize: 11.5 };
const SEL: React.CSSProperties = {
  padding: "5px 9px", fontSize: 12, borderRadius: 5,
  border: "1px solid var(--border-medium)",
  background: "var(--bg-surface)", color: "var(--text-primary)",
};

export default function Checkbooks({ escenarios, scenarioIds, deptos }: {
  escenarios: Scenario[];
  /** Las ranuras ocupadas de la pantalla. */
  scenarioIds: string[];
  /** `{código: nombre}` del catálogo, para el selector. */
  deptos: Record<string, string>;
}) {
  const [clase, setClase] = useState<string>("opex");
  const [dept, setDept] = useState<string>("");      // "" = todos
  const [datos, setDatos] = useState<DetalleCelda | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = useCallback(async () => {
    if (!scenarioIds.length) { setDatos(null); return; }
    setCargando(true); setError(null);
    try {
      setDatos(await getDetalleDeCelda(scenarioIds, clase, dept));
    } catch (e) {
      setDatos(null);
      setError(e instanceof Error ? e.message : "No se pudo cargar");
    } finally {
      setCargando(false);
    }
  }, [scenarioIds, clase, dept]);

  useEffect(() => { cargar(); }, [cargar]);

  /** Los departamentos que ESTE checkbook usa.
   *
   *  ⚠️ Se sacan del catálogo completo pero se ordenan por código: ofrecer los
   *  sesenta y cinco del catálogo en una clase que usa ocho hace buscar el que
   *  sirve entre los que no. El «todos» de arriba resuelve el caso de no saber
   *  cuál. */
  const opciones = useMemo(
    () => Object.keys(deptos).sort(), [deptos]);

  const versiones = datos?.versiones ?? [];
  const filas = useMemo(() => {
    const f = (datos?.filas ?? []).map(x => ({
      ...x,
      total: versiones.reduce(
        (a, v) => a + (x.series[v.scenario_id] ?? []).reduce((s, n) => s + n, 0), 0),
    }));
    return f.filter(x => Math.abs(x.total) >= 0.005)
            .sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
  }, [datos, versiones]);

  const rotuloLibro = LIBROS.find(l => l.clase === clase)?.rotulo ?? clase;

  return (
    <div>
      <p style={{ fontSize: 12.5, color: "var(--text-secondary)",
                  marginBottom: 12, maxWidth: 900, lineHeight: 1.6 }}>
        Lo que hay cargado en los checkbooks, <b>sólo para consultar</b>: los
        mismos números que Planning, sin poder editarlos. Cada versión dice si
        su detalle sale del <b>mayor</b> o de su <b>auxiliar</b> — un
        presupuesto no tiene mayor cargado, pero cada línea de su checkbook
        lleva su cuenta contable.
      </p>

      {/* ── Los cuatro libros, como sub-tabs de SEGUNDO nivel ──────────────
          Owner, 2026-09-03: «puede ser que se ponga un sub tab CHECKBOOKS e
          internamente se pongan las 4 en sub tab del sub».

          ⚠️ Van con subrayado y no como los botones-pastilla de arriba: dos
          filas de pastillas idénticas se leen como un solo nivel, y entonces
          «Opex» del checkbook parece hermano de «Opex x Depto», que es otro
          reporte. La forma tiene que decir cuál está adentro de cuál. */}
      <div style={{ display: "flex", gap: 2, alignItems: "flex-end",
                    flexWrap: "wrap", marginBottom: 14,
                    borderBottom: "1px solid var(--border-medium)" }}>
        {LIBROS.map(l => (
          <button key={l.clase} onClick={() => setClase(l.clase)} style={{
            padding: "7px 16px", fontSize: 12.5, cursor: "pointer",
            fontWeight: clase === l.clase ? 700 : 500,
            background: "transparent", border: "none",
            borderBottom: clase === l.clase
              ? "2px solid var(--brand)" : "2px solid transparent",
            color: clase === l.clase ? "var(--brand)" : "var(--text-secondary)",
            marginBottom: -1,
          }}>{l.rotulo}</button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 6, alignItems: "center",
                    flexWrap: "wrap", marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          Departamento
        </span>
        <select value={dept} onChange={e => setDept(e.target.value)} style={SEL}>
          <option value="">Todos</option>
          {opciones.map(c => (
            <option key={c} value={c}>{c} · {deptos[c]}</option>
          ))}
        </select>
        {cargando && (
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>cargando…</span>
        )}
        {error && <span style={{ fontSize: 12, color: "var(--negative)" }}>{error}</span>}
      </div>

      {/* ⚠️ El gasto de propiedad se abre por CUENTA, no por departamento: vive
          todo en el 0250. Decirlo evita que el selector de arriba parezca roto
          cuando no cambia nada. */}
      {clase === "property" && dept && (
        <p style={{ fontSize: 11.5, color: "var(--text-secondary)",
                    marginBottom: 10 }}>
          ⚠️ El gasto de propiedad no se abre por departamento —vive todo en el
          0250—: se abre por cuenta, así que el filtro de arriba no aplica acá.
        </p>
      )}

      {versiones.map(v => {
        const total = (serie: number[] | undefined) =>
          (serie ?? []).reduce((a, n) => a + n, 0);
        const mes = (i: number) =>
          filas.reduce((a, f) => a + ((f.series[v.scenario_id] ?? [])[i] ?? 0), 0);
        return (
          <div key={v.scenario_id} style={{ marginBottom: 26 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10,
                          marginBottom: 6 }}>
              <b style={{ fontSize: 13, color: "var(--brand)" }}>{v.escenario}</b>
              <span style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
                {rotuloLibro}
                {dept && clase !== "property" ? ` · ${dept} · ${deptos[dept] ?? ""}` : " · todos los departamentos"}
                {" · "}{v.fuente}
              </span>
            </div>
            <div className="fin-scroll-x">
              <table style={{ borderCollapse: "collapse", minWidth: 900 }}>
                <thead>
                  <tr>
                    <th style={{ ...TDL, textAlign: "left", fontWeight: 800,
                                 minWidth: 240, position: "static",
                                 borderBottom: "2px solid var(--text-primary)" }}>
                      Cuenta
                    </th>
                    {MESES.map(m => (
                      <th key={m} style={{ ...TD, fontWeight: 700, minWidth: 82,
                                           position: "static",
                                           borderBottom: "2px solid var(--text-primary)" }}>
                        {m}
                      </th>
                    ))}
                    <th style={{ ...TD, fontWeight: 800, minWidth: 100,
                                 position: "static",
                                 borderLeft: "2px solid var(--border-medium)",
                                 borderBottom: "2px solid var(--text-primary)" }}>
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filas.map(f => {
                    const serie = f.series[v.scenario_id] ?? [];
                    return (
                      <tr key={f.cuenta}>
                        <td style={TDL}>
                          <span className="mono" style={{ color: "var(--text-secondary)",
                                                          marginRight: 7 }}>
                            {f.cuenta}
                          </span>
                          {f.nombre}
                        </td>
                        {MESES.map((_, i) => (
                          <td key={i} className="mono" style={{
                            ...TD,
                            color: (serie[i] ?? 0) < 0 ? "var(--negative)" : undefined,
                          }}>{usd(serie[i] ?? 0)}</td>
                        ))}
                        <td className="mono" style={{
                          ...TD, fontWeight: 700,
                          borderLeft: "2px solid var(--border-medium)",
                          color: total(serie) < 0 ? "var(--negative)" : undefined,
                        }}>{usd(total(serie))}</td>
                      </tr>
                    );
                  })}
                  <tr style={{ background: "var(--bg-elevated, #EDF1F5)" }}>
                    <td style={{ ...TDL, fontWeight: 800,
                                 borderTop: "2px solid var(--text-primary)" }}>
                      TOTAL
                    </td>
                    {MESES.map((_, i) => (
                      <td key={i} className="mono" style={{
                        ...TD, fontWeight: 800,
                        borderTop: "2px solid var(--text-primary)",
                        color: mes(i) < 0 ? "var(--negative)" : undefined,
                      }}>{usd(mes(i))}</td>
                    ))}
                    <td className="mono" style={{
                      ...TD, fontWeight: 800,
                      borderTop: "2px solid var(--text-primary)",
                      borderLeft: "2px solid var(--border-medium)",
                    }}>
                      {usd(filas.reduce((a, f) => a + total(f.series[v.scenario_id]), 0))}
                    </td>
                  </tr>
                  {!filas.length && !cargando && (
                    <tr><td colSpan={14} style={{ ...TDL, color: "var(--text-secondary)" }}>
                      Este checkbook no tiene nada cargado para esa selección.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}

      {!versiones.length && !cargando && !error && (
        <p style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
          Elegí al menos una versión en las ranuras de arriba.
        </p>
      )}
    </div>
  );
}
