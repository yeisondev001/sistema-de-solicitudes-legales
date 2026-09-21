"""Generadores de PDF (fpdf2) — misma data que los .docx."""

from fpdf import FPDF
from datetime import date
from .base import parse_fecha, fecha_larga, MESES
from .audiencia_provincial import _periodo_traslado, _referencia


class _Doc(FPDF):
    F = "Helvetica"

    def __init__(self):
        super().__init__(unit="mm", format="A4")
        self.set_margins(left=30, top=25, right=25)
        self.set_auto_page_break(True, margin=25)
        self.add_page()
        self.set_font(self.F, "", 12)

    def _f(self, bold=False, size=12):
        self.set_font(self.F, "B" if bold else "", size)

    def blank(self):
        self.ln(5)

    def right(self, txt, bold=True):
        self._f(bold)
        self.cell(0, 6, txt, new_x="LMARGIN", new_y="NEXT", align="R")

    def field(self, label, *rows):
        lw, sw = 38, 5
        vw = self.epw - lw - sw
        for i, (txt, bold) in enumerate(rows):
            if i == 0:
                self._f(bold=True)
                self.cell(lw, 6, label)
                self.cell(sw, 6, ":")
            else:
                self.cell(lw + sw, 6, "")
            self._f(bold=bold)
            self.multi_cell(vw, 6, txt, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def par(self, txt, align="J", bold=False):
        self._f(bold)
        self.multi_cell(0, 6, txt, align=align, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def center(self, txt, bold=False):
        self._f(bold)
        self.cell(0, 6, txt, new_x="LMARGIN", new_y="NEXT", align="C")

    def firma(self, d):
        self.blank()
        self.blank()
        self._f()
        self.cell(0, 6, "_" * 45, new_x="LMARGIN", new_y="NEXT", align="C")
        self._f(bold=True)
        self.cell(0, 6, d["firmante_nombre"], new_x="LMARGIN", new_y="NEXT", align="C")
        self._f()
        self.cell(0, 6, d["firmante_cargo"], new_x="LMARGIN", new_y="NEXT", align="C")

    def iniciales(self, txt):
        self._f(size=10)
        self.set_y(self.h - self.b_margin - 8)
        self.cell(0, 5, txt, align="L")

    def to_bytes(self):
        return bytes(self.output())


def pdf_informe_tecnico(d: dict) -> bytes:
    doc = _Doc()
    fecha = parse_fecha(d["fecha_carta"]) or date.today()
    doc.right(f"Santo Domingo, D.N.,  {fecha_larga(fecha)}")
    doc.blank()
    doc.field("Al",
              (d["destinatario"], True),
              (d["cargo_destinatario"], False))
    doc.field("Atencion",
              (d["atencion_nombre"], True),
              (d["atencion_cargo"], False))
    doc.field("Asunto", (d["asunto"], False))
    anexos = [a.strip() for a in d.get("anexos", []) if a.strip()]
    if anexos:
        doc.field("Anexo", *[(f"{i+1}- {a}", False) for i, a in enumerate(anexos)])
    doc.blank()
    cuerpo = (
        "        Cortesmente, tenemos a bien solicitarle interponer de sus buenos oficios, "
        "a los fines de que el Departamento de Catastro de esta institucion, realice una "
        "Investigacion Parcelaria, sobre el inmueble identificado como: "
        f"<< Inscripcion Catastral No. {d['inscripcion_no']}, Expedido por la Direccion "
        f"General de Catastro Nacional a nombre de {d['propietario']} >>, "
        "donde se establezca si el Estado Dominicano tiene o no derechos sobre el inmueble "
        "anteriormente descrito o si existe alguna anotacion a favor de este, a los fines de "
        f"ser utilizado como medio probatorio para la audiencia fijada para el {d['fecha_audiencia']}, "
        f"por ante el Salon {d['salon']}, {d['piso']}, {d['lugar']}, "
        f"Exp. {d['expediente']}, a nombre de la senora {d['cliente']}."
    )
    doc.par(cuerpo, align="J")
    doc.blank()
    doc.par("Nota: Esta solicitud de Informe Tecnico, esta exento de pago.", align="L")
    doc.firma(d)
    doc.iniciales(d["iniciales"])
    return doc.to_bytes()


def pdf_copia_certificada(d: dict) -> bytes:
    doc = _Doc()
    fecha = parse_fecha(d["fecha_carta"]) or date.today()
    doc.right(f"Santo Domingo, D. N.,  {fecha_larga(fecha)}.")
    doc.blank()
    doc.field("A",
              (d["destinatario"], True),
              (d["cargo_destinatario"], False))
    doc.field("Asunto", (d["asunto"], False))
    doc.blank()
    cuerpo = (
        "        Cortesmente, tenemos a bien solicitar que interponga sus buenos oficios "
        "con el objetivo de remitirnos una Copia Certificada del Expediente "
        f"completo a nombre del senor {d['nombre_cliente']}, "
        f"teniendo de la cedula de identidad y electoral No. {d['cedula']}, "
        f"en relacion con el inmueble identificado como: <<{d['descripcion_inmueble']}>>, "
        f"a los fines de ser utilizado como medio probatorio en el proceso de "
        f"{d['tipo_proceso']} que se esta conociendo por ante la {d['tribunal']}."
    )
    doc.par(cuerpo, align="J")
    doc.blank()
    doc.par("Atentamente,", align="C")
    doc.firma(d)
    doc.iniciales(d["iniciales"])
    return doc.to_bytes()


def pdf_reporte_audiencia(d: dict) -> bytes:
    doc = _Doc()
    fa = parse_fecha(d["fecha_audiencia"])
    fecha_txt = f"{fa.day} de {MESES[fa.month]} {fa.year}" if fa else d["fecha_audiencia"]

    doc.center("REPORTE DE AUDIENCIA", bold=True)
    doc.blank()

    doc._f(bold=True)
    doc.cell(22, 6, "Caja No.")
    doc._f()
    doc.cell(28, 6, d["caja_no"])
    doc._f(bold=True)
    doc.cell(10, 6, "Rol")
    doc._f()
    doc.cell(28, 6, d["rol"])
    doc._f(bold=True)
    doc.cell(14, 6, "Fecha")
    doc._f()
    doc.cell(0, 6, fecha_txt, new_x="LMARGIN", new_y="NEXT")
    doc.blank()

    materia = d.get("materia", "").replace("MATERIA ", "").strip()
    if materia:
        doc.field("Materia", (materia, False))
    doc.field("Tribunal",       (d["tribunal"],    False))
    sala = d.get("sala", "").strip()
    if sala:
        doc.field("Sala", (sala, False))
    doc.field("No. Expediente", (d["expediente"],  False))
    doc.field("Demandante(s)",  (d["demandantes"], False))
    demandados = [x.strip() for x in d.get("demandados", []) if x.strip()]
    if demandados:
        doc.field("Demandado(s)", (demandados[0], False))
        for dem in demandados[1:]:
            doc.field("Demandado", (dem, False))
    doc.field("Asunto",     (d["asunto"],  False))
    doc.field("Parcela No", (d["parcela"], False))
    doc.blank()

    doc._f(bold=True)
    doc.cell(28, 6, "Demandante")
    doc._f()
    doc.cell(0, 6, "Conclusiones: " + "_" * 55, new_x="LMARGIN", new_y="NEXT")
    doc.blank()

    doc._f(bold=True)
    doc.cell(0, 6, "Demandado", new_x="LMARGIN", new_y="NEXT")
    doc._f()
    doc.cell(0, 6, "Conclusiones: " + "_" * 58, new_x="LMARGIN", new_y="NEXT")
    doc.blank()

    doc.center("Fallo:", bold=True)
    doc.blank()
    doc.par(d["fallo"], align="L")
    doc.blank()

    fp = parse_fecha(d["fecha_proxima"])
    fp_txt = f"{fp.day} de {MESES[fp.month]} de {fp.year}" if fp else d["fecha_proxima"]
    doc._f(bold=True)
    doc.cell(76, 6, "Fecha de la proxima audiencia:")
    doc._f()
    doc.cell(0, 6, fp_txt + ".", new_x="LMARGIN", new_y="NEXT")
    doc.blank()

    doc._f(bold=True)
    doc.cell(57, 6, "Abogado que Comparecio:")
    doc._f()
    doc.cell(0, 6, d["abogados"] + ".", new_x="LMARGIN", new_y="NEXT")

    return doc.to_bytes()


def pdf_informe_audiencia_provincial(d: dict) -> bytes:
    doc = _Doc()
    fecha = parse_fecha(d["fecha_informe"]) or date.today()
    doc.par("Santo Domingo, D.N.", align="L", bold=True)
    doc.par(fecha_larga(fecha), align="L", bold=True)
    doc.blank()
    doc.field("A", ("YOLANDA DE LA CRUZ VARGAS", True), ("Directora Legal.", False))
    doc.field("DE", ("RAYMOND GREGORI ROJAS HENRIQUEZ", True), ("Abogado.", False))
    doc.field("ASUNTO", (f"INFORMES SOBRE AUDIENCIAS EN LA PROV. {d['provincia'].upper()}", False))
    doc.field("REFERENCIA", (_referencia(d), False))
    doc.blank()
    municipio = d.get("municipio", "").strip()
    lugar = f" (municipio de {municipio})" if municipio else ""
    texto = (
        "Cortesmente, tenemos a bien informarle por este medio, que "
        f"{_periodo_traslado(d['fecha_desde'], d.get('fecha_hasta', ''))}, "
        f"nos trasladamos a la provincia {d['provincia']}{lugar} a los fines de participar "
        f"en la audiencia fijada por ante el {d['tribunal']}, en ocasion de conocer del proceso "
        f"de {d['tipo_proceso']} referente: {d['inmueble']}"
    )
    if d.get("demandante", "").strip():
        texto += f", a requerimiento de {d['demandante'].strip()}"
    if d.get("expediente", "").strip():
        texto += f". Expediente No.{d['expediente'].strip()}"
    doc.par(texto + ".", align="J")
    doc.blank()
    doc.par("La misma " + d["resultado"].strip().rstrip(".") + ".", align="L")
    doc.blank()
    doc.par("Sin mas por el momento,", align="L")
    doc.blank(); doc.blank()
    doc.center("________________________________________")
    doc.center("RAYMOND ROJAS HENRIQUEZ", bold=True)
    doc.center("Abogado")
    return doc.to_bytes()


def pdf_conclusiones_saneamiento(d: dict) -> bytes:
    doc = _Doc()
    doc.field("AL", ("KATTY ECHAVARRÍA PIMENTEL.", True),
              ("JUEZ DE LA CUARTA SALA DEL TRIBUNAL DE TIERRAS DE JURISDICCIÓN ORIGINAL DEL DISTRITO NACIONAL.", False))
    doc.field("ASUNTO", ("ESCRITO DE CONCLUSIONES RELATIVO A LOS TRABAJOS DE SANEAMIENTO EN EL MUNICIPIO PARAISO, PROVINCIA BARAHONA.", False))
    doc.field("INTERVINIENTE", ("DIRECCIÓN GENERAL DE BIENES NACIONALES.", False))
    doc.field("ABOGADOS", ("LICDOS. YOLANDA DE LA CRUZ VARGAS, CARLOS MANUEL GARO PEREZ Y RAYMOND ROJAS HENRIQUEZ.", False))
    doc.field("RECLAMANTE", (d["reclamante"], False))
    doc.field("INMUEBLE", (d["inmueble"], False))
    doc.field("EXPEDIENTE", (d["expediente"], False))
    doc.blank()
    doc.par("HONORABLE MAGISTRADA:", align="L", bold=True)
    doc.par("LA DIRECCIÓN GENERAL DE BIENES NACIONALES, representante del ESTADO DOMINICANO, creada mediante la ley 1832, del 3 de noviembre del año 1948, con domicilio abierto de manera permanente en la calle Fray Cipriano Utrera No.1, Centro de los Héroes, La Feria, Santo Domingo, Distrito Nacional, representado por su Director Dr.RAFAEL A. BURGOS GÓMEZ, dominicano, mayor de edad, funcionario público, portador de la cédula de identidad y electoral no.001-0734656-1,quien tiene como abogados constituidos apoderados especiales a losLICDOS. YOLANDA DE LA CRUZ VARGASY RAYMOND ROJAS HENRIQUEZ, dominicanos, mayores de edad, portadores de la cédulas de identidad y electoral nos. 001-0168488-4,,00119447456,yconCorreo:departamentolitigiosbn@gmail.com, donde mi requirente hace formal mi elección de domicilio para todos los fines y consecuencia legales de la presente instancia, tiene a bien concluir de la siguiente manera:", align="J")
    doc.par("Conclusiones de fondo:", align="L", bold=True)
    doc.par("Primero: Nos adherimos a las conclusiones presentadas por el Abogado del Estado, la Unidad Técnica Ejecutora de Titulación de Terrenos del Estado y el Instituto Agrario Dominicano (IAD).", align="J")
    doc.par("Segundo: Que sean acogidos en su totalidad los documentos depositados, así como los informes técnicos y trabajos desaneamientos con sus respectivos planos, aprobados por la Dirección General de Mensuras Catastrales.", align="J")
    doc.par("Tercero: Ordenar al Registro de Títulos correspondiente la expedición de los Certificados de Títulos que amparen los derechos de propiedad sobre las parcelas resultantes, vinculadas al presente expediente, en virtud de haberse demostrado que el reclamante ha mantenido sobre las mismas una posesión pública, pacífica, inequívoca e ininterrumpida por más de veinte (20) años, conforme ha sido debidamente comprobado por este Tribunal.", align="J")
    doc.par("En la ciudad de Santo Domingo, Distrito Nacional, capital de la República Dominicana, a los nueve (09) días del mes de Julio del año dos mil veinticinco (2025).", align="J")
    doc.blank(); doc.blank()
    doc.center("_______________________________        ______________________________________")
    doc.center("Lic. Raymond Rojas Henríquez      Licdos. Yolanda De La Cruz Vargas")
    doc.center("Abogado.                         Encargado del Depto. de Litigios.")
    doc.blank()
    doc.center("__________________________________________")
    doc.center("Licda. Yolanda De La Cruz Vargas,")
    doc.center("Directora legal.")
    return doc.to_bytes()


def pdf_solicitud_cobros(d: dict) -> bytes:
    doc = _Doc()
    fecha = parse_fecha(d["fecha_carta"]) or date.today()
    doc.right(f"Santo Domingo DN,  {fecha_larga(fecha)}.")
    doc.blank()
    doc.field("A LA",
              (d["destinatario"], True),
              (d["cargo_destinatario"], False))
    doc.field("ASUNTO", (d["asunto"], False))
    doc.blank()
    doc.par("Distinguida senora:", align="J")
    doc.blank()
    cuerpo = (
        "        Cortesmente, tenemos a bien solicitarle, a la mayor brevedad posible, "
        "si existe algun pago de compra a nombre de los Senores o entidad Juridica "
        f"con relacion al senor {d['nombre_cliente']}, "
        f"para conocer del {d['tipo_proceso']}, dentro de la "
        f"{d['parcela']}, del Municipio {d['municipio']} de la provincia "
        f"{d['provincia']}, EXP. N0.{d['expediente']}, Ced. No. {d['cedula']}, "
        f"en el {d['tribunal']}, contra la sentencia N0.{d['sentencia']}, "
        f"de fecha {d['fecha_sentencia']}, dictada por el {d['tribunal_original']}."
    )
    doc.par(cuerpo, align="J")
    doc.blank()
    doc.par("Con saludos de alta estima;", align="L")
    doc.firma(d)
    doc.iniciales(d["iniciales"])
    return doc.to_bytes()


def pdf_solicitud_inspeccion(d: dict) -> bytes:
    doc = _Doc()
    fecha = parse_fecha(d["fecha_carta"]) or date.today()
    doc.right(f"Santo Domingo, D. N.,  {fecha_larga(fecha)}.")
    doc.blank()
    doc.field("A",
              (d["destinatario"], True),
              (d["cargo_destinatario"], False))
    doc.field("Atencion",
              (d["atencion_nombre"], True),
              (d["atencion_cargo"], False))
    doc.field("Asunto", (d["asunto"], True))
    doc.blank()
    doc._f(bold=True)
    doc.cell(0, 6, "Distinguida senora:", new_x="LMARGIN", new_y="NEXT")
    doc.blank()
    doc.par(d["cuerpo_1"], align="J")
    if d.get("cuerpo_2", "").strip():
        doc.blank()
        doc.par(d["cuerpo_2"], align="J")
    doc.blank()
    doc.par("Con saludos de alta estima;", align="J")
    doc.blank()
    doc.center("Deferentemente;")
    doc.blank()
    doc.blank()
    doc._f()
    doc.cell(0, 6, "_" * 45, new_x="LMARGIN", new_y="NEXT", align="C")
    doc._f(bold=True)
    doc.cell(0, 6, d["firmante_nombre"], new_x="LMARGIN", new_y="NEXT", align="C")
    doc._f()
    doc.cell(0, 6, d["firmante_cargo"], new_x="LMARGIN", new_y="NEXT", align="C")
    doc.blank()
    doc.par(d["iniciales"], align="L")
    if d.get("cc", "").strip():
        doc.par(f"Cc. {d['cc']}", align="L")
    return doc.to_bytes()
