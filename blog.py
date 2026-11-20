"""
El blog (papinianord.com/blog): guías para traer visitas desde Google.

Cada artículo es un archivo Markdown en la carpeta blog/, con sus datos arriba entre líneas de tres guiones:

    ---
    titulo: "Prestaciones laborales en República Dominicana: cómo se calculan"
    titulo_seo: "Prestaciones laborales en RD: cómo se calculan"   # opcional: el que ve Google (menos de 60)
    descripcion: "Lo que sale debajo del título en Google (menos de 160 caracteres)."
    fecha: 2026-11-20
    actualizado: 2026-11-20
    publicado: false     # borrador hasta que un abogado lo revise
    revisado: ""         # quién lo revisó, cuando se publique
    ---

El nombre del archivo es la dirección: prestaciones-laborales-republica-dominicana.md →
/blog/prestaciones-laborales-republica-dominicana.

Un borrador (publicado: false) no sale en la lista del blog ni en el sitemap, y su página lleva «noindex»: se abre
con su dirección para que un abogado lo lea antes de publicarlo. El servidor manda el artículo completo en el HTML
(para Google y los asistentes de IA que no corren JavaScript) y la app lo muestra con /api/blog/<dirección>.
"""
import pathlib
import re

import yaml
from markdown_it import MarkdownIt

CARPETA = pathlib.Path(__file__).parent / "blog"
_DIRECCION = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_md = MarkdownIt("commonmark").enable("table")
_cache: dict = {}   # archivo → (fecha de modificación, artículo)


def _leer(archivo: pathlib.Path) -> dict:
    marca = archivo.stat().st_mtime
    if archivo in _cache and _cache[archivo][0] == marca:
        return _cache[archivo][1]
    texto = archivo.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    if not m:
        raise ValueError(f"{archivo.name}: falta el encabezado entre ---")
    datos = yaml.safe_load(m.group(1)) or {}
    titulo = str(datos["titulo"])
    articulo = {
        "slug": archivo.stem,
        "titulo": titulo,
        "titulo_seo": str(datos.get("titulo_seo") or titulo),
        "descripcion": str(datos["descripcion"]),
        "fecha": str(datos["fecha"]),
        "actualizado": str(datos.get("actualizado") or datos["fecha"]),
        "publicado": bool(datos.get("publicado")),
        "revisado": str(datos.get("revisado") or ""),
        # cada tabla dentro de .tabla (index.css): en el celular se desliza de lado en vez de ensanchar la página
        "html": _md.render(m.group(2)).replace("<table>", '<div class="tabla"><table>').replace("</table>", "</table></div>"),
    }
    _cache[archivo] = (marca, articulo)
    return articulo


def articulos(incluir_borradores: bool = False) -> list:
    """Los artículos publicados (o también los borradores), del más nuevo al más viejo."""
    if not CARPETA.is_dir():
        return []
    lista = [_leer(a) for a in CARPETA.glob("*.md")]
    return sorted((a for a in lista if incluir_borradores or a["publicado"]), key=lambda a: a["fecha"], reverse=True)


def articulo(slug: str) -> dict | None:
    """Un artículo por su dirección (también un borrador), o None si no existe."""
    if not _DIRECCION.fullmatch(slug or ""):
        return None
    archivo = CARPETA / f"{slug}.md"
    return _leer(archivo) if archivo.is_file() else None
