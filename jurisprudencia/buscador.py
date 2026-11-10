"""
Búsqueda híbrida sobre los fragmentos:
  - por palabras (búsqueda de texto de PostgreSQL en español) y
  - por significado (vectores de Cloudflare guardados con pgvector).
Las dos listas se mezclan con RRF: lo que sale arriba en ambas queda primero.
Cada usuario busca en lo público (el Boletín Judicial, las leyes y los libros comentados) y en sus propios
documentos, en todas las bases a la vez (ver basedatos.bases()).
"""

import re

from . import basedatos, leyes, vectores

_PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-/]*")
RRF_K = 60               # constante habitual de RRF
CANDIDATOS = 200         # vecinos que se piden al índice binario antes de reordenar

_COLUMNAS = """f.id, f.pagina, f.texto, d.id AS documento_id, d.origen, d.titulo, d.numero,
               d.expediente, d.sala, d.materia, d.decision, d.fecha, d.fuente_url"""
_EXTRACTO = """ts_headline('spanish', f.texto, to_tsquery('spanish', f_unaccent(%(tq)s)),
               'MaxWords=45, MinWords=20, MaxFragments=2, FragmentDelimiter=" … "') AS extracto"""
_PERMISO = "(d.usuario_id IS NULL OR d.usuario_id = %(usuario)s)"


# números de sentencia o expediente: SCJ-TS-25-1451, 001-022-2025-SRES-00121, TC/0001/24…
_NUMERO = re.compile(r"\b(?=[\w/-]*\d)[0-9A-Z]+(?:[-/][0-9A-Z]+){2,}\b", re.I)
MAX_PALABRAS = 7
_SOLO_CITA = re.compile(r"\s*art(?:[íi]culo|s?\.)?\s*\d{1,4}\s+(?:del?|de la)\s+[^,;]{3,80}", re.I)
MAX_ARTICULOS = 3   # lugares que se guardan para artículos de ley y sus comentarios entre las fuentes
LEYES_CANDIDATOS = 12   # de la búsqueda solo en leyes: artículos que se consideran por palabras y por significado
_comunes = {}     # base -> (palabras, hora en que se leyeron)


def _tsquery(texto: str) -> str:
    """'litis derechos registrados' -> 'litis | derechos | registrados' (para resaltar el extracto)."""
    palabras = [p for p in _PALABRA.findall(texto) if len(p) > 2]
    return " | ".join(dict.fromkeys(palabras))


def _terminos_comunes(conn) -> set:
    """Palabras que salen en casi todas las sentencias de esa base (se recargan cada 6 horas)."""
    import time
    base = basedatos.clave(conn)
    lista, hora = _comunes.get(base, (None, 0.0))
    if lista is None or time.time() - hora > 6 * 3600:
        lista = {f["palabra"] for f in basedatos.filas(conn, "SELECT palabra FROM terminos_comunes")}
        _comunes[base] = (lista, time.time())
    return lista


def _consulta_minimo_dos(conn, texto: str):
    """Arma una consulta que pide al menos 2 de las palabras importantes de la búsqueda:
    'prescripción litis registrados' -> (prescripcion & litis) | (prescripcion & registr) | (litis & registr)."""
    from itertools import combinations
    filas = basedatos.filas(
        conn, "SELECT unnest(tsvector_to_array(to_tsvector('spanish', f_unaccent(%s)))) AS l", (texto,))
    comunes = _terminos_comunes(conn)
    lex = [f["l"] for f in filas if len(f["l"]) > 2 and f["l"] not in comunes][:MAX_PALABRAS]
    lex = ["'" + l.replace("'", "''") + "'" for l in lex]
    if len(lex) >= 2:
        return " | ".join(f"({a} & {b})" for a, b in combinations(lex, 2))
    return lex[0] if lex else None


def _por_palabras(conn, consultas: list, usuario_id: int, n: int, solo_leyes: bool = False) -> list:
    mejores = {}
    filtro = " AND d.origen IN ('ley', 'doctrina')" if solo_leyes else ""
    for q in consultas:
        tq = _consulta_minimo_dos(conn, q)
        if not tq:
            continue
        filas = basedatos.filas(
            conn,
            f"""SELECT {_COLUMNAS}, ts_rank_cd(f.tsv, to_tsquery('simple', %(q)s)) AS puntaje, {_EXTRACTO}
                FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
                WHERE f.tsv @@ to_tsquery('simple', %(q)s) AND {_PERMISO}{filtro}
                ORDER BY puntaje DESC LIMIT %(n)s""",
            {"q": tq, "tq": _tsquery(q) or "sentencia", "usuario": usuario_id, "n": n})
        for f in filas:
            if f["id"] not in mejores or f["puntaje"] > mejores[f["id"]]["puntaje"]:
                mejores[f["id"]] = f
    return sorted(mejores.values(), key=lambda f: f["puntaje"], reverse=True)


# antes de 2022 las sentencias se citan "núm. 10 del 27 de enero de 2021"
_NUMERO_VIEJO = re.compile(r"n[úu]m(?:ero)?\.?\s*(\d{1,4}),?\s+(?:del?\s+)?(\d{1,2})\s+de\s+([a-záéíóú]+)\s+del?\s+(\d{4})",
                           re.I)


def _numeros(consultas: list) -> list:
    """Números de sentencia, expediente o artículo de ley que trae la pregunta, y patrones para
    las sentencias viejas."""
    nuevos = list(dict.fromkeys(m.upper() for q in consultas for m in _NUMERO.findall(q)))[:3]
    nuevos += list(dict.fromkeys(c for q in consultas for c in leyes.citas(q)))[:3]
    viejos = list(dict.fromkeys(f"%núm. {n} del {d} de {mes.lower()} de {a}"
                                for q in consultas for n, d, mes, a in _NUMERO_VIEJO.findall(q)))[:3]
    return nuevos, viejos


def _por_numero(conn, numeros: tuple, usuario_id: int) -> list:
    """Si la pregunta trae un número de sentencia o de expediente, ese documento va primero."""
    nuevos, viejos = numeros
    if not (nuevos or viejos):
        return []
    return basedatos.filas(
        conn,
        f"""SELECT {_COLUMNAS}, 1.0 AS puntaje, left(f.texto, 400) AS extracto
            FROM documentos d JOIN fragmentos f ON f.documento_id = d.id AND f.orden < 2
            WHERE (upper(f_unaccent(d.numero)) = ANY(%(nums)s) OR upper(d.expediente) LIKE ANY(%(pats)s)
                   OR d.numero LIKE ANY(%(viejos)s)) AND {_PERMISO}
            ORDER BY d.id DESC, f.orden LIMIT 6""",
        {"nums": nuevos, "pats": [f"%{x}%" for x in nuevos], "viejos": viejos, "usuario": usuario_id})


def _por_significado(conn, vector: str, pregunta: str, usuario_id: int, n: int) -> list:
    tipo = basedatos.vector_tipo(conn)
    if not (vector and tipo):
        return []
    params = {"v": vector, "usuario": usuario_id, "n": n, "tq": _tsquery(pregunta) or "sentencia",
              "cand": CANDIDATOS}
    if basedatos.indice_binario(conn):
        # el índice binario trae candidatos rápido; luego se ordenan con el vector completo
        sql = f"""WITH cand AS (
                      SELECT id FROM fragmentos WHERE emb IS NOT NULL
                      ORDER BY binary_quantize(emb)::bit({basedatos.DIMENSIONES})
                               <~> binary_quantize(%(v)s::halfvec)
                      LIMIT %(cand)s)
                  SELECT {_COLUMNAS}, f.emb <=> %(v)s::halfvec AS distancia, {_EXTRACTO}
                  FROM cand JOIN fragmentos f USING (id) JOIN documentos d ON d.id = f.documento_id
                  WHERE {_PERMISO} ORDER BY distancia LIMIT %(n)s"""
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL hnsw.ef_search = {CANDIDATOS}")
    else:
        sql = f"""SELECT {_COLUMNAS}, f.emb <=> %(v)s::{tipo} AS distancia, {_EXTRACTO}
                  FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
                  WHERE f.emb IS NOT NULL AND {_PERMISO} ORDER BY distancia LIMIT %(n)s"""
    return basedatos.filas(conn, sql, params)


def _leyes_por_significado(conn, vector: str, pregunta: str, n: int) -> list:
    """Los artículos de ley y comentarios más parecidos a la pregunta (son pocos miles: se recorren todos)."""
    tipo = basedatos.vector_tipo(conn)
    if not (vector and tipo):
        return []
    return basedatos.filas(
        conn,
        f"""SELECT {_COLUMNAS}, f.emb <=> %(v)s::{tipo} AS distancia, {_EXTRACTO}
            FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
            WHERE f.emb IS NOT NULL AND d.origen IN ('ley', 'doctrina') AND d.usuario_id IS NULL
            ORDER BY distancia LIMIT %(n)s""",
        {"v": vector, "n": n, "tq": _tsquery(pregunta) or "ley"})


def _en_base(indice: int, url: str, consultas, numeros, vector, pregunta, usuario_id, n):
    """Las listas de una base: número, palabras y significado, y en la principal (donde están las
    leyes) también palabras y significado buscando solo en leyes y comentarios."""
    with basedatos.conectar(url) as conn:
        listas = [_por_numero(conn, numeros, usuario_id), _por_palabras(conn, consultas, usuario_id, n)]
        try:
            listas.append(_por_significado(conn, vector, pregunta, usuario_id, n))
        except Exception:
            conn.rollback()
            listas.append([])
        listas.append(_por_palabras(conn, consultas, usuario_id, LEYES_CANDIDATOS, solo_leyes=True)
                      if indice == 0 else [])
        try:
            listas.append(_leyes_por_significado(conn, vector, pregunta, LEYES_CANDIDATOS) if indice == 0 else [])
        except Exception:
            conn.rollback()
            listas.append([])
    for lista in listas:
        for f in lista:
            f["base"] = indice
    return listas


def buscar(consultas, usuario_id: int, limite: int = 8, pregunta: str = None) -> list:
    """Fragmentos más relevantes de todas las bases, mezclando palabras y significado, sin repetir."""
    from concurrent.futures import ThreadPoolExecutor
    if isinstance(consultas, str):
        consultas = [consultas]
    pregunta = pregunta or consultas[-1]
    vector = None
    if vectores.configurado():
        try:
            vector = vectores.como_texto(vectores.de_pregunta(pregunta))
        except Exception:
            pass   # sin vectores (sin cuota o sin red): queda la búsqueda por palabras
    urls, numeros = basedatos.bases(), _numeros(consultas)
    if not urls:
        return []
    # "art. 76 del Código de Trabajo" (los que pide la IA que prepara la búsqueda) se buscan por número;
    # por palabras solo meterían ruido ("código", "trabajo")
    consultas = [q for q in consultas if not _SOLO_CITA.fullmatch(q)] or consultas

    def una(par):
        try:
            return _en_base(par[0], par[1], consultas, numeros, vector, pregunta, usuario_id, limite * 3)
        except Exception as ex:   # si una base falla se busca en las demás
            return ex

    with ThreadPoolExecutor(max_workers=len(urls)) as hilos:
        resultados = list(hilos.map(una, enumerate(urls)))
    buenos = [r for r in resultados if not isinstance(r, Exception)]
    if not buenos:
        raise resultados[0]
    # se juntan las listas de todas las bases y cada una se ordena con su puntaje
    por_numero = [f for r in buenos for f in r[0]]
    por_palabras = sorted((f for r in buenos for f in r[1]), key=lambda f: f["puntaje"], reverse=True)
    por_significado = sorted((f for r in buenos for f in r[2]), key=lambda f: f["distancia"])
    # (lista, peso): un número exacto de sentencia o expediente pesa más que todo lo demás
    listas = [(por_numero, 3.0), (por_palabras, 1.0), (por_significado, 1.0)]
    puntos, filas = {}, {}
    for lista, peso in listas:
        for pos, f in enumerate(lista):
            k = (f["base"], f["id"])   # los id se repiten entre bases
            puntos[k] = puntos.get(k, 0.0) + peso / (RRF_K + pos + 1)
            filas.setdefault(k, f)
    ordenados = sorted(filas, key=lambda k: puntos[k], reverse=True)
    # los artículos de ley compiten con 28.000 sentencias y casi nunca llegaban arriba: por eso se buscan
    # también solo entre leyes y comentarios. Un artículo va adelante si lo pidieron por número, o si sale
    # por palabras entre las leyes (usa los términos de la pregunta: "preaviso", "cesantía"), ordenado por
    # cuánto se parece además por significado. Solo por significado no alcanza: sin palabras en común
    # salían artículos que no venían al caso.
    leyes_palabras = sorted((f for r in buenos for f in r[3]), key=lambda f: f["puntaje"], reverse=True)
    leyes_significado = sorted((f for r in buenos for f in r[4]), key=lambda f: f["distancia"])
    puntos_ley = {}
    for lista in (leyes_palabras, leyes_significado):
        for pos, f in enumerate(lista):
            k = (f["base"], f["id"])
            puntos_ley[k] = puntos_ley.get(k, 0.0) + 1.0 / (RRF_K + pos + 1)
            filas.setdefault(k, f)
            puntos.setdefault(k, 0.0)
    con_palabras = {(f["base"], f["id"]) for f in leyes_palabras}
    pedidos = [k for k in ((f["base"], f["id"]) for f in por_numero) if filas[k]["origen"] in ("ley", "doctrina")]
    articulos = list(dict.fromkeys(pedidos + sorted(con_palabras, key=lambda k: puntos_ley[k], reverse=True)))
    articulos = articulos[:MAX_ARTICULOS]
    ordenados = articulos + [k for k in ordenados if k not in articulos]
    # como máximo 2 fragmentos por documento, para variar las fuentes
    por_doc, final = {}, []
    for k in ordenados:
        f = filas[k]
        doc = (f["base"], f["documento_id"])
        if por_doc.get(doc, 0) < 2:
            por_doc[doc] = por_doc.get(doc, 0) + 1
            final.append({**f, "puntaje": puntos[k]})
        if len(final) == limite:
            break
    return final


def referencia(f: dict) -> str:
    """Cómo se cita una fuente: número, sala, origen y página."""
    if f["origen"] == "ley":
        return f'{f["numero"]}' + (f' ({f["titulo"]})' if f["titulo"] else "") + f' — {f["sala"]}'
    if f["origen"] == "doctrina":
        return f'Comentario: {f["numero"]} — {f["sala"]}, pág. {f["pagina"]}'
    partes = [f["numero"] or f["titulo"] or "Documento", f["sala"], f["materia"]]
    origen = "Boletín Judicial" if f["origen"] == "boletin" else "Documento propio"
    return f'{" · ".join(p for p in partes if p)} — {origen}, pág. {f["pagina"]}'
