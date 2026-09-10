"use client";
/**
 * Cierre de mes · Estadística de habitaciones desde el PDF del PMS.
 *
 * Owner, 2026-09-09: *«la idea es que se suba el documento y se lea la
 * información pero que no se guarde — solo se tomen los datos y ya»* · *«esto
 * debe quedar en cierre de mes»* · *«Amarena no tiene Opera»*.
 *
 * ## Subir no es guardar, y acá se ven separados
 *
 * El PDF se sube, se lee **en memoria** y se descarta: el endpoint
 * `/room-stats/leer-pdf/` no escribe una sola fila. Lo que queda en pantalla
 * es el mes armado, y recién el botón **Guardar** lo manda al mismo endpoint
 * que usa la carga manual (`saveRoomStatsEntry`). El archivo nunca se
 * almacena.
 *
 * ⚠️ **El paso del medio es el que evita el error caro.** El PDF trae los
 * nombres del PMS («BEACH FRONT DLXE VILLA») y la base guarda los de la
 * propiedad (Master Data · Tipos de habitación). Si esto guardara solo,
 * una categoría que no calza se archivaría bajo un rótulo que el reporte no
 * busca: las noches entrarían, el Room Stats seguiría en cero y **nada
 * avisaría**. Por eso el calce se propone, se marca con qué confianza, y no
 * se puede guardar hasta que las tres filas tengan categoría.
 *
 * ## Lo que la pantalla muestra y no guarda
 *
 * El resumen del PDF trae DOS cifras de habitaciones que no coinciden —el
 * inventario completo y lo que quedó después de las bloqueadas— y por lo
 * tanto dos porcentajes de ocupación. Se muestran los dos. Las noches
 * disponibles que se guardan son `unidades × días` de Master Data, igual que
 * en la carga manual: si el Room Stats cambiara de vara según cómo entró el
 * mes, dos meses del mismo año no se podrían comparar.
 */
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getRoomStatsEntry, getScenarios, leerPdfRoomStats, saveRoomStatsEntry,
  type PdfRoomStatsLectura, type Scenario,
} from "@/lib/api";
import { bajarCuadros, type Cuadro } from "@/lib/exportCuadro";
import { useEscenarioDe } from "@/lib/escenarioPreferido";
import { HOTEL_ID } from "@/lib/hotel";

const SEL: React.CSSProperties = {
  padding: "6px 10px", fontSize: 12.5, borderRadius: 6,
  border: "1px solid var(--border-medium)",
  background: "var(--bg-surface)", color: "var(--text-primary)",
};
const TH: React.CSSProperties = {
  textAlign: "right", padding: "7px 10px", fontSize: 11.5, fontWeight: 600,
  color: "var(--text-secondary)", borderBottom: "1px solid var(--border-medium)",
  whiteSpace: "nowrap",
};
const TD: React.CSSProperties = {
  textAlign: "right", padding: "6px 10px", fontSize: 12.5,
  fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap",
};

const num = (n: number, dec = 0) =>
  n.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const usd = (n: number) => `$${num(n, 2)}`;

/** Sin categoría elegida no hay dónde guardar la fila. */
const SIN_CALCE = "";

export default function CierreRoomStatsPdfPage() {
  const [escenarios, setEscenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useEscenarioDe(
    "month-end/room-stats", escenarios, "actual");

  const [lectura, setLectura] = useState<PdfRoomStatsLectura | null>(null);
  /** Categoría elegida por fila, indexada por el nombre que trae el PDF. */
  const [calce, setCalce] = useState<Record<string, string>>({});
  const [categorias, setCategorias] = useState<{ name: string; units: number }[]>([]);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [leyendo, setLeyendo] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const archivo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getScenarios(HOTEL_ID).then(setEscenarios)
      .catch(e => setError(e instanceof Error ? e.message : "No se pudieron cargar los escenarios"));
  }, []);

  /** El catálogo de categorías de la propiedad, para el selector de calce.
   *  Sale del MISMO endpoint que la carga manual, así el desplegable no puede
   *  ofrecer un rótulo que el guardado no acepte. */
  useEffect(() => {
    if (!scenarioId || !lectura) return;
    let vivo = true;
    getRoomStatsEntry(scenarioId, lectura.month)
      .then(r => { if (vivo) setCategorias(r.rows.map(x => ({ name: x.room_type_name, units: x.units }))); })
      .catch(() => { if (vivo) setCategorias([]); });
    return () => { vivo = false; };
  }, [scenarioId, lectura]);

  const leer = useCallback(async (f: File) => {
    if (!scenarioId) { setError("Elegí primero la versión donde va el mes."); return; }
    setLeyendo(true); setError(null); setOk(null); setLectura(null);
    try {
      const r = await leerPdfRoomStats(scenarioId, f);
      setLectura(r);
      setCalce(Object.fromEntries(r.filas.map(x => [x.nombre_pdf, x.room_type_name ?? SIN_CALCE])));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo leer el PDF");
    } finally {
      setLeyendo(false);
      if (archivo.current) archivo.current.value = "";   // el mismo archivo se puede volver a subir
    }
  }, [scenarioId]);

  /** Dos filas del PDF apuntando a la misma categoría se sumarían en silencio
   *  al guardar —el mes se reemplaza entero— y una de las dos desaparecería. */
  const duplicadas = useMemo(() => {
    const vistas = new Map<string, number>();
    Object.values(calce).forEach(v => { if (v) vistas.set(v, (vistas.get(v) ?? 0) + 1); });
    return [...vistas.entries()].filter(([, n]) => n > 1).map(([v]) => v);
  }, [calce]);

  const faltanCalce = useMemo(
    () => (lectura?.filas ?? []).filter(f => !calce[f.nombre_pdf]).length,
    [lectura, calce]);

  const puedeGuardar = !!lectura && !leyendo && !guardando
    && faltanCalce === 0 && duplicadas.length === 0;

  async function guardar() {
    if (!lectura || !scenarioId) return;
    setGuardando(true); setError(null); setOk(null);
    try {
      const rows = lectura.filas.map(f => ({
        room_type_name: calce[f.nombre_pdf],
        units: categorias.find(c => c.name === calce[f.nombre_pdf])?.units ?? f.units,
        nights_occupied: f.nights_occupied,
        revenue: f.revenue,
        pax: f.pax,
      }));
      const r = await saveRoomStatsEntry(scenarioId, lectura.month, rows);
      setOk(`Guardado: ${lectura.mes_nombre} ${lectura.year} · ${r.rows_saved} categoría(s). `
            + "El PDF no se almacenó.");
      setLectura(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  /** El mes leído a Excel, con el detalle por agencia adentro.
   *
   *  ⚠️ Baja lo LEÍDO, esté guardado o no — es la evidencia de qué decía el
   *  PDF, y como el PDF no se archiva, este es el único respaldo de la lectura
   *  que queda en el paquete del cierre. */
  async function bajarExcel() {
    if (!lectura) return;
    const filas = lectura.filas.flatMap(f => [
      {
        label: f.nombre_pdf, es_total: true,
        valores: [calce[f.nombre_pdf] || "— sin calce —",
                  f.nights_occupied, f.pax, f.revenue, f.adr],
      },
      ...f.agencias.map(a => ({
        label: a.agencia, nivel: 1,
        valores: ["", a.nights_occupied, a.pax, a.revenue, a.tarifa_promedio],
      })),
    ]);
    const cuadro: Cuadro = {
      titulo: `Estadística de habitaciones · ${lectura.mes_nombre} ${lectura.year}`,
      subtitulo: `${lectura.entidad} · ${lectura.moneda} · leído de ${lectura.archivo}`,
      hoja: `Room Stats ${lectura.mes_nombre}`.slice(0, 31),
      columnas: [
        { label: "Categoría / Agencia", ancho: 34, formato: "texto" },
        { label: "Va a (Master Data)", ancho: 30, formato: "texto" },
        { label: "Noches ocupadas", ancho: 16, formato: "num" },
        { label: "Pax", ancho: 12, formato: "num" },
        { label: "Ingreso", ancho: 16, formato: "usd2" },
        { label: "ADR", ancho: 14, formato: "usd2" },
      ],
      filas: [
        ...filas,
        { label: "TOTAL", es_total: true,
          valores: ["", lectura.totales.nights_occupied, lectura.totales.pax,
                    lectura.totales.revenue, lectura.totales.adr] },
      ],
      comentarios: [
        `Resumen del PDF: ${lectura.resumen_pdf.capacidad_hab} hab × `
        + `${lectura.resumen_pdf.dias} días = ${lectura.resumen_pdf.habitaciones_totales} `
        + `habitaciones-noche; ${lectura.resumen_pdf.habitaciones_disponibles} disponibles, `
        + `${lectura.resumen_pdf.habitaciones_bloqueadas} bloqueadas.`,
        `Ocupación ${lectura.resumen_pdf.ocupacion_sobre_total}% del total · `
        + `${lectura.resumen_pdf.ocupacion_sobre_disponibles}% de las disponibles.`,
        `Ingreso total del hotel ${usd(lectura.resumen_pdf.ingreso_total_hotel)}, `
        + `de los cuales ${usd(lectura.resumen_pdf.ingreso_otros)} son otros ingresos `
        + `que no entran a esta estadística.`,
        ...(lectura.avisos_de_cuadre.length
          ? ["NO CUADRA: " + lectura.avisos_de_cuadre.join(" · ")] : []),
      ],
    };
    try {
      await bajarCuadros(`RoomStats_PMS_${lectura.year}_${String(lectura.month).padStart(2, "0")}`,
                         [cuadro]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo generar el Excel");
    }
  }

  const t = lectura?.totales;
  const r = lectura?.resumen_pdf;

  return (
    <div className="pag pag-ancha" style={{ padding: "18px 22px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10,
                    flexWrap: "wrap", marginBottom: 4 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Estadística de habitaciones · PDF del PMS</h1>
        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)} style={SEL}>
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>{s.type} · {s.version} · {s.year}</option>
          ))}
        </select>
        <label style={{ ...SEL, cursor: leyendo ? "wait" : "pointer", fontWeight: 600,
                        background: "var(--brand)", color: "#fff", border: "none" }}>
          {leyendo ? "Leyendo…" : "Subir PDF"}
          <input ref={archivo} type="file" accept="application/pdf,.pdf" hidden
                 disabled={leyendo || !scenarioId}
                 onChange={e => { const f = e.target.files?.[0]; if (f) leer(f); }} />
        </label>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 14, maxWidth: 760 }}>
        Reporte «Estadística de Explotación Totalizada por Tipo de Habitación» del PMS,
        un archivo por mes. <strong>El documento no se guarda</strong>: se lee, se muestra
        acá y se descarta. Lo que se guarda —cuando apretás Guardar— son las noches, los
        pax y el ingreso del mes.
      </p>

      {error && <Aviso tono="error">{error}</Aviso>}
      {ok && <Aviso tono="ok">{ok}</Aviso>}

      {lectura && (
        <>
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "baseline",
                        marginBottom: 10, fontSize: 12.5 }}>
            <strong style={{ fontSize: 15 }}>{lectura.mes_nombre} {lectura.year}</strong>
            <span style={{ color: "var(--text-secondary)" }}>{lectura.entidad}</span>
            <span style={{ color: "var(--text-secondary)" }}>{lectura.moneda}</span>
            <span style={{ color: "var(--text-secondary)" }}>{lectura.archivo}</span>
          </div>

          {/* El cuadre es lo primero: si el detalle no da los totales del propio
              archivo, no hay nada que revisar más abajo. */}
          {lectura.avisos_de_cuadre.length > 0 && (
            <Aviso tono="error">
              <strong>El archivo y lo leído no cuadran.</strong> No guardes esto sin
              revisar el PDF:
              <ul style={{ margin: "6px 0 0 18px" }}>
                {lectura.avisos_de_cuadre.map(a => <li key={a}>{a}</li>)}
              </ul>
            </Aviso>
          )}
          {lectura.mes_ya_tiene_datos && (
            <Aviso tono="warn">
              {lectura.mes_nombre} ya tiene estadística cargada en esta versión.
              Guardar <strong>reemplaza el mes completo</strong> — la columna «Ya
              guardado» muestra qué se estaría pisando.
            </Aviso>
          )}
          {faltanCalce > 0 && (
            <Aviso tono="warn">
              {faltanCalce} categoría(s) del PDF sin equivalente en Master Data.
              Elegí a cuál va cada una: guardarlas con el nombre del PMS las dejaría
              fuera del reporte sin ningún aviso.
            </Aviso>
          )}
          {duplicadas.length > 0 && (
            <Aviso tono="error">
              Hay dos filas del PDF apuntando a la misma categoría
              ({duplicadas.join(", ")}). Al guardar, una pisaría a la otra.
            </Aviso>
          )}
          {lectura.categorias_ausentes_en_el_pdf.length > 0 && (
            <Aviso tono="info">
              El PDF no trae movimiento de: {lectura.categorias_ausentes_en_el_pdf.join(", ")}.
              Al guardar quedan en cero para este mes.
            </Aviso>
          )}

          <div className="fin-scroll-x"
               style={{ overflowX: "auto", border: "1px solid var(--border-medium)",
                        borderRadius: 8 }}>
            <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 900 }}>
              <thead>
                <tr style={{ background: "var(--bg-header)" }}>
                  <th style={{ ...TH, textAlign: "left" }}>Categoría en el PDF</th>
                  <th style={{ ...TH, textAlign: "left" }}>Va a (Master Data)</th>
                  <th style={TH}>Noches disp.</th>
                  <th style={TH}>Noches ocup.</th>
                  <th style={TH}>Pax</th>
                  <th style={TH}>Ingreso</th>
                  <th style={TH}>ADR</th>
                  <th style={TH}>Ya guardado</th>
                </tr>
              </thead>
              <tbody>
                {lectura.filas.map(f => {
                  const elegida = calce[f.nombre_pdf] ?? SIN_CALCE;
                  const units = categorias.find(c => c.name === elegida)?.units ?? f.units;
                  const disp = units * lectura.dias_del_mes;
                  const abierto = abierta === f.nombre_pdf;
                  return (
                    // La llave va en el Fragment: la fila y su detalle por
                    // agencia son un solo bloque, y con la llave en el <tr> de
                    // adentro React vuelve a montar el detalle en cada render.
                    <Fragment key={f.nombre_pdf}>
                      <tr style={{ borderTop: "1px solid var(--border-subtle)" }}>
                        <td style={{ ...TD, textAlign: "left" }}>
                          <button onClick={() => setAbierta(abierto ? null : f.nombre_pdf)}
                                  title="Ver el detalle por agencia"
                                  style={{ background: "none", border: "none", cursor: "pointer",
                                           color: "var(--text-primary)", font: "inherit",
                                           padding: 0 }}>
                            {abierto ? "▾" : "▸"} {f.nombre_pdf}
                          </button>
                        </td>
                        <td style={{ ...TD, textAlign: "left" }}>
                          <select value={elegida} style={{ ...SEL, padding: "4px 8px" }}
                                  onChange={e => setCalce(c => ({ ...c, [f.nombre_pdf]: e.target.value }))}>
                            <option value={SIN_CALCE}>— elegir —</option>
                            {categorias.map(c => (
                              <option key={c.name} value={c.name}>{c.name}</option>
                            ))}
                          </select>
                          <Confianza valor={f.confianza} />
                        </td>
                        <td style={{ ...TD, color: "var(--text-secondary)" }}>{num(disp)}</td>
                        <td style={TD}>{num(f.nights_occupied)}</td>
                        <td style={TD}>{num(f.pax)}</td>
                        <td style={TD}>{usd(f.revenue)}</td>
                        <td style={TD}>{usd(f.adr)}</td>
                        <td style={{ ...TD, color: "var(--text-secondary)", fontSize: 11.5 }}>
                          {f.actual_guardado
                            ? `${num(f.actual_guardado.nights_occupied)} n · ${usd(f.actual_guardado.revenue)}`
                            : "—"}
                        </td>
                      </tr>
                      {abierto && f.agencias.map(a => (
                        <tr key={`${f.nombre_pdf}-${a.agencia}`}
                            style={{ background: "var(--bg-surface)", fontSize: 11.5 }}>
                          <td style={{ ...TD, textAlign: "left", paddingLeft: 30,
                                       color: "var(--text-secondary)" }}>{a.agencia}</td>
                          <td style={TD}></td>
                          <td style={TD}></td>
                          <td style={{ ...TD, color: "var(--text-secondary)" }}>{num(a.nights_occupied)}</td>
                          <td style={{ ...TD, color: "var(--text-secondary)" }}>{num(a.pax)}</td>
                          <td style={{ ...TD, color: "var(--text-secondary)" }}>{usd(a.revenue)}</td>
                          <td style={{ ...TD, color: "var(--text-secondary)" }}>{usd(a.tarifa_promedio)}</td>
                          <td style={TD}></td>
                        </tr>
                      ))}
                    </Fragment>
                  );
                })}
                {t && (
                  <tr style={{ borderTop: "2px solid var(--border-medium)", fontWeight: 700,
                               background: "var(--bg-elevated)" }}>
                    <td style={{ ...TD, textAlign: "left" }}>TOTAL</td>
                    <td style={TD}></td>
                    <td style={TD}>{num(t.nights_available_config)}</td>
                    <td style={TD}>{num(t.nights_occupied)}</td>
                    <td style={TD}>{num(t.pax)}</td>
                    <td style={TD}>{usd(t.revenue)}</td>
                    <td style={TD}>{usd(t.adr)}</td>
                    <td style={TD}></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {r && (
            <div style={{ marginTop: 14, padding: "10px 14px", fontSize: 12,
                          border: "1px solid var(--border-subtle)", borderRadius: 8,
                          background: "var(--bg-surface)", maxWidth: 900 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>
                Resumen del PDF <span style={{ fontWeight: 400, color: "var(--text-secondary)" }}>
                  — referencia, no se guarda
                </span>
              </div>
              <div style={{ display: "flex", gap: 22, flexWrap: "wrap",
                            color: "var(--text-secondary)" }}>
                <span>Capacidad: <b>{r.capacidad_hab}</b> hab · {r.dias} días</span>
                <span>Habitaciones-noche: <b>{num(r.habitaciones_totales)}</b></span>
                <span>Disponibles: <b>{num(r.habitaciones_disponibles)}</b></span>
                <span>Bloqueadas: <b>{num(r.habitaciones_bloqueadas)}</b></span>
                <span>Ocupación: <b>{r.ocupacion_sobre_total}%</b> del total
                      · <b>{r.ocupacion_sobre_disponibles}%</b> de las disponibles</span>
                <span>Hospedaje: <b>{usd(r.ingreso_hospedaje)}</b></span>
                <span>Otros ingresos: <b>{usd(r.ingreso_otros)}</b></span>
                <span>Total hotel: <b>{usd(r.ingreso_total_hotel)}</b></span>
              </div>
              {/* Los «otros ingresos» del resumen NO son de habitaciones y por eso
                  no entran acá: entran al P&L por su propia cuenta, desde el GL. */}
              <div style={{ marginTop: 6, color: "var(--text-secondary)", fontSize: 11.5 }}>
                Se guardan solo las noches, los pax y el ingreso de hospedaje por
                categoría. Los otros ingresos del hotel llegan al P&amp;L desde el GL,
                no desde acá.
              </div>
            </div>
          )}

          <div style={{ marginTop: 14, display: "flex", gap: 10, alignItems: "center" }}>
            <button onClick={guardar} disabled={!puedeGuardar}
              style={{ ...SEL, cursor: puedeGuardar ? "pointer" : "not-allowed",
                       fontWeight: 600, border: "none", padding: "8px 16px",
                       background: puedeGuardar ? "var(--positive)" : "var(--bg-elevated)",
                       color: puedeGuardar ? "#fff" : "var(--text-disabled)" }}>
              {guardando ? "Guardando…" : `Guardar ${lectura.mes_nombre} ${lectura.year}`}
            </button>
            <button onClick={bajarExcel}
              title="El mes leído, con el detalle por agencia. El PDF no se archiva: este es el respaldo."
              style={{ ...SEL, cursor: "pointer", fontWeight: 600,
                       background: "var(--accent-excel)", color: "#fff", border: "none" }}>
              ⬇ Excel
            </button>
            <button onClick={() => { setLectura(null); setOk(null); setError(null); }}
                    style={{ ...SEL, cursor: "pointer" }}>Descartar</button>
          </div>
        </>
      )}
    </div>
  );
}

function Confianza({ valor }: { valor: "exacto" | "probable" | "ninguno" }) {
  if (valor === "exacto") return null;   // no hay nada que revisar
  const [texto, color] = valor === "probable"
    ? ["por parecido — revisá", "var(--warning)"]
    : ["sin calce", "var(--negative)"];
  return (
    <span style={{ marginLeft: 8, fontSize: 11, color }}>{texto}</span>
  );
}

function Aviso({ tono, children }: {
  tono: "error" | "warn" | "ok" | "info"; children: React.ReactNode;
}) {
  const color = { error: "var(--negative)", warn: "var(--warning)",
                  ok: "var(--positive)", info: "var(--text-secondary)" }[tono];
  return (
    <div style={{ margin: "0 0 10px", padding: "8px 12px", fontSize: 12.5,
                  borderRadius: 6, borderLeft: `3px solid ${color}`,
                  background: "var(--bg-surface)" }}>
      {children}
    </div>
  );
}
