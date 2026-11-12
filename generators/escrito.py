"""
El escrito que Papiniano redacta al lado de la conversación, en Word y en PDF.

El escrito es texto simple: párrafos separados por una línea en blanco. El formato sale de estas
reglas, las mismas con que la app dibuja la hoja (web/src/lib/escrito.ts):
  - el primer párrafo es el título: centrado y en negrita;
  - una línea sola en mayúsculas (POR TALES MOTIVOS, Y HARÉIS JUSTICIA) también, salvo si termina en «:»;
  - los últimos dos párrafos con líneas cortas son la firma: centrados;
  - un párrafo de varias líneas cortas (AL:, ASUNTO:) va a la izquierda, línea por línea;
  - lo demás va justificado, y las palabras en mayúsculas que lo abren (ATENDIDO:, PRIMERO:) en negrita;
  - lo que está entre corchetes y en mayúsculas ([NOMBRE DEL SOLICITANTE]) es un dato por llenar: en amarillo.
"""

import re

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from fpdf import FPDF

from .base import a_bytes, doc_base, run

ESPACIO = re.compile(r"\[([^\[\]\n]{2,80})\]")
CLAVE = re.compile(r"^((?:[A-ZÁÉÍÓÚÜÑ]{2,} ?)+[:,])")


def es_espacio(dentro: str) -> bool:
    """[NOMBRE DEL SOLICITANTE] es un dato por llenar; [2] o [ver nota] no."""
    return bool(re.search(r"[A-ZÁÉÍÓÚÜÑ]", dentro)) and not re.search(r"[a-záéíóúüñ]", dentro)


def _mayusculas(linea: str) -> bool:
    return bool(re.search(r"[A-ZÁÉÍÓÚÜÑ]", linea)) and not re.search(r"[a-záéíóúüñ]", linea)


def parrafos(texto: str) -> list:
    """[(tipo, [líneas])]: tipo es titulo, centro, firma, lineas o normal."""
    bloques = [b for b in re.split(r"\n[ \t]*\n", texto.strip()) if b.strip()]
    salida = []
    for i, b in enumerate(bloques):
        lineas = [l.strip() for l in b.split("\n") if l.strip()]
        if i == 0:
            tipo = "titulo"
        elif len(lineas) == 1 and _mayusculas(lineas[0]) and len(lineas[0]) <= 100 and not lineas[0].endswith(":"):
            tipo = "centro"
        elif i >= len(bloques) - 2 and all(len(l) <= 60 for l in lineas):
            tipo = "firma"
        elif len(lineas) > 1 and all(len(l) <= 80 for l in lineas):
            tipo = "lineas"
        else:
            tipo = "normal"
        salida.append((tipo, lineas))
    return salida


def piezas(linea: str, negrita: bool = False) -> list:
    """[(texto, negrita, es un dato por llenar)] de una línea."""
    salida = []
    m = None if negrita else CLAVE.match(linea)
    if m:
        salida.append((m.group(1), True, False))
        linea = linea[m.end():]
    pos = 0
    for e in ESPACIO.finditer(linea):
        if es_espacio(e.group(1)):
            salida += [(linea[pos:e.start()], negrita, False), (e.group(0), negrita, True)]
            pos = e.end()
    salida.append((linea[pos:], negrita, False))
    return [s for s in salida if s[0]]


def nombre(texto: str, formato: str) -> str:
    """El nombre del archivo sale del título: «Instancia en solicitud de deslinde.docx»."""
    p = parrafos(texto)
    titulo = " ".join(p[0][1]) if p else ""
    titulo = re.sub(r"\s+", " ", re.sub(r'[\\/*?:"<>|\[\]]', "", titulo)).strip()
    if len(titulo) > 70:
        titulo = titulo[:70].rsplit(" ", 1)[0]
    if titulo.isupper():
        titulo = titulo[:1] + titulo[1:].lower()
    return f"{titulo or 'Escrito'}.{formato}"


# ── WORD ─────────────────────────────────────────
_ALINEAR = {"titulo": WD_ALIGN_PARAGRAPH.CENTER, "centro": WD_ALIGN_PARAGRAPH.CENTER,
            "firma": WD_ALIGN_PARAGRAPH.CENTER, "lineas": WD_ALIGN_PARAGRAPH.LEFT,
            "normal": WD_ALIGN_PARAGRAPH.JUSTIFY}


def _numero_de_pagina(doc):
    """El número de página abajo, al centro (un campo de Word: se cuenta solo)."""
    fp = doc.sections[0].footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = run(fp, "", size=10)
    for tipo, texto in (("begin", None), (None, "PAGE"), ("end", None)):
        if tipo:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), tipo)
        else:
            e = OxmlElement("w:instrText")
            e.set(qn("xml:space"), "preserve")
            e.text = texto
        r._r.append(e)


def generar(texto: str) -> bytes:
    doc = doc_base()
    lista = parrafos(texto)
    for i, (tipo, lineas) in enumerate(lista):
        par = doc.add_paragraph()
        par.alignment = _ALINEAR[tipo]
        f = par.paragraph_format
        f.space_before = Pt(0)
        f.space_after = Pt(18 if tipo == "titulo" else 12)
        f.line_spacing = 1.0 if tipo in ("firma", "lineas") else 1.5
        # la firma no queda sola en una hoja: se lleva el párrafo de antes (la fecha)
        f.keep_together = tipo == "firma"
        f.keep_with_next = i + 1 < len(lista) and lista[i + 1][0] == "firma"
        negrita = tipo in ("titulo", "centro")
        for j, linea in enumerate(lineas):
            if j:
                par.add_run().add_break()
            for t, b, espacio in piezas(linea, negrita):
                r = run(par, t, bold=b, size=13 if tipo == "titulo" else 12)
                if espacio:
                    r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    _numero_de_pagina(doc)
    return a_bytes(doc)


# ── PDF ──────────────────────────────────────────
# Las letras de siempre del PDF (Helvetica) solo tienen los caracteres de Europa occidental: los acentos
# y la ñ sí, las comillas tipográficas y la raya no.
_CAMBIOS = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "•": "-", " ": " ",
            "≤": "<=", "≥": ">=", "→": "->"}


def _latin1(t: str) -> str:
    for a, b in _CAMBIOS.items():
        t = t.replace(a, b)
    return t.encode("latin-1", "replace").decode("latin-1")


class _Hoja(FPDF):
    def __init__(self):
        super().__init__(unit="mm", format="A4")
        self.set_margins(left=30, top=25, right=25)
        self.set_auto_page_break(True, margin=25)
        self.add_page()

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 10, str(self.page_no()), align="C")


def generar_pdf(texto: str) -> bytes:
    pdf = _Hoja()
    alinear = {"titulo": "C", "centro": "C", "firma": "C", "lineas": "L", "normal": "J"}
    lista = parrafos(texto)
    for i, (tipo, lineas) in enumerate(lista):
        if i + 1 < len(lista) and lista[i + 1][0] == "firma" and tipo != "firma":
            # la firma no queda sola en una hoja: si no caben este párrafo y la firma, van a la siguiente
            pdf.set_font("Helvetica", "", 12)
            juntos = pdf.multi_cell(0, 6.5, _latin1("\n".join(lineas)), dry_run=True, output="HEIGHT")
            if pdf.get_y() + juntos + 5.5 * len(lista[i + 1][1]) + 4 > pdf.page_break_trigger:
                pdf.add_page()
        pdf.set_font("Helvetica", "", 13 if tipo == "titulo" else 12)
        alto = 5.5 if tipo in ("firma", "lineas") else 6.5
        negrita = tipo in ("titulo", "centro")
        texto_par = _latin1("\n".join(lineas))
        # las negritas van como **…**; si el párrafo ya tiene guiones bajos o dobles (la raya de la firma),
        # va sin negritas para que no se confundan con las marcas
        if any(m in texto_par for m in ("**", "__", "--")):
            pdf.set_font(style="B" if negrita else "")
            pdf.multi_cell(0, alto, texto_par, align=alinear[tipo], new_x="LMARGIN", new_y="NEXT")
        else:
            marcado = "\n".join("".join(f"**{t}**" if b or e else t for t, b, e in piezas(l, negrita))
                                for l in lineas)
            pdf.multi_cell(0, alto, _latin1(marcado), align=alinear[tipo], markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6 if tipo == "titulo" else 4)
    return bytes(pdf.output())
