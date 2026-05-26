from datetime import date
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm
from .base import (
    doc_base, tabla_encabezado, fila, firma_bloque,
    footer_iniciales, p, run, parse_fecha, fecha_larga, a_bytes,
)


def generar(d: dict) -> bytes:
    doc = doc_base()
    for s in doc.sections:
        s.right_margin = Cm(3)

    fecha = parse_fecha(d["fecha_carta"]) or date.today()
    p(doc, "Santo Domingo DN,",     align=WD_ALIGN_PARAGRAPH.RIGHT)
    p(doc, fecha_larga(fecha) + ".", align=WD_ALIGN_PARAGRAPH.RIGHT)
    p(doc)

    t = tabla_encabezado(doc)
    fila(t, "A LA",
         (d["destinatario"],       True),
         (d["cargo_destinatario"], False))
    fila(t, "ASUNTO", (d["asunto"], False))
    p(doc)

    p(doc, "Distinguida señora:", align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    p(doc)

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par.paragraph_format.space_before = par.paragraph_format.space_after = Pt(0)
    run(par, "\t\t")
    run(par, "Cortésmente, tenemos a bien solicitarle, a la mayor brevedad posible, "
             "si existe algún pago de compra a nombre de los Señores o entidad Jurídica "
             "con relación al señor ")
    run(par, d["nombre_cliente"], bold=True)
    run(par, f", para conocer del {d['tipo_proceso']}, dentro de la "
             f"{d['parcela']}, del Municipio {d['municipio']} de la provincia "
             f"{d['provincia']}, EXP. N0.{d['expediente']}, Ced. No. {d['cedula']}, "
             f"en el {d['tribunal']}, contra la sentencia N0.{d['sentencia']}, "
             f"de fecha {d['fecha_sentencia']}, dictada por el {d['tribunal_original']}.")
    p(doc)
    p(doc, "Con saludos de alta estima;")
    firma_bloque(doc, d)
    footer_iniciales(doc, d["iniciales"])
    return a_bytes(doc)
