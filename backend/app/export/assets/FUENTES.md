# Las fuentes que van en las imágenes de los cuadros

**Tinos** — Steve Matteson, licencia **Apache 2.0**.
<https://fonts.google.com/specimen/Tinos>

## Por qué ésta y no otra

Es **métricamente compatible con Times New Roman**, que es la del cuerpo del
informe (owner, 2026-09-30: *«el reporte debe ser en Times New Roman, letra
12»*). Un cuadro dibujado con otra serif se nota al lado del párrafo que lo
presenta: el ojo lo lee como pegado de otro documento.

## ⚠️ Por qué viaja en el repo

Las imágenes se dibujan con Pillow **en el servidor**, y el contenedor de
Railway no trae ninguna fuente: `/usr/share/fonts` está vacío y no hay
`fontconfig`. Sin el archivo acá, Pillow cae a su tipografía de mapa de bits y
el cuadro sale como una captura de pantalla de 1998.

Times New Roman **no** se puede redistribuir —es de Monotype—; Tinos sí, y da
el mismo ancho de línea.
