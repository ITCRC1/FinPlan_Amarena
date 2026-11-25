# -*- coding: utf-8 -*-
"""Porta los sub-tabs de «Mis libros» de Amarena a otra propiedad.

Owner, 2026-11-25: «las tres de una vez».

Los cuatro archivos del port (modelo, API, pruebas y pantalla) son IDÉNTICOS
entre las cuatro propiedades —se comprobó archivo por archivo, solo cambia el
fin de línea—, así que se copian tal cual. Lo que NO se copia es:

* la **migración**, que lleva el número que siga en cada repo y apunta a la
  cabeza de ESE repo (la 159 de Amarena no sirve en CWL, que va por la 167);
* el **cliente del frontend** y el **catálogo de errores**, que son archivos
  gigantes compartidos: ahí se aplica el mismo parche puntual.

No commitea ni empuja nada: deja el árbol listo para revisar.
"""
import pathlib
import re
import sys

AMARENA = pathlib.Path(r"C:\Users\User\Documents\FinPlan_Amarena")

#: Los que viajan tal cual.
COPIAR = [
    "backend/app/models/libro_colgado.py",
    "backend/app/api/libros_colgados_api.py",
    "backend/tests/test_mis_libros.py",
    "frontend/app/libros/page.tsx",
]

ERROR_NUEVO = '''    "libro.carpeta_invalida": {
        "es": "Esa carpeta no existe. Son: {carpetas}",
        "en": "No such folder. They are: {carpetas}"},
'''
ERROR_ANCLA = '''    "libro.muy_grande": {'''

MIGRACION = '''"""Mis libros: la carpeta (el sub-tab) de cada libro.

Owner, 2026-11-25: «podemos crear sub tabs acá… para subir archivos mensuales
para Cierre, Budget o Forecast y otros, ya si no se mezclan» y «es un mismo
repositorio solo que organizado por estos sub tabs». Port de Amarena (159).

Los libros que ya estaban caen en OTROS, salvo el Budget Package, que nace donde
corresponde. La carpeta NO entra en la llave única: el repositorio sigue siendo
uno y el título sigue mandando.

Revision ID: {rev}
Revises: {abajo}
"""
import sqlalchemy as sa
from alembic import op

revision = "{rev}"
down_revision = "{abajo}"
branch_labels = None
depends_on = None

TITULO_BUDGET_PACKAGE = "Budget Package (todo en un libro)"


def upgrade():
    # server_default se queda puesto: si una versión vieja del backend inserta
    # sin la columna, la fila cae en OTROS en vez de reventar.
    op.add_column("libros_colgados",
                  sa.Column("carpeta", sa.String(16), nullable=False,
                            server_default="OTROS"))
    op.execute(sa.text(
        "UPDATE libros_colgados SET carpeta = 'BUDGET' WHERE titulo = :t"
    ).bindparams(t=TITULO_BUDGET_PACKAGE))


def downgrade():
    op.drop_column("libros_colgados", "carpeta")
'''


def cabeza(repo: pathlib.Path) -> str:
    """El `revision` que nadie usa como `down_revision`: la punta de la cadena.

    Mirar el número más alto del nombre del archivo no alcanza — un repo puede
    tener la 160 colgando de la 158 — así que se arma la cadena de verdad.
    """
    carpeta = repo / "backend/alembic/versions"
    revs, abajo = set(), set()
    for f in carpeta.glob("*.py"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        # Las viejas llevan anotación de tipo: `revision: str = "014"` y
        # `down_revision: Union[str, None] = "013"`. Sin contemplarla, sus
        # padres parecen puntas sueltas y la cadena aparenta estar partida.
        m = re.search(r'^revision(?:\s*:[^=]+)?\s*=\s*["\']([^"\']+)', txt, re.M)
        d = re.search(r'^down_revision(?:\s*:[^=]+)?\s*=\s*["\']([^"\']+)', txt, re.M)
        if m:
            revs.add(m.group(1))
        if d:
            abajo.add(d.group(1))
    puntas = revs - abajo
    if len(puntas) != 1:
        raise SystemExit(f"{repo.name}: la cadena de migraciones tiene "
                         f"{len(puntas)} puntas ({sorted(puntas)}). A mano.")
    return puntas.pop()


def parchar_cliente(p: pathlib.Path) -> bool:
    t = p.read_text(encoding="utf-8")
    if "CarpetaLibro" in t:
        return False
    nuevo = AMARENA / "frontend/lib/api.ts"
    fuente = nuevo.read_text(encoding="utf-8")
    # Los tres trozos del port, tomados del archivo de Amarena para no
    # reescribirlos a mano y que se desincronicen.
    ini = fuente.index("// Las carpetas son los sub-tabs")
    fin = fuente.index("export const TITULO_BUDGET_PACKAGE")
    bloque = fuente[ini:fin]
    # OJO: `bloque` ya trae la interfaz ENTERA, cierre incluido, así que hay que
    # reemplazar la interfaz entera del destino. Reemplazar solo su primera
    # línea deja las de `nota`/`anterior` colgando y el archivo no compila.
    vieja = re.search(r"export interface Libro \{.*?\n\}\n", t, re.S)
    if vieja is None:
        raise SystemExit("   ⚠ no encontré `export interface Libro`. A mano.")
    t = t[:vieja.start()] + bloque.rstrip() + "\n" + t[vieja.end():]
    ini = fuente.index("export async function getCarpetasDeLibros")
    fin = fuente.index("export async function volverLibroAAnterior")
    t = re.sub(r"export async function subirLibro\(titulo: string, file: File,"
               r" nota = \"\"\): Promise<Libro> \{.*?\n\}\n",
               fuente[ini:fin], t, count=1, flags=re.S)
    p.write_text(t, encoding="utf-8")
    return True


def main(destino: str) -> int:
    repo = pathlib.Path(destino)
    if not (repo / "backend/app/models/libro_colgado.py").exists():
        raise SystemExit(f"{repo} no tiene «Mis libros»: hay que portar eso primero.")
    print(f"── {repo.name}")

    for rel in COPIAR:
        (repo / rel).write_bytes((AMARENA / rel).read_bytes())
        print(f"   copiado  {rel}")

    err = repo / "backend/app/errores.py"
    t = err.read_text(encoding="utf-8")
    if "libro.carpeta_invalida" in t:
        print("   errores  ya tenía la clave")
    elif ERROR_ANCLA in t:
        # Después de `muy_grande`, que es la última de los libros.
        corte = t.index(ERROR_ANCLA)
        fin = t.index("},", t.index("\n", corte)) + 3
        err.write_text(t[:fin] + ERROR_NUEVO + t[fin:], encoding="utf-8")
        print("   errores  clave libro.carpeta_invalida agregada")
    else:
        print("   ⚠ errores: no encontré dónde meter la clave. A mano.")

    api = repo / "frontend/lib/api.ts"
    print("   cliente  " + ("parchado" if parchar_cliente(api) else "ya estaba"))

    abajo = cabeza(repo)
    rev = str(int(abajo) + 1) if abajo.isdigit() else None
    if rev is None:
        raise SystemExit(f"   ⚠ la cabeza es «{abajo}», no es un número. A mano.")
    destino_mig = repo / f"backend/alembic/versions/{rev}_carpeta_de_libros.py"
    destino_mig.write_text(MIGRACION.format(rev=rev, abajo=abajo), encoding="utf-8")
    print(f"   migración {rev} (sobre la {abajo})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
