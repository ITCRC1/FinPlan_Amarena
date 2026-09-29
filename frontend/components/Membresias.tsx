"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getMembresias, importarMembresias, saveMembresias,
  type MembresiasAnio,
} from "@/lib/api";
import {
  bajarElAnio, MembresiasAnioPie, MembresiasAnioTabla,
} from "@/components/MembresiasAnioTabla";

/**
 * Membresías del club — el cobro de la cuota de mantenimiento.
 *
 * Owner, 2026-09-29: *«que aca incluyas este tab llamado MEMBRESIAS de la
 * misma forma en que esta la imagen. que se pueda actualizar manualmente por
 * mes. o que se pueda bajar o subir con un excel»*.
 *
 * ## No sale del PMS
 *
 * Es un conteo que lleva la propiedad y que vivía en una diapositiva. Por eso
 * esta pestaña es la única del cierre donde se ESCRIBE a mano — las otras
 * cuatro pintan lo que trajo el archivo.
 *
 * ## ⚠️ El total no se edita: se suma
 *
 * Es la suma de los conceptos. Dejarlo editable abre la puerta a que el total
 * y sus partes digan cosas distintas, que es el modo de falla que no avisa.
 *
 * ## ⚠️ Un mes sin cargar no es un mes en cero
 *
 * Los meses que nadie escribió se muestran en blanco, no en 0. Con doce meses
 * a la vista, un cero dice «no hubo membresías» y el blanco dice «todavía no
 * lo contamos».
 */

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

const n = (v: number) => v.toLocaleString("es-CR", { maximumFractionDigits: 0 });

export default function Membresias({ scenarioId, mesSel, SEL }: {
  scenarioId: string;
  /** El mes elegido arriba en la pantalla: la edición es de ESE mes. */
  mesSel: number;
  /** El estilo de control de la pantalla, para no inventar otro. */
  SEL: React.CSSProperties;
}) {
  const [anio, setAnio] = useState<MembresiasAnio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  /** Lo que se está editando del mes elegido: concepto → texto del input. */
  const [borrador, setBorrador] = useState<Record<string, string> | null>(null);
  const archivo = useRef<HTMLInputElement>(null);

  const cargar = useCallback(() => {
    if (!scenarioId) { setAnio(null); return; }
    getMembresias(scenarioId).then(setAnio)
      .catch(e => setError(e instanceof Error ? e.message : "No se pudo cargar"));
  }, [scenarioId]);

  useEffect(() => { cargar(); }, [cargar]);
  // Cambiar de mes descarta lo que se estuviera escribiendo: dejarlo vivo
  // haría que el borrador de agosto se guarde sobre septiembre.
  useEffect(() => { setBorrador(null); setOk(null); }, [mesSel]);

  const mes = anio?.meses[mesSel - 1] ?? null;

  /** El valor que va en el input: lo escrito si hay borrador, si no lo
   *  guardado. Un mes sin cargar arranca vacío, no en 0. */
  const valorDe = (concepto: string, cantidad: number) => {
    if (borrador && concepto in borrador) return borrador[concepto];
    if (!mes?.cargado) return "";
    return cantidad ? String(cantidad) : "";
  };

  const totalEditado = useMemo(() => {
    if (!mes) return 0;
    return mes.conceptos.reduce((a, c) => {
      const v = valorDe(c.concepto, c.cantidad);
      const x = parseFloat(v.replace(",", "."));
      return a + (Number.isFinite(x) ? x : 0);
    }, 0);
  }, [mes, borrador]);   // eslint-disable-line react-hooks/exhaustive-deps

  const hayCambios = borrador !== null && Object.keys(borrador).length > 0;

  async function guardar() {
    if (!mes || !scenarioId) return;
    setGuardando(true); setError(null); setOk(null);
    try {
      const conceptos = mes.conceptos.map(c => {
        const v = valorDe(c.concepto, c.cantidad);
        const x = parseFloat(v.replace(",", "."));
        return { concepto: c.concepto, cantidad: Number.isFinite(x) ? x : 0 };
      });
      const r = await saveMembresias(scenarioId, mes.month, conceptos);
      setOk(`Guardado: ${mes.mes_nombre} · ${r.conceptos_saved} concepto(s), `
            + `total ${n(totalEditado)}.`);
      setBorrador(null);
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally { setGuardando(false); }
  }

  async function subir(f: File) {
    if (!scenarioId) return;
    setSubiendo(true); setError(null); setOk(null);
    try {
      const r = await importarMembresias(scenarioId, f);
      setOk(`Importado: ${r.meses_nombre.join(", ")}. `
            + "Los meses que el archivo no traía quedaron como estaban.");
      setBorrador(null);
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo leer el archivo");
    } finally {
      setSubiendo(false);
      if (archivo.current) archivo.current.value = "";
    }
  }

  /** ⚠️ La definición del archivo vive en `MembresiasAnioTabla`, no acá: el
   *  Excel que baja del cierre y el que baja del Dashboard tienen que ser el
   *  mismo papel, y dos copias se separan en el primer arreglo. */
  async function bajar() {
    if (!anio) return;
    try { await bajarElAnio(anio); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudo generar el Excel"); }
  }

  if (!scenarioId) return null;
  if (!anio) {
    return <p style={{ padding: "26px 16px", margin: 0, fontSize: 12.5,
                       color: "var(--text-secondary)" }}>Cargando membresías…</p>;
  }

  return (
    <div style={{ padding: "10px 14px 16px" }}>
      {error && <Aviso tono="err">{error}</Aviso>}
      {ok && <Aviso tono="ok">{ok}</Aviso>}

      <div style={{ display: "flex", gap: 22, alignItems: "flex-start",
                    flexWrap: "wrap", padding: "8px 2px 0" }}>

        {/* ── El mes elegido, editable ───────────────────────────────── */}
        <div style={{ flex: "0 0 420px", minWidth: 340 }}>
          <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 2 }}>
            Ingresos cobro por cuota de mantenimiento
          </div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 8 }}>
            {MESES[mesSel - 1]} {anio.year}
            {mes?.cargado ? "" : " · todavía sin contar"}
          </div>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12.5 }}>
            <tbody>
              {mes?.conceptos.map(c => (
                <tr key={c.concepto}>
                  <td style={{ padding: "6px 8px", borderBottom: "1px solid var(--border-subtle)",
                               color: c.desconocido ? "var(--warning)" : undefined }}>
                    {c.rotulo}
                    {c.desconocido && (
                      <span style={{ fontSize: 10, marginLeft: 5 }}>· no reconocido</span>
                    )}
                  </td>
                  <td style={{ padding: "4px 8px", borderBottom: "1px solid var(--border-subtle)",
                               width: 110, textAlign: "right" }}>
                    <input inputMode="numeric" value={valorDe(c.concepto, c.cantidad)}
                      onChange={e => setBorrador(b => ({ ...(b ?? {}),
                                                         [c.concepto]: e.target.value }))}
                      aria-label={c.rotulo}
                      style={{ ...SEL, width: "100%", textAlign: "right",
                               padding: "4px 7px", fontSize: 12.5 }} />
                  </td>
                </tr>
              ))}
              {/* ⚠️ El total NO es un input: es la suma. */}
              <tr>
                <td style={{ padding: "7px 8px", fontWeight: 700,
                             borderTop: "2px solid var(--border-medium)" }}>
                  Total general
                </td>
                <td className="mono" style={{ padding: "7px 8px", fontWeight: 700,
                                              textAlign: "right",
                                              borderTop: "2px solid var(--border-medium)" }}>
                  {n(totalEditado)}
                </td>
              </tr>
            </tbody>
          </table>

          <div style={{ display: "flex", gap: 8, marginTop: 11, flexWrap: "wrap" }}>
            <button onClick={guardar} disabled={guardando || !hayCambios}
              style={{ ...SEL, padding: "7px 15px", fontWeight: 600,
                       cursor: hayCambios ? "pointer" : "not-allowed", border: "none",
                       background: hayCambios ? "var(--positive)" : "var(--bg-elevated)",
                       color: hayCambios ? "#fff" : "var(--text-disabled)" }}>
              {guardando ? "Guardando…" : `Guardar ${MESES[mesSel - 1]}`}
            </button>
            {hayCambios && (
              <button onClick={() => { setBorrador(null); setOk(null); }}
                style={{ ...SEL, cursor: "pointer" }}>Descartar cambios</button>
            )}
          </div>
          <p style={{ fontSize: 11, color: "var(--text-secondary)",
                      margin: "9px 0 0", lineHeight: 1.45 }}>
            El mes que se edita es el de arriba. Guardar <b>reemplaza</b> el mes
            entero; dejarlo todo en blanco lo vacía.
          </p>
        </div>

        {/* ── El año, para ver de dónde viene ───────────────────────── */}
        <div style={{ flex: "1 1 460px", minWidth: 340 }}>
          <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 2 }}>
            El año
          </div>
          <div style={{ marginBottom: 8 }}><MembresiasAnioPie anio={anio} /></div>
          <MembresiasAnioTabla anio={anio} mesSel={mesSel} />
          <div style={{ display: "flex", gap: 8, marginTop: 11, flexWrap: "wrap",
                        alignItems: "center" }}>
            <button onClick={bajar}
              style={{ ...SEL, cursor: "pointer", fontWeight: 600, border: "none",
                       background: "var(--accent-excel)", color: "#fff" }}>
              ⬇ Excel del año
            </button>
            <label style={{ ...SEL, cursor: subiendo ? "wait" : "pointer",
                            fontWeight: 600 }}>
              {subiendo ? "Leyendo…" : "⬆ Subir Excel"}
              <input ref={archivo} type="file" hidden accept=".xlsx,.xlsm,.xls,.csv"
                     disabled={subiendo}
                     onChange={e => { const f = e.target.files?.[0]; if (f) subir(f); }} />
            </label>
            <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
              Se sube el mismo archivo que baja. Los meses que no traiga quedan
              como están.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Aviso({ tono, children }: {
  tono: "err" | "ok"; children: React.ReactNode;
}) {
  const color = tono === "err" ? "var(--negative)" : "var(--positive)";
  return (
    <div style={{ margin: "8px 0", padding: "8px 13px", fontSize: 12.5,
                  lineHeight: 1.5, borderRadius: 5,
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  borderLeft: `3px solid ${color}` }}>
      {children}
    </div>
  );
}
