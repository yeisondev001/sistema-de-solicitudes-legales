from datetime import date
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from .base import (
    doc_base, tabla_encabezado, fila, firma_bloque,
    footer_iniciales, p, run, parse_fecha, fecha_larga, a_bytes,
)


def _cuerpo(doc, d):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par.paragraph_format.space_before = par.paragraph_format.space_after = Pt(0)
    run(par, "\t\t")
    run(par, "Cortésmente, tenemos a bien solicitar que interponga sus buenos oficios "
             "con el objetivo de remitirnos una Copia Certificada del Expediente "
             "completo a nombre del señor ")
    run(par, f"{d['nombre_cliente']}", bold=True)
    run(par, ", teniendo de la cédula de identidad y electoral No. ")
    run(par, f"{d['cedula']}")
    run(par, ", en relación con el inmueble identificado como: «")
    run(par, f"{d['descripcion_inmueble']}", bold=True)
    run(par, f"», a los fines de ser utilizado como medio probatorio en el proceso de ")
    run(par, f"{d['tipo_proceso']}", bold=True)
    run(par, " que se está conociendo por ante la ")
    run(par, f"{d['tribunal']}", bold=True)
    run(par, " ».")


def generar(d: dict) -> bytes:
    doc = doc_base()
    fecha = parse_fecha(d["fecha_carta"]) or date.today()
    p(doc, "Santo Domingo, D. N.", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    p(doc, fecha_larga(fecha) + ".", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    p(doc)
    t = tabla_encabezado(doc)
    fila(t, "A",
         (d["destinatario"],       True),
         (d["cargo_destinatario"], False))
    fila(t, "Asunto", (d["asunto"], False))
    p(doc)
    _cuerpo(doc, d)
    p(doc)
    p(doc, "Atentamente,", align=WD_ALIGN_PARAGRAPH.CENTER)
    firma_bloque(doc, d)
    footer_iniciales(doc, d["iniciales"])
    return a_bytes(doc)
