"""
Leyes y reglamentos: cada artículo se guarda como un documento público (origen 'ley'),
para que el chat pueda citar "Ley 108-05, art. 81" junto a las sentencias.

Son textos oficiales: la Ley 65-00, art. 41, permite reutilizarlos citando la fuente.

Libros de leyes comentadas (OBRAS, origen 'doctrina'): el comentario de cada artículo es un
documento con el mismo número que el artículo, así sale junto a la ley. Tienen autores y
licencia (CC BY-NC-ND): siempre se citan autores y obra, en pantalla solo salen extractos
cortos, y se quitan con `python cargar_leyes.py --quitar-comentarios`.

Cada norma dice dónde empieza y dónde termina su articulado dentro del PDF, porque los
PDFs traen antes un índice con los mismos artículos y después otras cosas (el PDF de la
Ley 108-05 es una recopilación de 2011 que también trae la Ley 51-07 y los reglamentos
viejos de 2009, que ya fueron reemplazados por los de 2022).
"""

import re

from .procesar import extraer_paginas, fragmentar

# corto: cómo se cita (va en documentos.numero junto al artículo)
# alias: cómo la nombra un abogado en una pregunta ("art. 12 del reglamento de mensuras")
NORMAS = [
    {"corto": "Ley 108-05",
     "nombre": "Ley núm. 108-05 de Registro Inmobiliario (modificada por la Ley núm. 51-07)",
     "fecha": "23 de marzo de 2005",
     "url": "https://ri.gob.do/wp-content/uploads/Download/51-07.pdf",
     "desde": r"HA DADO LA SIGUIENTE LEY", "hasta": r"^DADA en la Sala",
     "alias": r"ley\s*(?:n[úu]m\.?|no\.?)?\s*108-0?5|ley de registro inmobiliario|ley de tierras"},
    {"corto": "Reglamento de los Tribunales",
     "nombre": "Reglamento General de los Tribunales de la Jurisdicción Inmobiliaria (Res. núm. 787-2022)",
     "fecha": "27 de octubre de 2022",
     "url": "https://transparencia.poderjudicial.gob.do/documentos/PDF/resoluciones_pj/RPJ_resolucionnum7872022v2.pdf",
     "desde": r"RESUELVE", "hasta": r"^SEGUNDO:\s*ORDENA",
     "alias": r"787-2022|reglamento (?:general )?de (?:los )?tribunales"},
    {"corto": "Reglamento de Registro de Títulos",
     "nombre": "Reglamento General de Registro de Títulos (Res. núm. 788-2022)",
     "fecha": "27 de octubre de 2022",
     "url": "https://transparencia.poderjudicial.gob.do/documentos/PDF/resoluciones_pj/RPJ_resolucion_num_788_2022v2.pdf",
     "desde": r"RESUELVE", "hasta": r"^SEGUNDO:\s*ORDENA",
     "alias": r"788-2022|reglamento (?:general )?de registros? de t[íi]tulos"},
    {"corto": "Reglamento de Mensuras",
     "nombre": "Reglamento General de Mensuras Catastrales (Res. núm. 789-2022)",
     "fecha": "27 de octubre de 2022",
     "url": "https://transparencia.poderjudicial.gob.do/documentos/PDF/resoluciones_pj/RPJ_resolucion_num_789_2022v2.pdf",
     "desde": r"RESUELVE", "hasta": r"^SEGUNDO:\s*ORDENA",
     "alias": r"789-2022|reglamento (?:general )?de mensuras?(?: catastrales)?"},
    {"corto": "Reglamento de Regularización y Deslinde",
     "nombre": "Reglamento para la Regularización Parcelaria y el Deslinde (Res. núm. 790-2022)",
     "fecha": "27 de octubre de 2022",
     "url": "https://transparencia.poderjudicial.gob.do/documentos/PDF/resoluciones_pj/RPJ_resolucion_num_790_2022v2.pdf",
     "desde": r"RESUELVE", "hasta": r"^SEGUNDO:\s*ORDENA",
     "alias": r"790-2022|reglamento (?:para la |de )?(?:regularizaci[óo]n parcelaria|deslinde)"},
]
MATERIA = "Inmobiliario"

# Las que no tienen un PDF oficial a mano van en la carpeta leyes/ del repositorio (son textos
# oficiales, libres): "archivo" se usa al cargar y "url" (jsDelivr) para abrir la página en la app.
# Sin "desde"/"hasta" se toma todo el PDF: el índice no trae encabezados de artículo y lo que va
# después del último artículo se corta en "DADA en la Sala…" (_FIN_DE_LEY).
# El PDF de la Ley 64-00 (Medio Ambiente) no trae los artículos 79 a 115 y tiene páginas repetidas.
# jsDelivr sirve los archivos del repo como application/pdf y acepta "Range" (raw.githubusercontent no)
_REPO = "https://cdn.jsdelivr.net/gh/yeisondev001/sistema-de-solicitudes-legales@master/"
for _archivo, _corto, _nombre, _materia, _alias in [
    ("leyes/codigo-civil.pdf", "Código Civil", "Código Civil de la República Dominicana", "Civil",
     r"c[óo]digo civil"),
    ("leyes/codigo-procedimiento-civil.pdf", "Código de Procedimiento Civil",
     "Código de Procedimiento Civil de la República Dominicana", "Civil", r"(?:c[óo]digo de )?procedimiento civil"),
    ("leyes/codigo-de-trabajo.pdf", "Código de Trabajo", "Código de Trabajo de la República Dominicana (Ley núm. 16-92)",
     "Laboral", r"c[óo]digo de(?:l)? trabajo|ley\s*(?:n[úu]m\.?|no\.?)?\s*16-92"),
    ("leyes/ley-189-11.pdf", "Ley 189-11",
     "Ley núm. 189-11 para el Desarrollo del Mercado Hipotecario y el Fideicomiso", "Inmobiliario",
     r"189-11|ley de fideicomiso|mercado hipotecario"),
    ("leyes/ley-338-21.pdf", "Ley 338-21", "Ley núm. 338-21, que modifica los artículos 129 y 131 de la Ley núm. 189-11",
     "Inmobiliario", r"338-21"),
    ("leyes/ley-82-25.pdf", "Ley 82-25", "Ley núm. 82-25 sobre Bien de Familia", "Inmobiliario",
     r"82-25|bien de familia"),
    ("leyes/ley-5038.pdf", "Ley 5038", "Ley núm. 5038 sobre Condominios (1958)", "Inmobiliario",
     r"\b5038\b|ley de condominios?"),
    ("leyes/ley-675.pdf", "Ley 675", "Ley núm. 675 sobre Urbanización, Ornato Público y Construcciones", "Inmobiliario",
     r"ley\s*(?:n[úu]m\.?|no\.?)?\s*675\b|ornato p[úu]blico"),
    ("leyes/ley-176-07.pdf", "Ley 176-07", "Ley núm. 176-07 del Distrito Nacional y los Municipios", "Municipal",
     r"176-07|ley de (?:los )?municipios"),
    ("leyes/ley-202-04.pdf", "Ley 202-04", "Ley núm. 202-04, Sectorial de Áreas Protegidas", "Ambiental",
     r"202-04|[áa]reas protegidas"),
    ("leyes/ley-64-00.pdf", "Ley 64-00", "Ley núm. 64-00 General sobre Medio Ambiente y Recursos Naturales", "Ambiental",
     r"64-00|ley (?:general )?(?:de|sobre) medio ambiente"),
    ("leyes/res-517-2007.pdf", "Reglamento de Constancias Anotadas",
     "Reglamento para el Control y Reducción de Constancias Anotadas (Res. núm. 517-2007)", "Inmobiliario",
     r"517-2007|constancias anotadas"),
    ("leyes/res-82-2025.pdf", "Res. 82-2025",
     "Resolución núm. 82-2025, que modifica el Reglamento para la Regularización Parcelaria y el Deslinde",
     "Inmobiliario", r"82-2025"),
    ("leyes/res-008-2020.pdf", "Reglamento del Registro Inmobiliario (CPJ)",
     "Reglamento de Registro Inmobiliario del Consejo del Poder Judicial (Res. núm. 008-2020)", "Inmobiliario",
     r"008-2020"),
    ("leyes/codigo-penal-anterior.pdf", "Código Penal (derogado)",
     "Código Penal de la República Dominicana de 1884, derogado por la Ley núm. 74-25 (rige para hechos anteriores a su "
     "entrada en vigor, agosto de 2026)", "Penal", r"c[óo]digo penal (?:anterior|derogado|viejo|de 1884)"),
]:
    NORMAS.append({"corto": _corto, "nombre": _nombre, "fecha": "", "materia": _materia, "alias": _alias,
                   "archivo": _archivo, "url": _REPO + _archivo})
for _c in ("Ley 64-00", "Código Penal (derogado)"):   # páginas fuera de orden o artículos derogados (362-366)
    NORMAS[[n["corto"] for n in NORMAS].index(_c)]["orden_libre"] = True
# después del art. 738 el PDF del Código de Trabajo sigue con notas, índice y otras normas
NORMAS[[n["corto"] for n in NORMAS].index("Código de Trabajo")]["fin"] = r"\b\d{1,2}\.- Con posterioridad a la promulgaci"

# libros de leyes comentadas; desde_pagina: donde termina el índice y empieza el comentario
OBRAS = [
    {"corto": "Ley 108-05",
     "nombre": "La Ley 108-05 de Registro Inmobiliario comentada por Registradores de Títulos "
               "(Escuela Nacional de la Judicatura, 2022)",
     "fecha": "2022",
     "url": "https://ri.gob.do/wp-content/uploads/2023/10/Libro-Ley-108-05-de-registro-inmobiliario.pdf",
     "desde_pagina": 11},
]

# "Art. 81.- Plazo…" (Ley 108-05) o "Artículo 81. Plazo…" (reglamentos). pdftotext junta los
# párrafos, así que pueden venir a mitad de línea; se distinguen de las referencias ("el artículo 5
# de la ley") por la mayúscula, el punto después del número y la mayúscula que sigue.
# Los artículos de otras leyes que se citan entre comillas ("“Art. 1.- …") no cuentan.
# Los códigos llegan a 2.280 artículos; algunas leyes escriben "ARTICULO" sin tilde o "Art. 1o.-".
_ARTICULO = re.compile(r"(?<![“\"«])\b(?:Art[íi]culo|ART[ÍI]CULO|Art|ART)\.?\s*(\d{1,4})\s*(?:[ºo°]\.?)?"
                       r"(?:\s*[\.\-–:])+\s*(?=[A-ZÁÉÍÓÚÑ(“\"])")
# lo que va después del último artículo (firmas del Congreso y del Poder Ejecutivo, anexos)
_FIN_DE_LEY = re.compile(r"\bDADA en (?:la Sala|Santo Domingo)\b")
# títulos, capítulos y secciones: van en su propia línea y se quitan del texto del artículo
_ENCABEZADO = re.compile(r"^\s*(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|LIBRO)\s+[IVXLC\d]+\b.*$", re.M | re.I)
# cabeceras y pies que se repiten en cada página
_CABECERAS = re.compile(
    r"^\s*(?:PODER JUDICIAL|REP[ÚU]BLICA DOMINICANA|SUPREMA CORTE DE JUSTICIA|\d{1,3}"
    r"|\|?\s*\d{0,3}\s*Resoluci[óo]n n[úu]m\. \d+-2022,.*"
    r"|Ley No\. 108-05.*|Ley No\. 51-07|Reglamento General de Registros de T[íi]tulos)\s*$", re.M | re.I)
# lo que va después del número y antes del primer punto es el nombre del artículo
_NOMBRE = re.compile(r"^(?:\((?:Modificado|Agregado)[^)]*\)\s*)?([^.]{3,160}?)\.\s")


def _lineas(paginas: list, desde: str, hasta: str) -> list:
    """[(página, línea)] del articulado: desde la primera línea que cumple `desde`
    hasta la primera que cumple `hasta` (sin incluirla). Sin `desde`, desde el principio."""
    lineas, dentro = [], not desde
    for num, texto in paginas:
        for linea in texto.splitlines():
            if not dentro:
                dentro = bool(re.search(desde, linea))
                continue
            if hasta and re.search(hasta, linea, re.I):
                return lineas
            lineas.append((num, linea))
    return lineas


def articulos(paginas: list, norma: dict) -> list:
    """[{"articulo", "nombre", "pagina", "texto"}] en orden. Un artículo empieza solo si su
    número sigue al anterior (así no se cuelan los números que aparecen dentro del texto)."""
    texto, inicios = "", []   # inicios: (posición en el texto, página)
    for num, linea in _lineas(paginas, norma.get("desde"), norma.get("hasta")):
        if linea.strip() and not (_CABECERAS.match(linea) or _ENCABEZADO.match(linea)):
            inicios.append((len(texto), num))
            texto += linea.strip() + " "
    cortes = []   # (posición, número; 0 = página repetida que se descarta)
    for m in _ARTICULO.finditer(texto):
        n, ultimo = int(m.group(1)), max((c[1] for c in cortes), default=0)
        if norma.get("orden_libre"):
            # PDF con páginas fuera de orden o repetidas: vale cualquier número la primera vez
            cortes.append((m.start(), 0 if any(c[1] == n for c in cortes) else n))
        elif ultimo < n <= ultimo + 3:
            cortes.append((m.start(), n))
    lista = []
    for i, (pos, n) in enumerate(cortes):
        if not n:
            continue
        fin = cortes[i + 1][0] if i + 1 < len(cortes) else len(texto)
        cortes_fin = [m.start() for patron in (_FIN_DE_LEY, re.compile(norma.get("fin") or r"(?!)"))
                      for m in [patron.search(texto, pos, fin)] if m]
        fin = min(cortes_fin, default=fin)
        pagina = next(p for desde, p in reversed(inicios) if desde <= pos)
        lista.append({"articulo": n, "pagina": pagina, "texto": re.sub(r"\s+", " ", texto[pos:fin]).strip()})
    for a in lista:
        texto = a["texto"]
        cuerpo = _ARTICULO.sub("", texto, count=1)
        m = _NOMBRE.match(cuerpo)
        a["nombre"] = m.group(1).strip() if m else ""
        a["texto"] = texto
    return lista


_REFERENCIAS = re.compile(r"^\s*REFERENCIAS\s*$")
# el pdftotext de Linux (GitHub Actions) no siempre deja estos títulos solos en su línea
_CAPITULO_COMENTADO = re.compile(r"(?:ART[ÍI]CULOS|PRINCIPIOS)\s+COMENTADOS\b", re.I)
_EMPIEZA_COMENTARIO = re.compile(r"^\s*(?:Art[íi]culo\s+\d{1,3}\s*\.\s*-|PRINCIPIO\s+[IVX]+\b)")
# cabeceras del libro: el título repetido, "Principios generales", "CAPÍTULO ÚNICO", el número de página
_CABECERAS_OBRA = re.compile(r"^\s*(?:La Ley 108-05 de Registro Inmobiliario comentada.*|Principios generales"
                             r"|CAP[ÍI]TULO [ÚU]NICO|T[ÍI]TULO [IVXLC]+\..*|-?\d{1,3}-?)\s*$", re.I)


def comentarios(paginas: list, obra: dict) -> list:
    """El comentario de cada artículo, en orden: [{"articulo", "nombre", "pagina", "texto"}].
    Lo que va antes del artículo 1 (los principios generales) sale como artículo 0.
    Se saltan las listas de referencias bibliográficas del final de cada capítulo."""
    import unicodedata
    texto, inicios, en_referencias = "", [], False
    for num, pagina in paginas:
        if num < obra["desde_pagina"]:
            continue
        for linea in unicodedata.normalize("NFC", pagina).splitlines():
            if _REFERENCIAS.match(linea):
                en_referencias = True
            elif _CAPITULO_COMENTADO.search(linea):
                en_referencias = False
                continue
            elif _EMPIEZA_COMENTARIO.match(linea):
                en_referencias = False
            if (en_referencias or not linea.strip() or _CABECERAS_OBRA.match(linea)
                    or _ENCABEZADO.match(linea) or re.match(r"^\s*Por [A-ZÁÉÍÓÚ]", linea)):
                continue
            inicios.append((len(texto), num))
            texto += linea.strip() + " "
    # el comentario cita otros artículos: solo cuenta el que sigue exactamente al anterior
    cortes = [(0, 0)]
    for m in _ARTICULO.finditer(texto):
        if int(m.group(1)) == cortes[-1][1] + 1:
            cortes.append((m.start(), int(m.group(1))))
    lista = []
    for i, (pos, n) in enumerate(cortes):
        fin = cortes[i + 1][0] if i + 1 < len(cortes) else len(texto)
        trozo = re.sub(r"\s+", " ", texto[pos:fin]).strip()
        if not trozo:
            continue
        # el texto de cada página, para que cada fragmento recuerde la suya
        por_pagina = {}
        for j, (desde, p) in enumerate(inicios):
            hasta = inicios[j + 1][0] if j + 1 < len(inicios) else len(texto)
            if hasta > pos and desde < fin:
                por_pagina[p] = por_pagina.get(p, "") + texto[max(desde, pos):min(hasta, fin)]
        m = _NOMBRE.match(_ARTICULO.sub("", trozo, count=1)) if n else None
        lista.append({"articulo": n, "nombre": m.group(1).strip() if m else ("Principios generales" if not n else ""),
                      "pagina": min(por_pagina), "texto": trozo, "paginas": sorted(por_pagina.items())})
    return lista


def guardar_obra(conn, obra: dict, lista: list) -> int:
    """Reemplaza los comentarios de la obra. Un comentario largo se parte en fragmentos que
    recuerdan su página, para que el enlace abra el libro donde corresponde."""
    from .procesar import guardar
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documentos WHERE origen = 'doctrina' AND fuente_url = %s", (obra["url"],))
        if cur.fetchone()[0] == len(lista):   # ya está igual: no se recalculan sus vectores
            return 0
        cur.execute("DELETE FROM documentos WHERE origen = 'doctrina' AND fuente_url = %s", (obra["url"],))
    conn.commit()
    for a in lista:
        ficha = {"numero": numero(obra, a["articulo"]) if a["articulo"] else f"{obra['corto']}, principios",
                 "sala": obra["nombre"], "materia": MATERIA, "fecha": obra["fecha"]}
        guardar(conn, ficha, fragmentar(a["paginas"]), "doctrina", titulo=a["nombre"],
                fuente_url=obra["url"], pagina=a["pagina"])
    return len(lista)


def quitar_obras(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documentos WHERE origen = 'doctrina'")
        n = cur.rowcount
    conn.commit()
    return n


def numero(norma: dict, articulo: int) -> str:
    """Cómo se cita: 'Ley 108-05, art. 81'."""
    return f"{norma['corto']}, art. {articulo}"


def leer(ruta: str, norma: dict) -> list:
    return articulos(extraer_paginas(ruta), norma)


def guardar_norma(conn, norma: dict, lista: list, forzar: bool = False) -> int:
    """Reemplaza los artículos de la norma (se puede volver a cargar sin duplicar). Si ya está
    con los mismos artículos no la toca, para no gastar neuronas recalculando sus vectores."""
    from .procesar import guardar
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documentos WHERE origen = 'ley' AND fuente_url = %s", (norma["url"],))
        if cur.fetchone()[0] == len(lista) and not forzar:
            return 0
        cur.execute("DELETE FROM documentos WHERE origen = 'ley' AND fuente_url = %s", (norma["url"],))
    conn.commit()
    for a in lista:
        paginas = [(a["pagina"], a["texto"])]
        ficha = {"numero": numero(norma, a["articulo"]), "sala": norma["nombre"],
                 "materia": norma.get("materia", MATERIA), "fecha": norma["fecha"]}
        guardar(conn, ficha, fragmentar(paginas), "ley", titulo=a["nombre"], fuente_url=norma["url"],
                pagina=a["pagina"])
    return len(lista)


# "art. 81 de la Ley 108-05", "artículo 12 del Reglamento de Mensuras"
_CITA = re.compile(r"\bart(?:[íi]culo|s?\.)?\s*(\d{1,4})\b(?=(.{0,80}))", re.I)


def citas(texto: str) -> list:
    """Números de artículo que trae una pregunta, en mayúsculas y sin tildes, para compararlos con
    upper(f_unaccent(documentos.numero)) (el upper() de Postgres puede no cambiar las vocales con tilde)."""
    salida = []
    for art, resto in _CITA.findall(texto):
        # la norma que se nombra más cerca del número ("art. 12 del reglamento de mensuras y art. 81 de la ley")
        nombradas = [(m.start(), norma) for norma in NORMAS for m in [re.search(norma["alias"], resto, re.I)] if m]
        if nombradas:
            cita = numero(min(nombradas, key=lambda x: x[0])[1], int(art)).upper()
            salida.append(cita.translate(str.maketrans("ÁÉÍÓÚÜ", "AEIOUU")))
    return list(dict.fromkeys(salida))
