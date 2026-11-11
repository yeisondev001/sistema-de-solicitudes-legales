"""
Redacción: las plantillas de solicitudes (Word y PDF) y sus listas
==================================================================
Solo para las cuentas con plantillas activadas. Los documentos los arman los generadores
de generators/; aquí está lo que cada plantilla necesita: valores iniciales, campos
obligatorios y el nombre del archivo. Lo usan la app de Flet (main.py) y servidor.py.
"""

from datetime import datetime, timedelta, timezone

from generators import (
    generar_informe_tecnico, generar_copia_certificada, generar_reporte_audiencia, generar_solicitud_cobros,
    generar_solicitud_inspeccion, generar_informe_audiencia_provincial, generar_conclusiones_saneamiento,
    nombre_archivo, pdf_informe_tecnico, pdf_copia_certificada, pdf_reporte_audiencia, pdf_solicitud_cobros,
    pdf_solicitud_inspeccion, pdf_informe_audiencia_provincial, pdf_conclusiones_saneamiento,
)

ZONA_RD = timezone(timedelta(hours=-4))   # República Dominicana no cambia la hora en verano


# ── LISTAS DE TRIBUNALES Y SALAS ─────────────────
TRIBUNALES_INMOBILIARIA = [
    "SUPREMA CORTE DE JUSTICIA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE AZUA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE BARAHONA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE DUARTE",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE EL SEIBO",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE ESPAILLAT",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE HERMANAS MIRABAL",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE LA ALTAGRACIA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE LA VEGA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MARIA TRINIDAD SÁNCHEZ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MONSEÑOR NOUEL",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MONTE CRISTI",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MONTE PLATA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE PERAVIA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE PUERTO PLATA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAMANÁ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAN CRISTÓBAL",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAN JUAN DE LA MAGUANA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAN PEDRO DE MACORÍS",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SÁNCHEZ RAMÍREZ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SANTIAGO",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SANTIAGO RODRIGUEZ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE VALVERDE",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DEL DISTRITO NACIONAL",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO CENTRAL",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO ESTE",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO NORESTE",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO NORTE",
]

TRIBUNALES_CIVIL = [
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE BARAHONA",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN FRANCISCO DE MACORÍS",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE LA VEGA",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN CRISTÓBAL",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN JUAN DE LA MAGUANA",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN PEDRO DE MACORÍS",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SANTIAGO",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SANTO DOMINGO",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DEL DISTRITO NACIONAL",
    "CÁMARA CIVIL Y COMERCIAL DEL JUZGADO DE PRIMERA INSTANCIA DE AZUA",
]

SALAS_INMOBILIARIA = [
    "Primera Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Segunda Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Tercera Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Cuarta Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Quinta Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Sexta Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Séptima Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Octava Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
]

ASUNTOS_INMOBILIARIA = [
    "SOLICITUD DE DESLINDE",
    "SANEAMIENTO",
    "LITIS SOBRE DERECHOS REGISTRADOS",
]

TIPOS_AUDIENCIA_PROVINCIAL = [
    "Deslinde",
    "Deslinde y su división",
    "Deslinde, su división y refundición",
    "Saneamiento",
    "Litis sobre Derechos Registrados",
]

RECLAMANTES_SANEAMIENTO = [
    "COMISIÓN PERMANENTE DE TITULACIÓN DE TERRENOS DEL ESTADO (UTEC).",
    "INSTITUTO AGRARIO DOMINICANO (IAD), REPRESENTADO POR LA COMISIÓN PERMANENTE DE TITULACIÓN DE TERRENOS DEL ESTADO.",
]


# ── PLANTILLAS ───────────────────────────────────
def _hoy() -> str:
    hoy = datetime.now(ZONA_RD)
    return f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}"


def _ident(*claves, otro="Solicitud"):
    """Lo que va en el nombre del archivo: los valores de esas claves, unidos con guion."""
    return lambda d: "-".join(x for x in (str(d.get(k) or "").strip() for k in claves) if x) or otro


# Cada plantilla: nombre, qué es, valores con que empieza el formulario, campos obligatorios
# (clave, nombre para el aviso), generadores de Word y PDF, y cómo se nombra el archivo.
# Los campos de cada formulario, en pantalla, están en web/src/lib/plantillas.ts.
PLANTILLAS = {
    "informe": {
        "nombre": "Informe Técnico", "sub": "Catastro · Investigación Parcelaria",
        "valores": lambda: {
            "fecha_carta": _hoy(), "destinatario": "Arq. Gilberto Grullón.", "cargo_destinatario": "Director técnico.",
            "atencion_nombre": "Agrim. Julio Yens Seijas,", "atencion_cargo": "Encargado del Depto. de Catastro",
            "asunto": "Solicitud de Investigación Parcelaria.",
            "anexos": ["Acto No. ", "Certificado de Inscripción Catastral No. "],
            "inscripcion_no": "", "propietario": "", "fecha_audiencia": "", "salon": "3", "piso": "Segundo Piso",
            "lugar": "Ciudad Judicial", "expediente": "", "cliente": "",
            "firmante_nombre": "YOLANDA DE LA CRUZ VARGAS.", "firmante_cargo": "Directora Legal.", "iniciales": "JDCV/rr",
        },
        "requeridos": [("inscripcion_no", "No. Inscripción Catastral"), ("propietario", "Propietario"),
                       ("fecha_audiencia", "Fecha de audiencia"), ("expediente", "No. Expediente"),
                       ("cliente", "Cliente"), ("anexos", "al menos un Anexo")],
        "word": generar_informe_tecnico, "pdf": pdf_informe_tecnico,
        "archivo": "Informe Tecnico", "ident": _ident("cliente"),
    },
    "archivo": {
        "nombre": "Archivo", "sub": "Archivo · Expediente",
        "valores": lambda: {
            "fecha_carta": _hoy(), "destinatario": "Sr. Leibi Rafael Méndez Beltre.",
            "cargo_destinatario": "Encargado interino de la División de Archivos de Expedientes Legales.",
            "asunto": "Solicitud de Copia Certificada de Expediente.", "nombre_cliente": "", "cedula": "",
            "descripcion_inmueble": "", "materia": "", "tipo_proceso": "deslinde", "tribunal": "", "sala": "",
            "firmante_nombre": "YOLANDA DE LA CRUZ VARGAS.", "firmante_cargo": "Directora Legal.", "iniciales": "YDCV/rr",
        },
        "requeridos": [("nombre_cliente", "Nombre del cliente"), ("cedula", "Cédula"),
                       ("descripcion_inmueble", "Descripción del inmueble"), ("tipo_proceso", "Tipo de proceso"),
                       ("tribunal", "Tribunal")],
        "word": generar_copia_certificada, "pdf": pdf_copia_certificada,
        "archivo": "Solicitud de Archivo", "ident": _ident("nombre_cliente"),
    },
    "reporte": {
        "nombre": "Reporte de Audiencia", "sub": "Audiencia · Fallo y próxima fecha",
        "valores": lambda: {
            "materia": "", "tribunal": "", "sala": "", "expediente": "", "demandantes": "", "demandados": [""],
            "asunto": "Solicitud de Deslinde.", "parcela": "", "agrimensor": "", "caja_no": "", "rol": "",
            "fecha_audiencia": _hoy(), "fallo": "", "fecha_proxima": "", "abogados": "",
        },
        "requeridos": [("tribunal", "Tribunal"), ("expediente", "No. Expediente"), ("demandantes", "Demandante(s)"),
                       ("parcela", "Parcela"), ("fecha_audiencia", "Fecha de audiencia"), ("fallo", "Fallo"),
                       ("fecha_proxima", "Fecha próxima audiencia"), ("abogados", "Abogado(s)"),
                       ("demandados", "Demandado(s)")],
        "word": generar_reporte_audiencia, "pdf": pdf_reporte_audiencia,
        "archivo": "Reporte de Audiencia", "ident": _ident("demandantes", "expediente", otro="Reporte"),
        "historial": True,   # cada reporte generado se guarda en el historial de expedientes
    },
    "cobros": {
        "nombre": "Cobros", "sub": "Cobros · Verificación de pago",
        "valores": lambda: {
            "fecha_carta": _hoy(), "destinatario": "Licda. Denisse Amadés",
            "cargo_destinatario": "Encargada dpto. de cobros.", "asunto": "SI EXISTE CUENTA O PAGO.",
            "nombre_cliente": "", "materia": "", "tipo_proceso": "Saneamiento", "parcela": "Designación Posesional No.",
            "municipio": "", "provincia": "", "expediente": "", "cedula": "", "tribunal": "", "sala": "",
            "sentencia": "", "fecha_sentencia": "", "tribunal_original": "",
            "firmante_nombre": "LICDA. YOLANDA DE LA CRUZ VARGAS.", "firmante_cargo": "Directora Legal.",
            "iniciales": "YDLCV/rr",
        },
        "requeridos": [("nombre_cliente", "Nombre del cliente"), ("tipo_proceso", "Tipo de proceso"),
                       ("parcela", "Parcela"), ("municipio", "Municipio"), ("provincia", "Provincia"),
                       ("expediente", "No. Expediente"), ("cedula", "Cédula"), ("tribunal", "Tribunal"),
                       ("sentencia", "No. Sentencia"), ("fecha_sentencia", "Fecha sentencia"),
                       ("tribunal_original", "Tribunal que dictó la sentencia")],
        "word": generar_solicitud_cobros, "pdf": pdf_solicitud_cobros,
        "archivo": "Solicitud de Cobros", "ident": _ident("nombre_cliente"),
    },
    "inspeccion": {
        "nombre": "Inspección", "sub": "Inspección · Cuerpo libre",
        "valores": lambda: {
            "fecha_carta": _hoy(), "destinatario": "", "cargo_destinatario": "Director Técnico", "atencion_nombre": "",
            "atencion_cargo": "Encargada dpto. de Inspección.", "asunto": "Solicitud de Inspección",
            "cuerpo_1": "Muy cortésmente, por medio de la presente, solicitamos que nos informe ", "cuerpo_2": "",
            "firmante_nombre": "YOLANDA DE LA CRUZ VARGAS.", "firmante_cargo": "Directora Legal.",
            "iniciales": "YDLCV/rr", "cc": "",
        },
        "requeridos": [("destinatario", "Destinatario"), ("asunto", "Asunto"), ("cuerpo_1", "Párrafo principal")],
        "word": generar_solicitud_inspeccion, "pdf": pdf_solicitud_inspeccion,
        "archivo": "Solicitud de Inspeccion", "ident": _ident("destinatario"),
    },
    "audiencia_provincial": {
        "nombre": "Provincial", "sub": "Audiencia · Traslado a provincia",
        "valores": lambda: {
            "fecha_informe": _hoy(), "provincia": "", "municipio": "", "fecha_desde": _hoy(), "fecha_hasta": "",
            "tribunal": "", "tipo_proceso": "Deslinde", "inmueble": "", "demandante": "", "expediente": "",
            "resultado": "",
        },
        "requeridos": [("provincia", "Provincia"), ("fecha_desde", "Fecha de traslado"), ("tribunal", "Tribunal"),
                       ("tipo_proceso", "Tipo de proceso"), ("inmueble", "Inmueble"), ("demandante", "Demandante"),
                       ("resultado", "Resultado de la audiencia")],
        "word": generar_informe_audiencia_provincial, "pdf": pdf_informe_audiencia_provincial,
        "archivo": "Informe de Audiencia Provincial",
        "ident": _ident("provincia", "expediente", otro="Audiencia provincial"),
    },
    "conclusiones_saneamiento": {
        "nombre": "Conclusiones", "sub": "Saneamiento · Modelo fijo",
        "valores": lambda: {"expediente": "", "reclamante": RECLAMANTES_SANEAMIENTO[0], "inmueble": ""},
        "requeridos": [("expediente", "No. de expediente"), ("reclamante", "Reclamante"), ("inmueble", "Inmueble")],
        "word": generar_conclusiones_saneamiento, "pdf": pdf_conclusiones_saneamiento,
        "archivo": "Conclusiones de Saneamiento", "ident": _ident("expediente"),
    },
}

LISTAS = {
    "tribunales_inmobiliaria": TRIBUNALES_INMOBILIARIA, "tribunales_civil": TRIBUNALES_CIVIL,
    "salas_inmobiliaria": SALAS_INMOBILIARIA, "asuntos_inmobiliaria": ASUNTOS_INMOBILIARIA,
    "tipos_audiencia_provincial": TIPOS_AUDIENCIA_PROVINCIAL, "reclamantes_saneamiento": RECLAMANTES_SANEAMIENTO,
}


def faltantes(clave: str, d: dict) -> list:
    """Los campos obligatorios que están vacíos (las listas cuentan si tienen algo escrito)."""
    falta = []
    for campo, nombre in PLANTILLAS[clave]["requeridos"]:
        valor = d.get(campo)
        lleno = any(str(x).strip() for x in valor) if isinstance(valor, list) else bool(str(valor or "").strip())
        if not lleno:
            falta.append(nombre)
    return falta


def generar(clave: str, d: dict, formato: str) -> tuple:
    """(contenido, nombre del archivo) del documento en Word ("docx") o PDF ("pdf").
    ValueError si faltan campos obligatorios."""
    p = PLANTILLAS[clave]
    falta = faltantes(clave, d)
    if falta:
        raise ValueError("Campos requeridos: " + ", ".join(falta))
    datos = {**p["valores"](), **d}
    contenido = (p["pdf"] if formato == "pdf" else p["word"])(datos)
    nombre = nombre_archivo(p["archivo"], p["ident"](datos))
    return contenido, nombre.replace(".docx", ".pdf") if formato == "pdf" else nombre
