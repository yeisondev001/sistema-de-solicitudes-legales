"""
Redacción a partir del documento de la otra parte (sala «Redacción»).

El abogado elige qué quiere hacer (demanda, escrito de defensa, recurso de apelación, de casación o de revisión
constitucional) y sube el documento al que responde: la demanda que recibió, la sentencia que va a recurrir…

Ley 172-13: el documento NO va tal cual a la IA. Antes, aquí y sin la IA, se cambian por datos por llenar
los nombres de las personas, las cédulas, RNC, pasaportes, teléfonos, correos y domicilios: [PERSONA 1],
[CÉDULA 1], [DOMICILIO 1]… El abogado ve el texto así antes de mandarlo y puede borrar lo que se haya escapado.
La lista de qué dato es cada uno (el «mapa») vuelve solo a su navegador, que la guarda como «Datos por llenar»
de ese escrito: la IA y la base de Papiniano nunca la ven, y los datos solo se ponen al descargar el Word o PDF.
"""

import re
import tempfile
from pathlib import Path

import modelos

TIPOS = {
    "demanda": {
        # el nombre del modelo tiene que decir alguna de «debe» y ninguna de «no» (sin tildes, el principio)
        "debe": ["demand"],
        "no": [],
        "nombre": "Demanda",
        "documento": "El documento en que se basa: el contrato, el acto, la sentencia o la intimación que tenga.",
        "grupos": ["demandas"],
        "pedido": "una demanda introductiva de instancia a favor de nuestro cliente, basada en el documento",
        "palabras": "demanda",
    },
    "defensa": {
        # el nombre del modelo tiene que decir alguna de «debe» y ninguna de «no» (sin tildes, el principio)
        "debe": ["defensa", "conclus"],
        "no": ["casaci"],
        "nombre": "Escrito de defensa",
        "documento": "La demanda o el recurso que recibió su cliente.",
        "grupos": ["defensas", "conclusiones"],
        "pedido": "un escrito de defensa para la parte demandada o recurrida (nuestro cliente), que responda punto "
                  "por punto al documento y pida su rechazo, con los medios de inadmisión que apliquen",
        "palabras": "escrito de defensa",
    },
    "apelacion": {
        # el nombre del modelo tiene que decir alguna de «debe» y ninguna de «no» (sin tildes, el principio)
        "debe": ["apelaci"],
        "no": ["casaci"],
        "nombre": "Recurso de apelación",
        "documento": "La sentencia de primer grado que quiere apelar.",
        "grupos": ["recursos", "conclusiones"],
        "pedido": "un recurso de apelación contra la sentencia del documento, a favor de la parte que perdió "
                  "(nuestro cliente), con los agravios que causa la sentencia y la revocación que se pide",
        "palabras": "recurso de apelacion",
    },
    "casacion": {
        # el nombre del modelo tiene que decir alguna de «debe» y ninguna de «no» (sin tildes, el principio)
        "debe": ["casaci"],
        "no": [],
        "nombre": "Recurso de casación",
        "documento": "La sentencia de la corte o del tribunal de segundo grado que quiere recurrir.",
        "grupos": ["recursos"],
        "pedido": "un memorial de casación contra la sentencia del documento, a favor de la parte que perdió "
                  "(nuestro cliente), con los medios de casación (violación de la ley, falta de base legal, "
                  "desnaturalización, falta de motivos) bien desarrollados",
        "palabras": "recurso de casacion memorial",
    },
    "constitucional": {
        # el nombre del modelo tiene que decir alguna de «debe» y ninguna de «no» (sin tildes, el principio)
        "debe": ["constitu"],
        "no": [],
        "nombre": "Recurso de revisión constitucional",
        "documento": "La sentencia firme que quiere llevar ante el Tribunal Constitucional.",
        "grupos": [],
        "pedido": "un recurso de revisión constitucional de decisión jurisdiccional ante el Tribunal "
                  "Constitucional contra la sentencia del documento, a favor de la parte que perdió (nuestro "
                  "cliente), con los derechos fundamentales vulnerados y la especial trascendencia o relevancia "
                  "constitucional",
        "palabras": "recurso de revision constitucional",
    },
}

MAX_CARACTERES = 200_000   # lo que se lee del documento
MAX_PARA_IA = 14_000       # lo que se le manda a la IA para analizarlo (~4.000 tokens; Groq da 8.000 por minuto)

# ── Quitar los datos de las personas, sin la IA ─────────────────────────────────

_MAYUS = "A-ZÁÉÍÓÚÜÑ"
_PALABRA_NOMBRE = rf"(?:[{_MAYUS}][a-záéíóúüñ]+|[{_MAYUS}]{{2,}}|[{_MAYUS}]\.)"
_UNION = r"(?:\s+(?:de\s+(?:la\s+|los\s+|las\s+)?|del\s+|y\s+)?)"
_NOMBRE = rf"{_PALABRA_NOMBRE}(?:{_UNION}{_PALABRA_NOMBRE}){{1,6}}"

# palabras que no son de nombres de personas: si un «nombre» las tiene, no se toca
_NO_NOMBRE = {
    "tribunal", "juzgado", "corte", "suprema", "justicia", "republica", "dominicana", "dominicano", "santo",
    "domingo", "distrito", "nacional", "sala", "salas", "primera", "segunda", "tercera", "reunidas", "pleno",
    "codigo", "ley", "civil", "comercial", "laboral", "trabajo", "tierras", "jurisdiccion", "original", "superior",
    "camara", "instancia", "ministerio", "publico", "procuraduria", "procurador", "direccion", "general",
    "registro", "titulos", "mensuras", "catastrales", "banco", "poder", "judicial", "constitucion", "constitucional",
    "articulo", "considerando", "atendido", "resulta", "fallo", "falla", "sentencia", "recurso", "apelacion",
    "casacion", "demanda", "demandante", "demandado", "demandada", "recurrente", "recurrido", "recurrida",
    "abogado", "abogados", "magistrado", "magistrada", "presidente", "presidenta", "juez", "jueza", "provincia",
    "municipio", "ayuntamiento", "consejo", "administrativo", "contencioso", "estado", "senado", "camara",
    "diputados", "secretaria", "secretario", "notario", "alguacil", "ordinario", "estrados", "colegio",
    "matricula", "expediente", "parcela", "solar", "manzana", "inmueble", "calle", "avenida", "sector", "ensanche",
    "contrato", "venta", "acto", "resolucion", "decreto", "reglamento", "srl", "eirl", "sas", "s.a.", "s.r.l.",
    "compania", "empresa", "sociedad", "asociacion", "fundacion", "cooperativa", "universidad", "hospital",
    "honorable", "jueces", "fiscal", "fiscalia", "policia", "agricultura", "hacienda", "impuestos", "internos",
    "por", "tales", "motivos", "primero", "segundo", "tercero", "cuarto", "quinto", "unico", "dispositivo",
    "conclusiones", "hechos", "derecho", "fundamentos", "puntos", "que", "en", "el", "la", "los", "las", "con",
}
# lo que sigue a un nombre en los escritos dominicanos: «JUAN PÉREZ, dominicano, mayor de edad, portador…»
_DESPUES = re.compile(r"\s*,\s*(?:dominican[oa]s?|mayor(?:es)? de edad|portador[ae]?s?|solter[oa]|casad[oa]|"
                      r"viud[oa]|divorciad[oa]|de nacionalidad|venezolan[oa]|haitian[oa]|estadounidense|"
                      r"comerciante|empleado|empleada|ingenier[oa]|médic[oa]|agricultor|ama de casa)", re.I)
# lo que va antes: «el señor JUAN PÉREZ», «Lic. JUAN PÉREZ», «a requerimiento de JUAN PÉREZ»
_ANTES = re.compile(r"(?:\b(?:señor(?:a|es|as)?|sr\.|sra\.|srta\.|lic\.|licdo\.|licda\.|licdos\.|licdas\.|"
                    r"licenciad[oa]s?|dr\.|dra\.|doctor(?:a)?|ing\.|arq\.|ciudadan[oa]|finad[oa]|"
                    r"de cujus|requerimiento de|a favor de|en contra de|contra|interpuesto por|incoad[oa] por|"
                    r"representad[oa] por)\s+)$", re.I)

_DOMICILIO = re.compile(
    r"(domiciliad[oa]s?(?:\s+y\s+residentes?)?\s+en|residentes?\s+en|con\s+domicilio(?:\s+social)?\s+en|"
    r"con\s+estudio\s+profesional\s+abierto\s+en|ubicad[oa]\s+en\s+la\s+calle)\s+((?:[^;:.]|\.(?=\s?\d))(?:[^;:.]|\.(?=\s?\d)){5,179}?)"
    r"(?=\s*(?:[;:]|\.(?!\s?\d))|\s*,\s*(?:de\s+esta|en\s+esta|quien|lugar|donde|y\s+con|ciudad|municipio\s+de|provincia\s+de))",
    re.I)

_OTROS = [
    ("CORREO", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("CÉDULA", re.compile(r"\b\d{3}-?\d{7}-?\d\b")),
    ("RNC", re.compile(r"\b\d-?\d{2}-?\d{5}-?\d\b")),
    ("PASAPORTE", re.compile(r"(?<=pasaporte)(?:\s+(?:núm\.?|no\.?|número)?\s*)([A-Z]{1,3}\d{5,9})\b", re.I)),
    ("TELÉFONO", re.compile(r"\(?\b8[024]9\)?[-\s.]?\d{3}[-\s.]?\d{4}\b")),
]


def _sin_tildes(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _es_nombre(candidato: str) -> bool:
    palabras = [p for p in re.findall(r"[\wÁÉÍÓÚÜÑáéíóúüñ.]+", candidato) if p.lower() not in ("de", "del", "la",
                                                                                              "los", "las", "y")]
    if len(palabras) < 2:
        return False
    return not any(_sin_tildes(p).strip(".") in _NO_NOMBRE for p in palabras)


_CONECTORES = {"de", "del", "la", "los", "las", "y"}


def _apellidos(nombre: str):
    """«JUAN CARLOS PÉREZ GÓMEZ» → «PÉREZ GÓMEZ»; «Ana Luisa Martínez de la Cruz» → «Martínez de la Cruz»:
    así «la señora Martínez de la Cruz» se reconoce como la misma persona. None si el nombre es corto."""
    partes = nombre.split()
    reales = [i for i, p in enumerate(partes) if p.lower() not in _CONECTORES]
    if len(reales) < 3:
        return None
    desde = reales[2] if len(reales) >= 4 else reales[1]
    resto = " ".join(partes[desde:])
    return resto if len([p for p in resto.split() if p.lower() not in _CONECTORES]) >= 2 else None


def _personas(texto: str) -> list:
    """Los nombres de personas que se reconocen por lo que va antes o después, en el orden en que aparecen."""
    hallados = {}
    for m in re.finditer(_NOMBRE, texto):
        raw = m.group(0)
        # el patrón puede comerse una palabra de más al principio («Contra JUAN PÉREZ»): se prueba recortando
        partes = raw.split()
        # dónde empieza cada palabra dentro del match: entre ellas puede haber varios espacios o un salto de línea
        posiciones = [w.start() for w in re.finditer(r"\S+", raw)]
        for i in range(0, min(3, len(partes) - 1)):
            candidato = " ".join(partes[i:])
            inicio = m.start() + posiciones[i]
            antes = texto[max(0, inicio - 60):inicio]
            despues = texto[m.end():m.end() + 80]
            if _es_nombre(candidato) and (_DESPUES.match(despues) or _ANTES.search(antes)):
                hallados.setdefault(candidato, inicio)
                break
    return sorted(hallados, key=hallados.get)


def quitar_datos_caso(texto: str) -> tuple:
    """(texto con los datos cambiados por datos por llenar, mapa {"PERSONA 1": "Juan Pérez", …},
    cuántos de cada tipo). Cada persona o dato distinto lleva su número y se usa el mismo en todo el texto."""
    mapa, cuenta = {}, {}

    def nuevo(tipo: str, valor: str) -> str:
        for clave, v in mapa.items():
            if clave.startswith(tipo + " ") and _sin_tildes(v) == _sin_tildes(valor):
                return clave
        cuenta[tipo] = cuenta.get(tipo, 0) + 1
        clave = f"{tipo} {cuenta[tipo]}"
        mapa[clave] = valor
        return clave

    # domicilios primero: tienen nombres de calles que no son personas
    texto = _DOMICILIO.sub(lambda m: f"{m.group(1)} [{nuevo('DOMICILIO', m.group(2).strip())}]", texto)
    for tipo, patron in _OTROS:
        texto = patron.sub(lambda m: m.group(0).replace(m.group(m.lastindex or 0), f"[{nuevo(tipo, m.group(m.lastindex or 0))}]"),
                           texto)
    # cada persona con su número, en el orden en que aparece; los apellidos solos son la misma persona
    formas = []   # (cómo aparece, clave)
    for nombre in _personas(texto):
        dueno = next((c for f, c in formas if _sin_tildes(nombre) in _sin_tildes(f)), None)
        clave = dueno or nuevo("PERSONA", nombre)
        formas.append((nombre, clave))
        apellidos = _apellidos(nombre)
        if apellidos and not dueno:
            formas.append((apellidos, clave))
    # se reemplaza de la forma más larga a la más corta, en cualquier forma: JUAN PÉREZ o Juan Pérez
    for forma, clave in sorted(formas, key=lambda x: len(x[0]), reverse=True):
        patron = r"\s+".join(re.escape(p) for p in forma.split())
        texto = re.sub(rf"(?<![\w\[]){patron}(?![\w\]])", f"[{clave}]", texto, flags=re.I)
    return texto, mapa, cuenta


# ── Leer el documento que sube el abogado ──────────────────────────────────────

def leer(contenido: bytes, nombre: str) -> str:
    """El texto del PDF o del Word. ValueError con un mensaje para el abogado si no se puede leer."""
    ext = Path(nombre).suffix.lower()
    if ext == ".docx":
        try:
            texto = modelos.de_word(contenido)
        except Exception:
            raise ValueError(f"«{nombre}» no se pudo leer. Verifique que sea un Word válido.")
    elif ext == ".pdf":
        from jurisprudencia.procesar import extraer_paginas, DocumentoSinTexto
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "documento.pdf"
            ruta.write_bytes(contenido)
            try:
                paginas = extraer_paginas(str(ruta))
            except DocumentoSinTexto:
                raise ValueError(f"«{nombre}» es un PDF escaneado (una foto de las páginas): no tiene texto que "
                                 "se pueda leer. Súbalo en Word o en un PDF digital.")
            except Exception:
                raise ValueError(f"«{nombre}» no se pudo leer. Verifique que sea un PDF válido.")
        texto = "\n\n".join(t.strip() for _, t in paginas if t.strip())
    else:
        raise ValueError(f"«{nombre}»: suba el documento en PDF o en Word (.docx).")
    texto = re.sub(r"[ \t]+", " ", texto).strip()
    if len(texto) < 200:
        raise ValueError(f"«{nombre}» casi no tiene texto.")
    return texto[:MAX_CARACTERES]


def para_ia(texto: str) -> str:
    """Lo que se le manda a la IA para analizar: todo si cabe; si no, el principio (partes y hechos) y el final
    (las conclusiones o el dispositivo de la sentencia)."""
    if len(texto) <= MAX_PARA_IA:
        return texto
    mitad = MAX_PARA_IA // 2
    return texto[:mitad] + "\n\n[…se omite la parte del medio del documento…]\n\n" + texto[-mitad:]


def elegir_modelo(tipo: str, analisis: str, propios: list = (), materia: str = "") -> dict | None:
    """El modelo de ese tipo que más se parece al caso, de la misma materia si hay; None si no hay modelos
    de ese tipo."""
    t = TIPOS[tipo]
    if not t["grupos"]:
        return None
    def del_tipo(m):
        nombre = _sin_tildes(m["nombre"])
        return any(d in nombre for d in t["debe"]) and not any(n in nombre for n in t["no"])

    candidatos = [m for m in modelos.sugerir(f"{t['palabras']} {analisis}", maximo=10, propios=propios)
                  if (m.get("grupo") in t["grupos"] or m.get("propio") or m.get("oficina")) and del_tipo(m)]
    # un modelo de otra materia (laboral para un caso civil) solo si no hay ninguno de la misma
    materia = _sin_tildes(materia)
    if materia:
        de_la_materia = [m for m in candidatos if m.get("materia") and m["materia"] in materia]
        if de_la_materia:
            return de_la_materia[0]
        de_la_materia = [m for m in modelos.lista() if m["grupo"] in t["grupos"] and m["materia"] in materia
                         and del_tipo(m)]
        if de_la_materia:
            return de_la_materia[0]
    if candidatos:
        return candidatos[0]
    # nada parecido al caso: el primero de ese tipo, de cualquier materia, como formato
    return next((m for m in modelos.lista() if m["grupo"] in t["grupos"] and del_tipo(m)), None)


def pedido(tipo: str, resumen: str, indicaciones: str = "", con_modelo: bool = False) -> str:
    """Lo que se le pide a la IA para redactar el escrito a partir del análisis del documento."""
    t = TIPOS[tipo]
    return (
        f"Redacte {t['pedido']}. Devuelva el escrito completo en \"escrito\".\n"
        + ("El escrito actual es un MODELO: úselo como formato (estructura, estilo y fórmulas), pero cambie todo su "
           "contenido al caso. Donde el modelo tenga datos por llenar de las partes ([NOMBRE DE SU CLIENTE]…), "
           "ponga la marca del documento si es la misma persona (por ejemplo [PERSONA 2]).\n" if con_modelo else "")
        + "El modelo puede ser de otra materia o de otro tribunal: el tribunal al que va dirigido, la materia y las "
          "normas salen del caso, no del modelo (por ejemplo, para apelar una sentencia civil de primera instancia, "
          "la Corte de Apelación Civil que corresponda). Cada conclusión tiene que favorecer a nuestro cliente: las "
          "costas, por ejemplo, se piden contra la otra parte.\n"
        + "NO INVENTE HECHOS: afirme solo lo que dice el análisis del documento. Si un argumento depende de algo que "
          "no consta (una cláusula del contrato, un pago, una fecha de notificación, un plazo), escríbalo como algo "
          "por verificar entre corchetes y en mayúsculas, por ejemplo [VERIFICAR: SI EL CONTRATO TIENE CLÁUSULA DE "
          "GRACIA], o no lo use. Los puntos del análisis que empiezan con «Verificar:» van así, nunca como hechos. "
          "Los artículos y sentencias, SOLO de las fuentes: si el que hace falta no está, no lo cite de memoria; "
          "deje el argumento sin el artículo y dígalo en el mensaje.\n"
        + "Las marcas [PERSONA 1], [CÉDULA 1], [DOMICILIO 1]… vienen del documento: cópielas exactamente así "
          "donde vaya ese dato y nunca les ponga un nombre ni invente marcas con números que no están; para un "
          "dato que falta, use una descripción en mayúsculas, por ejemplo [CÉDULA DEL RECURRENTE].\n\n"
        f"Análisis del documento de la otra parte:\n{resumen}"
        + (f"\n\nIndicaciones del abogado: {indicaciones}" if indicaciones else "")
    )


# ── «Hacerlo yo mismo»: sin documento, con las respuestas del abogado ────────────
# Lo que es único de cada caso, según el tipo de escrito. Los nombres y cédulas NO se preguntan: van como
# datos por llenar ([NOMBRE DEL DEMANDANTE]…) y se llenan al descargar. Si el abogado los escribe en una
# respuesta, se quitan igual que en el documento (quitar_datos_caso) antes de mandarlo a la IA.
PREGUNTAS = {
    "demanda": [
        {"clave": "tribunal", "pregunta": "¿A qué tribunal va dirigida?",
         "ayuda": "Por ejemplo: Cámara Civil y Comercial del Juzgado de Primera Instancia del Distrito Nacional."},
        {"clave": "objeto", "pregunta": "¿Qué se demanda?", "requerida": True,
         "ayuda": "Cobro de pesos, desalojo, rescisión de contrato, daños y perjuicios, nulidad…"},
        {"clave": "hechos", "pregunta": "Los hechos: qué pasó, cuándo y dónde", "requerida": True,
         "ayuda": "Cuente el caso en orden, con las fechas y los montos. No escriba nombres ni cédulas."},
        {"clave": "motivos", "pregunta": "Los motivos: por qué su cliente tiene derecho", "requerida": True,
         "ayuda": "Qué obligación se incumplió o qué derecho se violó. Papiniano busca los artículos en la biblioteca."},
        {"clave": "pide", "pregunta": "¿Qué le pide al tribunal?", "requerida": True,
         "ayuda": "Las conclusiones: que se condene a pagar tanto, que se ordene el desalojo, las costas…"},
        {"clave": "pruebas", "pregunta": "Pruebas y documentos que tiene",
         "ayuda": "Contrato, recibos, actos de alguacil, certificaciones…"},
    ],
    "defensa": [
        {"clave": "tribunal", "pregunta": "Tribunal y número de expediente",
         "ayuda": "Donde está la demanda contra su cliente."},
        {"clave": "contraria", "pregunta": "¿Qué pide la otra parte?", "requerida": True,
         "ayuda": "Lo que reclama la demanda o el recurso."},
        {"clave": "hechos", "pregunta": "Su versión de los hechos", "requerida": True,
         "ayuda": "Qué pasó según su cliente, con fechas. No escriba nombres ni cédulas."},
        {"clave": "motivos", "pregunta": "Por qué debe rechazarse", "requerida": True,
         "ayuda": "Excepciones, inadmisibilidades (prescripción, falta de calidad…) y argumentos de fondo."},
        {"clave": "pide", "pregunta": "¿Qué le pide al tribunal?", "requerida": True,
         "ayuda": "Que se declare inadmisible, que se rechace, las costas…"},
        {"clave": "pruebas", "pregunta": "Pruebas y documentos que tiene"},
    ],
    "apelacion": [
        {"clave": "sentencia", "pregunta": "La sentencia que apela: tribunal, número y fecha", "requerida": True},
        {"clave": "notificacion", "pregunta": "¿Cuándo le notificaron la sentencia?",
         "ayuda": "Para el plazo del recurso."},
        {"clave": "decidio", "pregunta": "¿Qué decidió la sentencia?", "requerida": True},
        {"clave": "motivos", "pregunta": "¿Por qué está mal? (los agravios)", "requerida": True,
         "ayuda": "Qué hechos o pruebas valoró mal, qué normas aplicó mal, qué no contestó…"},
        {"clave": "pide", "pregunta": "¿Qué le pide a la corte?", "requerida": True,
         "ayuda": "Que revoque la sentencia y acoja la demanda, que la rechace, las costas…"},
    ],
    "casacion": [
        {"clave": "sentencia", "pregunta": "La sentencia que recurre: tribunal, número y fecha", "requerida": True},
        {"clave": "notificacion", "pregunta": "¿Cuándo le notificaron la sentencia?",
         "ayuda": "Para el plazo del recurso."},
        {"clave": "decidio", "pregunta": "¿Qué decidió la sentencia?", "requerida": True},
        {"clave": "motivos", "pregunta": "Los medios de casación", "requerida": True,
         "ayuda": "Violación de la ley, falta de base legal, desnaturalización de los hechos, falta de motivos…"},
        {"clave": "pide", "pregunta": "¿Qué le pide a la Suprema Corte?", "requerida": True,
         "ayuda": "Que case la sentencia y envíe el asunto a otro tribunal, las costas…"},
    ],
    "constitucional": [
        {"clave": "sentencia", "pregunta": "La sentencia firme que recurre: tribunal, número y fecha",
         "requerida": True},
        {"clave": "notificacion", "pregunta": "¿Cuándo le notificaron la sentencia?"},
        {"clave": "decidio", "pregunta": "¿Qué decidió la sentencia?", "requerida": True},
        {"clave": "motivos", "pregunta": "¿Qué derechos fundamentales se violaron y cómo?", "requerida": True,
         "ayuda": "Tutela judicial efectiva, debido proceso, derecho de propiedad…"},
        {"clave": "trascendencia", "pregunta": "¿Por qué tiene especial trascendencia o relevancia constitucional?"},
        {"clave": "pide", "pregunta": "¿Qué le pide al Tribunal Constitucional?", "requerida": True},
    ],
}

_REGLAS = (
    "Cada conclusión tiene que favorecer a nuestro cliente: las costas, por ejemplo, se piden contra la otra "
    "parte.\n"
    "NO INVENTE HECHOS: afirme solo lo que dice el abogado. Si un argumento depende de algo que no dijo (una "
    "cláusula, un pago, una fecha, un plazo), escríbalo como algo por verificar entre corchetes y en mayúsculas, "
    "por ejemplo [VERIFICAR: FECHA DE NOTIFICACIÓN DE LA SENTENCIA], o no lo use. Los artículos y sentencias, "
    "SOLO de las fuentes: si el que hace falta no está, no lo cite de memoria; deje el argumento sin el "
    "artículo y dígalo en el mensaje.\n"
    "Los nombres, cédulas y domicilios de las partes no los tiene: póngalos como datos por llenar "
    "([NOMBRE DEL DEMANDANTE], [CÉDULA DEL DEMANDANTE]…), y las marcas [PERSONA 1], [CÉDULA 1]… que aparezcan "
    "cópielas exactamente así.\n\n"
)


def preguntas(tipo: str) -> list:
    return [{"requerida": False, "ayuda": "", **p} for p in PREGUNTAS[tipo]]


def respuestas_sin_datos(tipo: str, respuestas: dict) -> tuple:
    """(las respuestas como texto, sin los datos de las personas, mapa). Se quitan juntas, así la misma
    persona lleva el mismo número en todas."""
    partes = []
    for p in PREGUNTAS[tipo]:
        r = str(respuestas.get(p["clave"]) or "").strip()[:4000]
        if r:
            partes.append(f"{p['pregunta']}\n{r}")
    texto, mapa, _ = quitar_datos_caso("\n\n".join(partes))
    return texto, mapa


def faltan(tipo: str, respuestas: dict) -> list:
    """Las preguntas obligatorias sin responder."""
    return [p["pregunta"] for p in PREGUNTAS[tipo]
            if p.get("requerida") and len(str(respuestas.get(p["clave"]) or "").strip()) < 3]


def pedido_propio(tipo: str, respuestas: str, con_modelo: bool = False) -> str:
    """Lo que se le pide a la IA para redactar con lo que contestó el abogado."""
    t = TIPOS[tipo]
    return (
        f"Redacte {t['nombre'].lower()} a favor de nuestro cliente con la información que dio el abogado. "
        "Devuelva el escrito completo en \"escrito\".\n"
        + ("El escrito actual es un MODELO: úselo como formato (estructura, estilo y fórmulas), pero cambie todo "
           "su contenido al caso. El tribunal, la materia y las normas salen de las respuestas, no del modelo.\n"
           if con_modelo else "")
        + _REGLAS
        + f"Lo que dijo el abogado:\n{respuestas}"
    )


def modelos_del_tipo(tipo: str) -> list:
    """Los modelos de todos que sirven para ese tipo de escrito, para que el abogado elija uno."""
    t = TIPOS[tipo]
    if not t["grupos"]:
        return []

    def del_tipo(m):
        nombre = _sin_tildes(m["nombre"])
        return any(d in nombre for d in t["debe"]) and not any(n in nombre for n in t["no"])

    return [{"clave": m["clave"], "nombre": m["nombre"], "materia": m["materia"]}
            for m in modelos.lista() if m["grupo"] in t["grupos"] and del_tipo(m)]
