"use client";
/**
 * Qué sub-tabs de Cierre de Mes se ven, y para quién.
 *
 * Owner, 2026-09-02: *«esta vista la van a ver los dueños; me gustaría tener la
 * opción de poder esconder y visualizar a mi manera, poder quitar y poner tabs
 * sin borrarlas, sólo para dejar lo importante para el dueño»*.
 *
 * ## Las tres reglas, iguales a las de la barra
 *
 * Es la MISMA matriz (`tab_enablement`) con un tercer nivel, `SUBTAB`, así que
 * hereda las reglas que ya estaban probadas:
 *
 * * **La tabla es esparsa y el default es PRENDIDO.** No tener fila significa
 *   visible: el día que esto se despliega no cambia nada, y un sub-tab nuevo
 *   nace visible. Al revés —nacer oculto— sería peor: se construye algo, nadie
 *   lo ve, y nadie sabe que existe para poder prenderlo.
 * * **Prender BORRA la fila**, así la tabla contiene sólo lo que alguien apagó.
 * * **Se puede apagar TODO sin quedarse afuera.** El botón que abre este panel
 *   no es un sub-tab: sigue ahí aunque no quede ninguno.
 *
 * ## Esconde, no es un permiso
 *
 * ⚠️ La ruta sigue respondiendo y el dato sigue viajando: quien conozca la URL
 * entra igual. Para *impedir* está el perfil `viewer` (`app/perfiles.py`), que
 * hace que el servidor rechace toda escritura. Las dos capas se complementan:
 * ésta ordena la vista, aquélla impide el cambio.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { HOTEL_ID } from "@/lib/hotel";
import {
  getTabsApagados, saveTabsApagados, PERFILES, ROTULO_PERFIL,
  type Perfil, type TabsApagados,
} from "@/lib/tabsVisibles";

export default function VistasVisibles({ vistas, rotulo, apagados, onCambio, onCerrar }: {
  /** Las claves de todos los sub-tabs, en el orden de la pantalla. */
  vistas: readonly string[];
  rotulo: (k: string) => string;
  /** Lo que está apagado HOY para quien está mirando. */
  apagados: string[];
  onCambio: (nuevos: string[]) => void;
  onCerrar: () => void;
}) {
  /** Para QUIÉN se configura. `""` = para toda la propiedad.
   *
   *  Arranca en la propiedad porque es la decisión que manda: lo que se apaga
   *  ahí no lo ve nadie, y afinar por perfil sólo tiene sentido después. */
  const [perfil, setPerfil] = useState<Perfil>("");
  const [estado, setEstado] = useState<TabsApagados | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      // ⚠️ `perfil` va SIEMPRE, incluso vacío: sin él el backend contestaría
      // por el rol de quien abrió el panel, y estaríamos editando la vista del
      // admin creyendo que editamos la de la propiedad.
      setEstado(await getTabsApagados(HOTEL_ID, perfil));
    } catch (e) {
      setError(e instanceof Error ? e.message : "no se pudo cargar");
    }
  }, [perfil]);

  useEffect(() => { cargar(); }, [cargar]);

  const fuera = useMemo(() => new Set(estado?.SUBTAB ?? []), [estado]);

  async function alternar(clave: string) {
    setGuardando(true); setError(null);
    try {
      const r = await saveTabsApagados(HOTEL_ID,
        [{ scope_kind: "SUBTAB", clave, visible: fuera.has(clave) }], perfil);
      setEstado(r.estado);
      // La pantalla se entera sola sólo cuando se tocó SU vista: si se está
      // configurando el perfil de otro, la barra de acá no cambia — y avisar lo
      // contrario sería mentir, porque al recargar vuelve.
      if (!perfil) onCambio(r.estado.SUBTAB);
    } catch (e) {
      setError(e instanceof Error ? e.message : "no se pudo guardar");
    } finally { setGuardando(false); }
  }

  async function todas(visible: boolean) {
    setGuardando(true); setError(null);
    try {
      const r = await saveTabsApagados(HOTEL_ID,
        vistas.map(k => ({ scope_kind: "SUBTAB" as const, clave: k, visible })),
        perfil);
      setEstado(r.estado);
      if (!perfil) onCambio(r.estado.SUBTAB);
    } catch (e) {
      setError(e instanceof Error ? e.message : "no se pudo guardar");
    } finally { setGuardando(false); }
  }

  const btn: React.CSSProperties = {
    padding: "4px 10px", fontSize: 11.5, borderRadius: 5, cursor: "pointer",
    border: "1px solid var(--border-medium)", background: "var(--bg-surface)",
    color: "var(--text-secondary)",
  };

  return (
    <div style={{
      padding: "12px 16px", marginBottom: 14, borderRadius: 9,
      border: "1px solid var(--border)",
      borderLeft: "4px solid var(--brand)",
      background: "var(--bg-surface)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center", gap: 12, marginBottom: 10 }}>
        <b style={{ fontSize: 13 }}>Qué sub-tabs se ven</b>
        <button onClick={onCerrar} style={btn}>Cerrar</button>
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap",
                    alignItems: "center", marginBottom: 10 }}>
        <span style={{ fontSize: 11.5, color: "var(--text-secondary)",
                       fontWeight: 700 }}>Para:</span>
        {PERFILES.map(pf => (
          <button key={pf || "todos"} onClick={() => setPerfil(pf)} disabled={guardando}
            style={{ ...btn, fontWeight: perfil === pf ? 700 : 500,
                     background: perfil === pf ? "var(--brand)" : "var(--bg-surface)",
                     color: perfil === pf ? "#fff" : "var(--text-secondary)" }}>
            {ROTULO_PERFIL[pf]}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        <button onClick={() => todas(true)} disabled={guardando} style={btn}>
          Mostrar todas
        </button>
        <button onClick={() => todas(false)} disabled={guardando} style={btn}>
          Esconder todas
        </button>
      </div>

      {perfil && (
        <p style={{ fontSize: 11.5, color: "var(--text-secondary)",
                    lineHeight: 1.55, margin: "0 0 10px", maxWidth: 780 }}>
          Estás viendo <b>sólo lo apagado para {ROTULO_PERFIL[perfil]}</b>. Lo
          que apagaste en <b>Toda la propiedad</b> también le aplica y no aparece
          marcado acá: se suman, no se reemplazan.
        </p>
      )}

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {vistas.map(k => {
          const visible = !fuera.has(k);
          return (
            <button key={k} onClick={() => alternar(k)} disabled={guardando}
              title={visible ? "Se ve — click para esconder"
                             : "Escondido — click para mostrar"}
              style={{ ...btn, fontWeight: 600,
                       opacity: visible ? 1 : 0.5,
                       background: visible ? "var(--bg-elevated)" : "transparent",
                       color: visible ? "var(--text-primary)" : "var(--text-disabled)",
                       textDecoration: visible ? "none" : "line-through" }}>
              {visible ? "☑" : "☐"} {rotulo(k)}
            </button>
          );
        })}
      </div>

      {error && <p style={{ fontSize: 11.5, color: "var(--negative)",
                            marginBottom: 0 }}>{error}</p>}

      <p style={{ fontSize: 11, color: "var(--text-secondary)",
                  lineHeight: 1.55, margin: "10px 0 0", maxWidth: 800 }}>
        <b>Esconde, no borra.</b> El dato sigue ahí y el sub-tab vuelve con un
        click. No es un permiso: quien conozca la URL entra igual — para impedir
        cambios está el perfil <b>Sólo lectura</b>, que se asigna en Usuarios.
      </p>
    </div>
  );
}
