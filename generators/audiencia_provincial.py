"""Informe narrativo de las audiencias celebradas fuera de Santo Domingo."""

from datetime import date

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from .base import (
    MESES, a_bytes, doc_base, fecha_larga, fila, p, parse_fecha, run,
    tabla_encabezado,
)


def _fecha_de_audiencia(valor: str) -> str:
    fecha = parse_fecha(valor)
    if not fecha:
        return valor
    return f"{fecha.day} del mes de {MESES[fecha.month]} del año {fecha.year}"


def _periodo_traslado(desde: str, hasta: str) -> str:
    inicio = parse_fecha(desde)
    fin = parse_fecha(hasta)
    if inicio and fin and inicio != fin:
        return (
            f"desde el día {inicio.day} del mes de {MESES[inicio.month]} del año {inicio.year} "
            f"hasta el día {fin.day} del mes de {MESES[fin.month]} del año {fin.year}"
        )
    return f"en fecha {_fecha_de_audiencia(desde)}"


def _referencia(d: dict) -> str:
    partes = [d["tipo_proceso"].strip(), d["inmueble"].strip()]
    if d.get("demandante", "").strip():
        partes.append(f"a requerimiento de {d['demandante'].strip()}")
    if d.get("expediente", "").strip():
        partes.append(f"Expediente No.{d['expediente'].strip()}")
    return ", ".join(x for x in partes if x)


def generar(d: dict) -> bytes:
    doc = doc_base()
    fecha_informe = parse_fecha(d["fecha_informe"]) or date.today()

    p(doc, "Santo Domingo, D.N.", bold=True)
    p(doc, fecha_larga(fecha_informe), bold=True)
    p(doc)

    tabla = tabla_encabezado(doc)
    fila(tabla, "A", ("YOLANDA DE LA CRUZ VARGAS", True), ("Directora Legal.", False))
    fila(tabla, "DE", ("RAYMOND GREGORI ROJAS HENRIQUEZ", True), ("Abogado.", False))
    fila(tabla, "ASUNTO", (f"INFORMES SOBRE AUDIENCIAS EN LA PROV. {d['provincia'].upper()}", False))
    fila(tabla, "REFERENCIA", (_referencia(d), False))
    p(doc)

    municipio = d.get("municipio", "").strip()
    lugar = f" (municipio de {municipio})" if municipio else ""
    tribunal = d["tribunal"].strip()
    cuerpo = doc.add_paragraph()
    cuerpo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    cuerpo.paragraph_format.first_line_indent = Pt(36)
    cuerpo.paragraph_format.space_before = Pt(0)
    cuerpo.paragraph_format.space_after = Pt(0)
    run(cuerpo, "Cortésmente, tenemos a bien informarle por este medio, que ")
    run(cuerpo, f"{_periodo_traslado(d['fecha_desde'], d.get('fecha_hasta', ''))}, ")
    run(cuerpo, f"nos trasladamos a la provincia {d['provincia']}{lugar} ")
    run(cuerpo, "a los fines de participar en la audiencia fijada ")
    run(cuerpo, f"por ante el {tribunal}, ")
    run(cuerpo, f"en ocasión de conocer del proceso de {d['tipo_proceso']} referente: ")
    run(cuerpo, d["inmueble"], bold=True)
    if d.get("demandante", "").strip():
        run(cuerpo, f", a requerimiento de {d['demandante'].strip()}", bold=True)
    if d.get("expediente", "").strip():
        run(cuerpo, f". Expediente No.{d['expediente'].strip()}", bold=True)
    run(cuerpo, ".")

    p(doc)
    resultado = d["resultado"].strip().rstrip(".")
    p(doc, f"La misma {resultado}.")
    p(doc)
    p(doc, "Sin más por el momento,")
    p(doc)
    p(doc, "________________________________________", align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "RAYMOND ROJAS HENRIQUEZ", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "Abogado", align=WD_ALIGN_PARAGRAPH.CENTER)
    return a_bytes(doc)
