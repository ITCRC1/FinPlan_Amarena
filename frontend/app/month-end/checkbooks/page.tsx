"use client";
/**
 * Los checkbooks, para CONSULTAR: pantalla propia, sin entrar a Planning.
 *
 * Owner, 2026-09-03: *«algunos usuarios no van a tener acceso a Planning por
 * obvias razones; necesito poder generar los checkbooks, la misma vista de
 * Planning pero para visualizar qué hay a modo de reportes»* y, después de
 * verlo dentro de Cierre de Mes: *«favor mueve el checkbook afuera, donde está
 * Full P&L Ejecutivo»*.
 *
 * ⚠️ **Está en el MENÚ, no en un sub-tab, y eso cambia quién lo encuentra.**
 * Un sub-tab de Cierre de Mes obliga a entrar al cierre, elegir versiones y
 * saber que el checkbook está ahí adentro. El que no tiene acceso a Planning
 * viene justamente a mirar un checkbook: tiene que ser una entrada del menú,
 * al lado de los otros reportes.
 *
 * El cuadro es el MISMO componente que se usaba adentro (`Checkbooks.tsx`), no
 * una copia: una segunda versión de la misma tabla es cómo terminan mostrando
 * números distintos.
 */
import { useEffect, useMemo, useState } from "react";

import Checkbooks from "@/app/month-end/pl/Checkbooks";
import { getDetalleDeCelda, getGastoPorClase, getScenarios,
         type Scenario } from "@/lib/api";
import { cuadroCheckbookCortes } from "@/lib/checkbookCortes";
import { bajarCuadros, type Cuadro } from "@/lib/exportCuadro";
import { sembrarTres, useEscenarioDe } from "@/lib/escenarioPreferido";
import { HOTEL_ID } from "@/lib/hotel";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"];

/** Los cuatro libros, con el nombre que usa el owner. Acá para el Excel; el
 *  componente tiene la misma lista para sus sub-tabs. */
const LIBROS = [["opex", "Opex"], ["payroll", "Salarios"],
                ["cost", "Costo de ventas"],
                ["property", "Gastos de propiedad"]] as const;

const SEL: React.CSSProperties = {
  padding: "6px 10px", fontSize: 12.5, borderRadius: 6,
  border: "1px solid var(--border-medium)",
  background: "var(--bg-surface)", color: "var(--text-primary)",
};

export default function CheckbooksPage() {
  const [escenarios, setEscenarios] = useState<Scenario[]>([]);
  const [deptos, setDeptos] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  /** Abre en el FORECAST vivo: es el checkbook que se está trabajando. Y se
   *  queda donde lo dejen — ver `useEscenarioDe`. */
  const [scenarioId, setScenarioId] = useEscenarioDe(
    "month-end/checkbooks", escenarios, "forecast");

  /** Cuál de las dos vistas fijas (owner, 2026-09-30).
   *
   *  ⚠️ Vive acá y no adentro del cuadro porque las dos necesitan cosas
   *  distintas de esta pantalla: los doce meses van de una versión, y los tres
   *  cortes necesitan las TRES. Y el Excel baja la que esté puesta. */
  const [vista, setVista] = useState<"12m" | "cortes">("12m");
  const [mes, setMes] = useState(0);   // 0 = todavía sin sembrar

  /** Las tres versiones de la comparación: Actual, Budget y Forecast.
   *
   *  ⚠️ Salen de `sembrarTres` —la regla del owner— y no de un
   *  `escenarios.find(...)`: `GET /scenarios/` ordena por año descendente, así
   *  que el primer BUDGET de la lista es el Working 2035 y la comparación
   *  abriría contra un presupuesto real, vacío y de otro año, sin que nada
   *  fallara. */
  const tres = useMemo(() => sembrarTres(escenarios), [escenarios]);

  /** El mes del cierre. Arranca en el corte del Forecast —hasta dónde hay
   *  actuales cargados—, que es el mes del que se está hablando. Sin eso habría
   *  que elegirlo a mano cada vez para ver algo que no esté vacío. */
  useEffect(() => {
    if (mes || !escenarios.length) return;
    const f = escenarios.find(s => s.id === tres.forecast);
    setMes(f?.actuals_through || new Date().getMonth() + 1);
  }, [escenarios, tres, mes]);

  useEffect(() => {
    getScenarios(HOTEL_ID).then(setEscenarios)
      .catch(e => setError(e instanceof Error ? e.message : "No se pudieron cargar los escenarios"));
  }, []);

  /** El catálogo de departamentos, para el selector.
   *
   *  ⚠️ Sale de `gasto-por-clase`, que es el mismo mapa que usa Cierre de Mes.
   *  Pedirlo a otro lado daría un selector con nombres distintos de los que se
   *  ven en el reporte de al lado. */
  useEffect(() => {
    if (!scenarioId) return;
    let vivo = true;
    getGastoPorClase([scenarioId], false)
      .then(g => { if (vivo) setDeptos(g.departamentos ?? {}); })
      .catch(() => { if (vivo) setDeptos({}); });
    return () => { vivo = false; };
  }, [scenarioId]);

  /** Qué versiones pide el cuadro. En los doce meses, la elegida; en los tres
   *  cortes, las tres — la comparación no existe sin ellas. */
  const ids = useMemo(() => (
    vista === "cortes"
      ? [tres.actual, tres.budget, tres.forecast].filter(Boolean)
      : (scenarioId ? [scenarioId] : [])
  ), [vista, tres, scenarioId]);

  /** Los cuatro libros a un Excel, una hoja cada uno.
   *
   *  ⚠️ Baja los CUATRO y con TODOS los departamentos, no lo que esté
   *  seleccionado en pantalla. Un archivo que sale distinto según el filtro que
   *  estaba puesto cuando alguien lo bajó no se puede archivar: dos copias del
   *  mismo mes dirían cosas distintas. */
  async function bajarExcel() {
    if (!ids.length) return;
    const etiqueta = escenarios.find(s => s.id === scenarioId);
    const nombre = vista === "cortes"
      ? `Cortes_${MESES[mes - 1] ?? ""}`
      : (etiqueta ? `${etiqueta.type}_${etiqueta.version}_${etiqueta.year}`
                  : scenarioId);
    const MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                  "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const cuadros: Cuadro[] = [];

    // ── La vista de cortes ───────────────────────────────────────────────
    //
    // ⚠️ Arma el MISMO cuadro que la pantalla (`cuadroCheckbookCortes`). Dos
    // armados del mismo reporte empiezan iguales y se separan en el primer
    // arreglo que alguien hace de un lado.
    if (vista === "cortes") {
      for (const [clase, rotulo] of LIBROS) {
        try {
          const d = await getDetalleDeCelda(ids, clase, "");
          const c = cuadroCheckbookCortes(rotulo, d, mes, escenarios, "", deptos);
          // Sólo el TOTAL y nada más: el libro está vacío para esas versiones.
          if (c.filas.length > 1) cuadros.push(c);
        } catch { /* un libro que falla no se lleva los otros tres */ }
      }
      if (!cuadros.length) { alert("No hay nada cargado para bajar."); return; }
      try { await bajarCuadros(`Checkbooks_${nombre}`, cuadros); }
      catch (e) { alert(e instanceof Error ? e.message : "No se pudo generar el Excel"); }
      return;
    }

    for (const [clase, rotulo] of LIBROS) {
      try {
        const d = await getDetalleDeCelda([scenarioId], clase, "");
        const vivas = d.filas.filter(f =>
          (f.series[scenarioId] ?? []).some(n => Math.abs(n) >= 0.005));
        if (!vivas.length) continue;
        cuadros.push({
          titulo: `Checkbook · ${rotulo}`,
          subtitulo: `${d.versiones[0]?.escenario ?? ""} · ${d.versiones[0]?.fuente ?? ""} · USD`,
          hoja: `Checkbook ${rotulo}`.slice(0, 31),
          columnas: [
            { label: "Cuenta", ancho: 10, formato: "texto" },
            { label: "Nombre", ancho: 34, formato: "texto" },
            ...MES3.map(m => ({ label: m, ancho: 13, formato: "usd2" as const })),
            { label: "Total", ancho: 15, formato: "usd2" as const },
          ],
          filas: vivas.map(f => {
            const serie = f.series[scenarioId] ?? [];
            return {
              label: f.cuenta, es_total: false,
              valores: [f.nombre, ...MES3.map((_, i) => serie[i] ?? 0),
                        serie.reduce((a, n) => a + n, 0)],
            };
          }),
        });
      } catch { /* un libro que falla no se lleva los otros tres */ }
    }
    if (!cuadros.length) { alert("No hay nada cargado para bajar."); return; }
    try {
      await bajarCuadros(`Checkbooks_${nombre}`, cuadros);
    } catch (e) {
      alert(e instanceof Error ? e.message : "No se pudo generar el Excel");
    }
  }

  return (
    <div className="pag pag-ancha" style={{ padding: "18px 22px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10,
                    flexWrap: "wrap", marginBottom: 12 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Checkbooks</h1>

        {/* ── Las DOS vistas fijas ──────────────────────────────────────────
            Owner, 2026-09-30: «en realidad que sean 2 vistas fijas: 12 meses,
            y mes-YTD-Full year». Son dos preguntas distintas —cómo se reparte
            el año, y cómo va contra el presupuesto—, no dos formatos del mismo
            cuadro, y por eso son botones y no un menú perdido. */}
        <div style={{ display: "flex", gap: 0, borderRadius: 6, overflow: "hidden",
                      border: "1px solid var(--border-medium)" }}>
          {([["12m", "12 meses"], ["cortes", "Mes · YTD · Full Year"]] as const)
            .map(([v, rot]) => (
            <button key={v} onClick={() => setVista(v)} style={{
              padding: "6px 13px", fontSize: 12.5, cursor: "pointer", border: "none",
              fontWeight: vista === v ? 700 : 500,
              background: vista === v ? "var(--brand)" : "var(--bg-surface)",
              color: vista === v ? "#fff" : "var(--text-secondary)",
            }}>{rot}</button>
          ))}
        </div>

        {/* La versión sólo elige en los doce meses: en los tres cortes van las
            tres —Actual, Budget y Forecast— porque la comparación las necesita,
            y un selector que no cambia nada se lee como roto. */}
        {vista === "12m" ? (
          <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}
                  style={SEL}>
            {escenarios.map(s => (
              <option key={s.id} value={s.id}>{s.type} · {s.version} · {s.year}</option>
            ))}
          </select>
        ) : (
          <>
            <select value={mes} onChange={e => setMes(Number(e.target.value))}
                    style={SEL} title="El mes del cierre: define el corte del mes y hasta dónde llega el YTD">
              {MESES.map((m, i) => (
                <option key={m} value={i + 1}>{m}</option>
              ))}
            </select>
            <span style={{ fontSize: 11.5, color: "var(--text-secondary)",
                           maxWidth: 420, lineHeight: 1.5 }}>
              Actual · Budget · Forecast — {ids.length < 3
                ? "falta alguna de las tres versiones del año"
                : "las tres versiones del año"}
            </span>
          </>
        )}
        <button onClick={bajarExcel}
          title="Los cuatro checkbooks en un Excel, una hoja cada uno y con todos los departamentos"
          style={{ ...SEL, cursor: "pointer", fontWeight: 600,
                   background: "var(--accent-excel)", color: "#fff",
                   border: "none" }}>⬇ Excel</button>
        {error && (
          <span style={{ fontSize: 12.5, color: "var(--negative)" }}>{error}</span>
        )}
      </div>

      <Checkbooks escenarios={escenarios} scenarioIds={ids} deptos={deptos}
                  vista={vista} mes={mes || 12} />
    </div>
  );
}
