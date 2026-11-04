"use client";
import ResumenEjecutivo from "@/components/ResumenEjecutivo";

/** La pantalla propia del resumen. El cuerpo vive en el componente porque la
 *  pantalla de Comentarios & Q&A monta el MISMO — dos puertas a un solo
 *  código, que es distinto de dos copias que se desincronizan. */
export default function ResumenAnualPage() {
  return (
    <div className="pag pag-ancha">
      <ResumenEjecutivo />
    </div>
  );
}
