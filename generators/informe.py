from datetime import date
from docx.enum.text import WD_ALIGN_PARAGRAPH
from .base import (
    doc_base, tabla_encabezado, fila, firma_bloque,
    footer_iniciales, p, run, parse_fecha, fecha_larga, a_bytes,
)


def _cuerpo(doc, d):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par.paragraph_format.space_before = par.paragraph_format.space_after = __import__("docx.shared", fromlist=["Pt"]).Pt(0)
    run(par, "\t\t")
    run(par, "Cortésmente, tenemos a bien solicitarle interponer de sus buenos oficios, "
             "a los fines de que el Departamento de Catastro de esta institución, realice una "
             "Investigación Parcelaria, sobre el inmueble identificado como: «")
    run(par, f" Inscripción Catastral No. {d['inscripcion_no']} , Expedido por la Dirección "
             f"General de Catastro Nacional a nombre de {d['propietario']} »", bold=True)
    run(par, ", donde se establezca si el ")
    run(par, "Estado Dominicano", bold=True)
    run(par, " tiene o no derechos sobre el inmueble anteriormente descrito "
             "o si existe alguna anotación a favor de este, a los fines de ser utilizado "
             "como medio probatorio ")
    run(par, f"para la audiencia fijada para el {d['fecha_audiencia']},", bold=True)
    run(par, f" por ante el Salón {d['salon']}, {d['piso']}, {d['lugar']}")
    run(par, f", Exp. {d['expediente']}", bold=True)
    run(par, ", a nombre de la señora ")
    run(par, f"{d['cliente']}.", bold=True)


def generar(d: dict) -> bytes:
    doc = doc_base()
    fecha = parse_fecha(d["fecha_carta"]) or date.today()
    p(doc, "Santo Domingo, D.N.", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    p(doc, fecha_larga(fecha),    bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    p(doc)
    t = tabla_encabezado(doc)
    fila(t, "Al",
         (d["destinatario"],       True),
         (d["cargo_destinatario"], False))
    fila(t, "Atención",
         (d["atencion_nombre"], True),
         (d["atencion_cargo"],  False))
    fila(t, "Asunto", (d["asunto"], False))
    anexos = [a.strip() for a in d.get("anexos", []) if a.strip()]
    if anexos:
        fila(t, "Anexo", *[(f"{i+1}- {a}", False) for i, a in enumerate(anexos)])
    p(doc)
    _cuerpo(doc, d)
    p(doc)
    p(doc, "Nota: Esta solicitud de Informe Técnico, está exento de pago.")
    firma_bloque(doc, d)
    footer_iniciales(doc, d["iniciales"])
    return a_bytes(doc)
