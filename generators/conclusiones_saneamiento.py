"""Escrito de conclusiones de saneamiento, conforme al modelo suministrado."""

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from .base import a_bytes, doc_base, fila, p, run, tabla_encabezado


def _parrafo(doc, texto: str, sangria=False):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par.paragraph_format.space_before = Pt(0)
    par.paragraph_format.space_after = Pt(0)
    if sangria:
        par.paragraph_format.first_line_indent = Pt(36)
    run(par, texto)
    return par


def generar(d: dict) -> bytes:
    doc = doc_base()
    tabla = tabla_encabezado(doc)
    fila(tabla, "AL", ("KATTY ECHAVARRÍA PIMENTEL.", True),
         ("JUEZ DE LA CUARTA SALA DEL TRIBUNAL DE TIERRAS DE JURISDICCIÓN ORIGINAL DEL DISTRITO NACIONAL.", False))
    fila(tabla, "ASUNTO", ("ESCRITO DE CONCLUSIONES RELATIVO A LOS TRABAJOS DE SANEAMIENTO EN EL MUNICIPIO PARAISO, PROVINCIA BARAHONA.", False))
    fila(tabla, "INTERVINIENTE", ("DIRECCIÓN GENERAL DE BIENES NACIONALES.", False))
    fila(tabla, "ABOGADOS", ("LICDOS. YOLANDA DE LA CRUZ VARGAS, CARLOS MANUEL GARO PEREZ Y RAYMOND ROJAS HENRIQUEZ.", False))
    fila(tabla, "RECLAMANTE", (d["reclamante"], False))
    fila(tabla, "INMUEBLE", (d["inmueble"], False))
    fila(tabla, "EXPEDIENTE", (d["expediente"], False))
    p(doc)
    p(doc, "HONORABLE MAGISTRADA:", bold=True)
    _parrafo(
        doc,
        "LA DIRECCIÓN GENERAL DE BIENES NACIONALES, representante del ESTADO DOMINICANO, creada mediante la ley 1832, del 3 de noviembre del año 1948, con domicilio abierto de manera permanente en la calle Fray Cipriano Utrera No.1, Centro de los Héroes, La Feria, Santo Domingo, Distrito Nacional, representado por su Director Dr.RAFAEL A. BURGOS GÓMEZ, dominicano, mayor de edad, funcionario público, portador de la cédula de identidad y electoral no.001-0734656-1,quien tiene como abogados constituidos apoderados especiales a losLICDOS. YOLANDA DE LA CRUZ VARGASY RAYMOND ROJAS HENRIQUEZ, dominicanos, mayores de edad, portadores de la cédulas de identidad y electoral nos. 001-0168488-4,,00119447456,yconCorreo:departamentolitigiosbn@gmail.com, donde mi requirente hace formal mi elección de domicilio para todos los fines y consecuencia legales de la presente instancia, tiene a bien concluir de la siguiente manera:",
        sangria=True,
    )
    p(doc)
    p(doc, "Conclusiones de fondo:", bold=True)
    _parrafo(doc, "Primero: Nos adherimos a las conclusiones presentadas por el Abogado del Estado, la Unidad Técnica Ejecutora de Titulación de Terrenos del Estado y el Instituto Agrario Dominicano (IAD).")
    _parrafo(doc, "Segundo: Que sean acogidos en su totalidad los documentos depositados, así como los informes técnicos y trabajos desaneamientos con sus respectivos planos, aprobados por la Dirección General de Mensuras Catastrales.")
    _parrafo(doc, "Tercero: Ordenar al Registro de Títulos correspondiente la expedición de los Certificados de Títulos que amparen los derechos de propiedad sobre las parcelas resultantes, vinculadas al presente expediente, en virtud de haberse demostrado que el reclamante ha mantenido sobre las mismas una posesión pública, pacífica, inequívoca e ininterrumpida por más de veinte (20) años, conforme ha sido debidamente comprobado por este Tribunal.")
    p(doc)
    _parrafo(doc, "En la ciudad de Santo Domingo, Distrito Nacional, capital de la República Dominicana, a los nueve (09) días del mes de Julio del año dos mil veinticinco (2025).")
    p(doc); p(doc)
    p(doc, "_______________________________        ______________________________________", align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "Lic. Raymond Rojas Henríquez                         Licdos. Yolanda De La Cruz Vargas", align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "Abogado.                                    Encargado del Depto. de Litigios.", align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc)
    p(doc, "__________________________________________", align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "Licda. Yolanda De La Cruz Vargas,", align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "Directora legal.", align=WD_ALIGN_PARAGRAPH.CENTER)
    return a_bytes(doc)
