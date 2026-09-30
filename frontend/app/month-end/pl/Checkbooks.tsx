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
 *
 * ## Dos vistas fijas, no un selector de todo
 *
 * Owner, 2026-09-30: *«además de la vista de 12 meses, quiero también tener la
 * opción de comparar el actual versus Budget del mes, YTD del mes y Budget, y
 * Full year Forecast versus Budget. en realidad que sean 2 vistas fijas»*.
 *
 * | vista | qué contesta |
 * |---|---|
 * | **12 meses** | cómo se reparte el año, una versión a la vez |
 * | **Mes · YTD · Full Year** | cómo va contra el presupuesto, las tres juntas |
 *
 * ⚠️ La segunda arma su cuadro con `lib/checkbookCortes`, que a su vez usa
 * `lib/tresCortes` sin copiarlo: el checkbook y el P&L tienen que cortar el año
 * por los mismos meses y restar el mismo par, o el detalle diría una variación
 * y el reporte otra sobre los mismos datos.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getDetalleDeCelda, type DetalleCelda, type Scenario } from "@/lib/api";
import { anchoDelCorte, cortesDelCheckbook,
         cuadroCheckbookCortes } from "@/lib/checkbookCortes";
import { ROTULO_VAR, vistaDe } from "@/lib/tresCortes";

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
/** La raya que separa un corte del siguiente. */
const BL = "2px solid var(--border-medium)";

const SEL: React.CSSProperties = {
  padding: "5px 9px", fontSize: 12, borderRadius: 5,
  border: "1px solid var(--border-medium)",
  background: "var(--bg-surface)", color: "var(--text-primary)",
};

export default function Checkbooks({ escenarios, scenarioIds, deptos,
                                    vista = "12m", mes = 12,
                                    visibles, actualDelFullYear }: {
  escenarios: Scenario[];
  /** Las ranuras ocupadas de la pantalla. En la vista de cortes son las TRES
   *  —Actual, Budget, Forecast—, que es lo que la comparación necesita. */
  scenarioIds: string[];
  /** `{código: nombre}` del catálogo, para el selector. */
  deptos: Record<string, string>;
  /** Cuál de las dos vistas fijas. La manda la pantalla porque el Excel baja
   *  la que esté puesta, y el selector de versiones cambia con ella. */
  vista?: "12m" | "cortes";
  /** El mes del cierre: define el corte «mes» y hasta dónde llega el YTD. */
  mes?: number;
  /** Las versiones que SON columnas, en orden. El cuadro puede traer una más
   *  —el Forecast Current— que se pide y no se dibuja aparte. */
  visibles?: string[];
  /** Quién ocupa la primera columna del full year. Ver `checkbookCortes`. */
  actualDelFullYear?: string;
}) {
  const [clase, setClase] = useState<string>("opex");
  const [dept, setDept] = useState<string>("");      // "" = todos
  const [datos, setDatos] = useState<DetalleCelda | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  /** ⚠️ Se pide SIEMPRE el libro completo —sin filtrar departamento— y el
   *  filtro se aplica acá.
   *
   *  Dos razones. Una: los departamentos del selector salen de los datos, no de
   *  un catálogo aparte; ofrecer los sesenta y cinco del catálogo en un libro
   *  que usa ocho hace buscar el que sirve entre los que no. Y dos: el catálogo
   *  llegaba vacío —`gasto-por-clase` sólo devuelve los nombres cuando se le
   *  pide el detalle— y el selector se quedaba con «Todos» y nada más
   *  (owner, 2026-09-03: «sólo existe la opción Todos, no hay más opciones»).
   */
  const cargar = useCallback(async () => {
    if (!scenarioIds.length) { setDatos(null); return; }
    setCargando(true); setError(null);
    try {
      setDatos(await getDetalleDeCelda(scenarioIds, clase, ""));
    } catch (e) {
      setDatos(null);
      setError(e instanceof Error ? e.message : "No se pudo cargar");
    } finally {
      setCargando(false);
    }
  }, [scenarioIds, clase]);

  useEffect(() => { cargar(); }, [cargar]);

  /** Los departamentos que ESTE libro usa de verdad, sacados de sus filas. */
  const opciones = useMemo(() => {
    const vistos = new Map<string, string>();
    for (const f of datos?.filas ?? []) {
      if (f.dept_code) vistos.set(f.dept_code, f.dept_name || deptos[f.dept_code] || "");
    }
    return [...vistos.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [datos, deptos]);

  // Un departamento que ya no existe en el libro nuevo dejaría la tabla vacía
  // sin decir por qué: se vuelve a «todos» al cambiar de libro.
  useEffect(() => {
    if (dept && !opciones.some(([c]) => c === dept)) setDept("");
  }, [opciones, dept]);

  // ⚠️ `?? []` crea un arreglo nuevo en cada render y de él cuelgan la vista y
  // el cuadro: sin el memo se recalculan siempre.
  const versiones = useMemo(() => datos?.versiones ?? [], [datos]);

  /** Las filas del libro, ya filtradas y AGRUPADAS POR DEPARTAMENTO.
   *
   *  Owner, 2026-09-03: *«los checkbooks deben estar por departamentos, si no
   *  no se puede saber a qué corresponde; puede ser todos, pero internamente
   *  separados»*.
   *
   *  ⚠️ Una lista de cuentas sin su departamento no se puede leer: la 7065
   *  aparece cuatro veces —Habitaciones, Club, Mantenimiento…— y las cuatro se
   *  llaman «Cleaning Supplies». Sin el corte, son cuatro filas idénticas con
   *  montos distintos. */
  const grupos = useMemo(() => {
    const con = (datos?.filas ?? [])
      .filter(x => !dept || x.dept_code === dept)
      .map(x => ({
        ...x,
        total: versiones.reduce(
          (a, v) => a + (x.series[v.scenario_id] ?? []).reduce((s, n) => s + n, 0), 0),
      }))
      .filter(x => Math.abs(x.total) >= 0.005);

    const out = new Map<string, { nombre: string; filas: typeof con }>();
    for (const f of con) {
      const g = out.get(f.dept_code)
        || { nombre: f.dept_name || deptos[f.dept_code] || "", filas: [] };
      g.filas.push(f);
      out.set(f.dept_code, g);
    }
    return [...out.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([code, g]) => ({
        code, nombre: g.nombre,
        // Dentro del departamento, lo más grande primero: lo que explica el
        // número va arriba.
        filas: g.filas.sort((a, b) => Math.abs(b.total) - Math.abs(a.total)),
      }));
  }, [datos, versiones, dept, deptos]);

  const filas = useMemo(() => grupos.flatMap(g => g.filas), [grupos]);

  const rotuloLibro = LIBROS.find(l => l.clase === clase)?.rotulo ?? clase;

  /** El cuadro de los tres cortes. ⚠️ Es EL MISMO que baja al Excel — la
   *  pantalla lo dibuja, no lo vuelve a armar. */
  // El año va en el rótulo del corte, igual que en el archivo.
  const anioCb = useMemo(
    () => escenarios.find(e => e.id === versiones[0]?.scenario_id)?.year,
    [escenarios, versiones]);
  const cortes = useMemo(() => cortesDelCheckbook(mes, anioCb),
    [mes, anioCb]);
  /** Qué columnas se dibujan y quién ocupa cada una.
   *
   *  ⚠️ La MISMA que arma el cuadro. Antes la pantalla recortaba las versiones
   *  a las visibles por su cuenta para medir los anchos, y con el Forecast
   *  fuera de las ranuras medía un ancho y el cuadro traía otro: los
   *  encabezados de corte quedaban corridos respecto de los números. */
  const vistaCb = useMemo(
    () => vistaDe(versiones, visibles, actualDelFullYear, escenarios),
    [versiones, visibles, actualDelFullYear, escenarios]);
  const cuadro = useMemo(() => (
    vista === "cortes" && datos
      ? cuadroCheckbookCortes(rotuloLibro, datos, mes, escenarios, dept, deptos,
                              { visibles, actualDelFullYear })
      : null
  ), [vista, datos, rotuloLibro, mes, escenarios, dept, deptos,
      visibles, actualDelFullYear]);

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
          {opciones.map(([c, nombre]) => (
            <option key={c} value={c}>{c} · {nombre}</option>
          ))}
        </select>
        {cargando && (
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>cargando…</span>
        )}
        {error && <span style={{ fontSize: 12, color: "var(--negative)" }}>{error}</span>}
      </div>

      {versiones.some(v => (v.actuals_through ?? 0) > 0) && (
        <p style={{ fontSize: 11.5, marginBottom: 10, padding: "8px 12px",
                    borderRadius: 7, lineHeight: 1.6,
                    border: "1px solid var(--border)",
                    borderLeft: "4px solid var(--positive)",
                    color: "var(--text-secondary)", maxWidth: 900 }}>
          Este forecast está <b>compuesto por dos cosas</b>: hasta el corte los
          números son los <b>actuales cargados</b> —van marcados «real» en el
          encabezado del mes— y de ahí en adelante es lo <b>proyectado</b> en su
          checkbook. Son los mismos meses que usa el P&amp;L, así que esta tabla
          suma exactamente lo que dice el reporte.
        </p>
      )}

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

      {/* ══════════ Vista: mes · YTD · full year ══════════════════════════ */}
      {vista === "cortes" && cuadro && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11.5, color: "var(--text-secondary)",
                        marginBottom: 8, maxWidth: 900, lineHeight: 1.6 }}>
            {rotuloLibro}
            {dept && clase !== "property"
              ? ` · ${dept} · ${deptos[dept] ?? ""}` : " · todos los departamentos"}
            {" — "}
            <b>en el full year la varianza es Forecast contra Budget</b>: el
            Actual del año todavía no existe, son los meses cargados y nada más.
          </div>
          <div className="fin-scroll-x">
            <table style={{ borderCollapse: "collapse", minWidth: 900 }}>
              <thead>
                {/* La fila de cortes, arriba de las versiones: sin ella, nueve
                    columnas de montos no dicen cuál pertenece a qué período. */}
                <tr>
                  <th style={{ ...TDL, position: "static", minWidth: 250 }} />
                  {cortes.map((c, ci) => (
                    <th key={c.clave} colSpan={anchoDelCorte(c, versiones, escenarios, vistaCb)}
                        style={{ ...TD, position: "static", textAlign: "center",
                                 fontWeight: 800, color: "var(--brand)",
                                 borderLeft: ci ? BL : undefined }}>
                      {c.titulo}
                    </th>
                  ))}
                </tr>
                <tr>
                  {cuadro.columnas.map((col, i) => (
                    <th key={i} style={{
                      ...(i === 0 ? { ...TDL, textAlign: "left", minWidth: 250 }
                                  : { ...TD, minWidth: 96 }),
                      position: "static", fontWeight: 700,
                      fontStyle: col.label === ROTULO_VAR ? "italic" : undefined,
                      color: "var(--text-secondary)",
                      borderBottom: "2px solid var(--text-primary)",
                    }}>
                      {/* El corte ya está en la fila de arriba; acá va sólo la
                          versión, o «Var». */}
                      {/* El período ya está en la fila de arriba; acá va sólo
                          la versión. Ver `ColumnaCuadro.sub`. */}
                      {i === 0 ? "Cuenta" : col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cuadro.filas.map((f, i) => {
                  if (!f.valores.length) {
                    return <tr key={i}>
                      <td colSpan={cuadro.columnas.length} style={{ height: 9 }} />
                    </tr>;
                  }
                  const banda = f.es_total && f.nivel === 0 && f.label !== "TOTAL";
                  const fin = f.label === "TOTAL";
                  return (
                    <tr key={i} style={{
                      background: banda || fin
                        ? "var(--bg-elevated, #EDF1F5)" : undefined,
                    }}>
                      <td style={{ ...TDL, fontWeight: f.es_total ? 800 : 400,
                                   paddingLeft: 10 + (f.nivel ?? 0) * 14,
                                   borderTop: fin ? "2px solid var(--text-primary)"
                                     : banda ? "2px solid var(--border-medium)"
                                     : f.es_total ? "1px solid var(--border-medium)"
                                     : undefined }}>
                        {f.label}
                      </td>
                      {(f.valores as (number | null)[]).map((v, j) => {
                        const esVar = cuadro.columnas[j + 1]?.label === ROTULO_VAR;
                        const abre = cortes.some((c, ci) => ci > 0 && j === cortes
                          .slice(0, ci).reduce(
                            (a, x) => a + anchoDelCorte(x, versiones, escenarios,
                                                       vistaCb), 0));
                        return (
                          <td key={j} className="mono" style={{
                            ...TD, fontWeight: f.es_total ? 800 : 400,
                            fontStyle: esVar ? "italic" : undefined,
                            borderLeft: abre ? BL : undefined,
                            borderTop: fin ? "2px solid var(--text-primary)"
                              : banda ? "2px solid var(--border-medium)"
                              : f.es_total ? "1px solid var(--border-medium)"
                              : undefined,
                            color: typeof v === "number" && v < 0
                              ? "var(--negative)" : undefined,
                          }}>
                            {typeof v === "number" ? usd(v) : ""}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
                {cuadro.filas.length <= 1 && !cargando && (
                  <tr><td colSpan={cuadro.columnas.length}
                          style={{ ...TDL, color: "var(--text-secondary)" }}>
                    Este checkbook no tiene nada cargado para esa selección.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ══════════ Vista: los doce meses, una versión por tabla ══════════ */}
      {vista === "12m" && versiones.map(v => {
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
                    {/* ⚠️ Los meses que ya son ACTUALES van marcados.
                        Owner, 2026-09-03: «el Forecast 2026 está compuesto por
                        actuales y por forecast; cómo se está manejando esto en
                        esta vista».

                        Doce columnas iguales harían leer como presupuesto lo
                        que ya pasó — y en este checkbook conviven las dos
                        cosas. */}
                    {MESES.map((m, i) => {
                      const real = i < (v.actuals_through ?? 0);
                      return (
                        <th key={m} title={real ? "Actual cargado" : "Proyectado"}
                            style={{ ...TD, fontWeight: 700, minWidth: 82,
                                     position: "static",
                                     color: real ? "var(--positive)" : undefined,
                                     borderBottom: "2px solid var(--text-primary)" }}>
                          {m}
                          {real && (
                            <div style={{ fontSize: 9, fontWeight: 600,
                                          letterSpacing: .3 }}>real</div>
                          )}
                        </th>
                      );
                    })}
                    <th style={{ ...TD, fontWeight: 800, minWidth: 100,
                                 position: "static",
                                 borderLeft: "2px solid var(--border-medium)",
                                 borderBottom: "2px solid var(--text-primary)" }}>
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {grupos.flatMap(g => [
                    // La banda del departamento. Va siempre, incluso con uno
                    // solo elegido: el encabezado dice de qué se está mirando
                    // el checkbook, y sin él la tabla no se puede imprimir.
                    <tr key={`d-${g.code}`}>
                      <td colSpan={14} style={{
                        ...TDL, fontWeight: 800, fontSize: 12,
                        padding: "7px 10px",
                        background: "var(--bg-elevated, #EDF1F5)",
                        borderTop: "2px solid var(--border-medium)",
                      }}>
                        <span className="mono" style={{ color: "var(--text-secondary)" }}>
                          {g.code}
                        </span>{g.nombre ? ` · ${g.nombre}` : ""}
                      </td>
                    </tr>,
                    ...g.filas.map(f => {
                    const serie = f.series[v.scenario_id] ?? [];
                    return (
                      <tr key={`${g.code}-${f.cuenta}`}>
                        <td style={{ ...TDL, paddingLeft: 22 }}>
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
                    }),
                    // El subtotal del departamento: sin él, con seis
                    // departamentos abiertos no hay forma de saber cuánto pesa
                    // cada uno sin sumar a mano.
                    <tr key={`s-${g.code}`}>
                      <td style={{ ...TDL, paddingLeft: 22, fontWeight: 700,
                                   borderTop: "1px solid var(--border-medium)" }}>
                        Subtotal {g.code}
                      </td>
                      {MESES.map((_, i) => (
                        <td key={i} className="mono" style={{
                          ...TD, fontWeight: 700,
                          borderTop: "1px solid var(--border-medium)",
                        }}>
                          {usd(g.filas.reduce(
                            (a, f) => a + ((f.series[v.scenario_id] ?? [])[i] ?? 0), 0))}
                        </td>
                      ))}
                      <td className="mono" style={{
                        ...TD, fontWeight: 700,
                        borderTop: "1px solid var(--border-medium)",
                        borderLeft: "2px solid var(--border-medium)",
                      }}>
                        {usd(g.filas.reduce(
                          (a, f) => a + total(f.series[v.scenario_id]), 0))}
                      </td>
                    </tr>,
                  ])}
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
