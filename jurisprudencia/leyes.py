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
_ARTICULO = re.compile(r"(?<![“\"])\b(?:Art[íi]culo|ARTÍCULO|Art)\.?\s*(\d{1,3})(?:\s*[\.\-–:])+\s*(?=[A-ZÁÉÍÓÚÑ(])")
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
    hasta la primera que cumple `hasta` (sin incluirla)."""
    lineas, dentro = [], False
    for num, texto in paginas:
        for linea in texto.splitlines():
            if not dentro:
                dentro = bool(re.search(desde, linea))
                continue
            if re.search(hasta, linea, re.I):
                return lineas
            lineas.append((num, linea))
    return lineas


def articulos(paginas: list, norma: dict) -> list:
    """[{"articulo", "nombre", "pagina", "texto"}] en orden. Un artículo empieza solo si su
    número sigue al anterior (así no se cuelan los números que aparecen dentro del texto)."""
    texto, inicios = "", []   # inicios: (posición en el texto, página)
    for num, linea in _lineas(paginas, norma["desde"], norma["hasta"]):
        if linea.strip() and not (_CABECERAS.match(linea) or _ENCABEZADO.match(linea)):
            inicios.append((len(texto), num))
            texto += linea.strip() + " "
    cortes = []
    for m in _ARTICULO.finditer(texto):
        n, ultimo = int(m.group(1)), cortes[-1][1] if cortes else 0
        if ultimo < n <= ultimo + 3:
            cortes.append((m.start(), n))
    lista = []
    for i, (pos, n) in enumerate(cortes):
        fin = cortes[i + 1][0] if i + 1 < len(cortes) else len(texto)
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
_CAPITULO_COMENTADO = re.compile(r"^\s*(?:ART[ÍI]CULOS|PRINCIPIOS) COMENTADOS\b")
# cabeceras del libro: el título repetido, "Principios generales", "CAPÍTULO ÚNICO", el número de página
_CABECERAS_OBRA = re.compile(r"^\s*(?:La Ley 108-05 de Registro Inmobiliario comentada.*|Principios generales"
                             r"|CAP[ÍI]TULO [ÚU]NICO|T[ÍI]TULO [IVXLC]+\..*|-?\d{1,3}-?)\s*$", re.I)


def comentarios(paginas: list, obra: dict) -> list:
    """El comentario de cada artículo, en orden: [{"articulo", "nombre", "pagina", "texto"}].
    Lo que va antes del artículo 1 (los principios generales) sale como artículo 0.
    Se saltan las listas de referencias bibliográficas del final de cada capítulo."""
    texto, inicios, en_referencias = "", [], False
    for num, pagina in paginas:
        if num < obra["desde_pagina"]:
            continue
        for linea in pagina.splitlines():
            if _REFERENCIAS.match(linea):
                en_referencias = True
            elif _CAPITULO_COMENTADO.match(linea):
                en_referencias = False
                continue
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


def guardar_norma(conn, norma: dict, lista: list) -> int:
    """Reemplaza los artículos de la norma (se puede volver a cargar sin duplicar)."""
    from .procesar import guardar
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documentos WHERE origen = 'ley' AND fuente_url = %s", (norma["url"],))
    conn.commit()
    for a in lista:
        paginas = [(a["pagina"], a["texto"])]
        ficha = {"numero": numero(norma, a["articulo"]), "sala": norma["nombre"], "materia": MATERIA,
                 "fecha": norma["fecha"]}
        guardar(conn, ficha, fragmentar(paginas), "ley", titulo=a["nombre"], fuente_url=norma["url"],
                pagina=a["pagina"])
    return len(lista)


# "art. 81 de la Ley 108-05", "artículo 12 del Reglamento de Mensuras"
_CITA = re.compile(r"\bart(?:[íi]culo|s?\.)?\s*(\d{1,3})\b(?=(.{0,80}))", re.I)


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
