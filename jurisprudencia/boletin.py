"""
Carga del Boletín Judicial mensual de la Suprema Corte de Justicia (público).
El PDF del mes trae al inicio un índice con cada sentencia y su página; con eso
se corta el PDF en sentencias, se guardan en la base y el PDF se borra.
Fuente: https://consultaglobal.blob.core.windows.net/boletines/Boletines/{AÑO}/{MES}.pdf
(Ley 65-00, art. 41: los textos judiciales pueden reutilizarse citando la fuente).
"""

import re
from pathlib import Path

import httpx

from .procesar import detectar_ficha, extraer_paginas, fragmentar, guardar

MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
         "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
_URL = "https://consultaglobal.blob.core.windows.net/boletines/Boletines/{anio}/{mes}.pdf"

_SALAS = {"primera sala": "Primera Sala", "segunda sala": "Segunda Sala", "tercera sala": "Tercera Sala",
          "salas reunidas": "Salas Reunidas", "pleno": "Pleno"}
_FIN_ENTRADA = re.compile(r"\.{3,}\s*(\d{1,5})\s*$")      # "Inadmisible.........33"
_PRUEBA = re.compile(r"test|prueba|^(\d)\1{5,}$|^123456$", re.I)
BUSCAR_PAGINAS = 3   # si la sentencia no está en la página del índice, se busca ±3


def url_mes(anio: int, mes: int) -> str:
    return _URL.format(anio=anio, mes=MESES[mes - 1])


def buscar_url(anio: int, mes: int):
    """URL del PDF del mes, o None si no está publicado. El nombre del archivo cambia de
    un año a otro (MAYO.pdf, Mayo.pdf, junio.pdf) y el servidor distingue mayúsculas."""
    nombre = MESES[mes - 1]
    for variante in dict.fromkeys((nombre, nombre.capitalize(), nombre.lower())):
        url = _URL.format(anio=anio, mes=variante)
        if httpx.head(url, timeout=60, follow_redirects=True).status_code == 200:
            return url
    return None


def mes_de_url(url: str):
    """(año, mes) de una URL del Boletín, o None."""
    m = re.search(r"/Boletines/(\d{4})/([^/]+)\.pdf$", url)
    if m and m.group(2).upper() in MESES:
        return int(m.group(1)), MESES.index(m.group(2).upper()) + 1
    return None


def descargar(url: str, destino: Path) -> bool:
    """Descarga el PDF del mes; False si todavía no está publicado."""
    with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
        if r.status_code == 404:
            return False
        r.raise_for_status()
        with open(destino, "wb") as f:
            for trozo in r.iter_bytes(1 << 20):
                f.write(trozo)
    return True


def _entrada(texto: str, sala: str):
    """'• Sentencia Definitiva SCJ-PS-25-0917 | Expediente No. X | Civil | Recurso | Decisión....33'"""
    fin = _FIN_ENTRADA.search(texto)
    if not fin:
        return None
    partes = [p.strip() for p in texto[:fin.start()].lstrip("•").split("|")]
    tipo_num = partes[0].split()
    if len(tipo_num) < 2:
        return None
    exp = re.sub(r"^Expediente\s+No\.?\s*", "", partes[1]) if len(partes) > 1 else ""
    # el índice escribe "Contenciosoadministrativo" y "Contencioso-administrativo"
    materia = re.sub(r"^Contencioso-?\s*(\w)", r"Contencioso-\1", partes[2]) if len(partes) > 2 else ""
    return {"tipo": " ".join(tipo_num[:-1]), "numero": tipo_num[-1], "expediente": exp,
            "materia": materia, "recurso": partes[3] if len(partes) > 3 else "",
            "decision": partes[-1] if len(partes) > 4 else "", "sala": sala, "pagina": int(fin.group(1))}


def leer_indice(paginas: list) -> list:
    """Entradas del índice (las de prueba se descartan)."""
    entradas, sala, actual, en_indice = [], "", None, False
    for _, texto in paginas[:80]:
        if "•" not in texto:
            if en_indice:
                break          # terminó el índice
            continue
        en_indice = True
        for linea in texto.splitlines():
            linea = linea.strip()
            if actual is None and linea.lower() in _SALAS:
                sala = _SALAS[linea.lower()]
            elif linea.startswith("•"):
                actual = linea
            elif actual is not None:
                actual += " " + linea
            if actual is not None and _FIN_ENTRADA.search(actual):
                e = _entrada(actual, sala)
                if e and not (_PRUEBA.search(e["numero"]) or _PRUEBA.search(e["expediente"])):
                    entradas.append(e)
                actual = None
    return entradas


def quitar_repetidas(paginas: list, proporcion: float = 0.2) -> list:
    """Quita las líneas que se repiten en muchas páginas (pie de página con la dirección,
    teléfono y web del Poder Judicial, rayas separadoras). No aportan y ensucian la búsqueda."""
    def clave(linea):   # el pie trae el número de página: se compara sin números
        return re.sub(r"\d+", "#", linea.strip())
    cuenta = {}
    for _, texto in paginas:
        for c in {clave(l) for l in texto.splitlines() if len(l.strip()) > 3}:
            cuenta[c] = cuenta.get(c, 0) + 1
    repetidas = {c for c, n in cuenta.items() if n > proporcion * len(paginas)}
    return [(num, "\n".join(l for l in texto.splitlines() if clave(l) not in repetidas and not _PIE.search(l)))
            for num, texto in paginas]


# el pie del Poder Judicial sale cortado de muchas formas distintas
_PIE = re.compile(r"H[ée]roes de Constanza|Estero Hondo|poderjudicial\.gob\.do|^\s*•?\s*(Tel\.?:|E-?mail:)", re.I)


def _normal(t: str) -> str:
    return re.sub(r"\s+", "", t).upper()


def _ubicar(entrada: dict, paginas: list) -> int:
    """Página real donde empieza la sentencia (a veces el índice está corrido unas páginas)."""
    total, num = len(paginas), _normal(entrada["numero"])
    # en algunas resoluciones el número sale cortado ("-SRES-00121"): basta con el final
    final = _normal("-" + "-".join(entrada["numero"].split("-")[-2:])) if num.count("-") >= 3 else num
    for d in [0] + [x for k in range(1, BUSCAR_PAGINAS + 1) for x in (k, -k)]:
        p = entrada["pagina"] + d
        if 1 <= p <= total:
            cabecera = _normal(paginas[p - 1][1][:1500])
            if num in cabecera or final in cabecera:
                return p
    return entrada["pagina"]


def cortar(paginas: list, entradas: list) -> list:
    """[(entrada, páginas de esa sentencia)], en orden de página."""
    for e in entradas:
        e["inicio"] = _ubicar(e, paginas)
    entradas = sorted((e for e in entradas if 1 <= e["inicio"] <= len(paginas)), key=lambda e: e["inicio"])
    resultado = []
    for i, e in enumerate(entradas):
        fin = entradas[i + 1]["inicio"] - 1 if i + 1 < len(entradas) else len(paginas)
        resultado.append((e, paginas[e["inicio"] - 1:max(fin, e["inicio"])]))
    return resultado


# Los boletines anteriores a 2025 (y el de enero 2025) no traen el índice con "|", así que
# se cortan por la cabecera que trae cada sentencia arriba de su primera página:
#   2020-2021: "SENTENCIA DEL 27 DE ENERO DE 2021, NÚM. 10"
#   2022-2024: "SENTENCIA DEL 29 DE JUNIO DE 2022, NÚM. SCJ-PS-22-1765"
#   enero 2025: "SCJ-PS-25-0001 Exp. núm. … Materia: … Decisión: …" repetido en cada página
_CABECERA = re.compile(r"\b(SENTENCIA|RESOLUCI[ÓO]N|AUTO)\s+DEL?\s+(\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚ]+\s+DE\s+\d{4}),?"
                       r"\s*N[ÚU]M\.?\s*([\w-]+)", re.I)
_SCJ = re.compile(r"\bSCJ-([A-Z]{2,3})-\d{2}-\d{3,5}\b")
_SALA_SCJ = {"PS": "Primera Sala", "SS": "Segunda Sala", "TS": "Tercera Sala", "SR": "Salas Reunidas"}


def _arriba(texto: str) -> str:
    return "\n".join([l.strip() for l in texto.splitlines() if l.strip()][:6])[:700]


def _dueno(texto: str):
    """(número, fecha) de la sentencia que empieza o sigue en esta página, según su cabecera."""
    arriba = _arriba(texto)
    # página del índice ("• SENTENCIA …" o "SCJ-PS-25-0001 ......... 137"); ojo: desde 2023 la
    # cabecera de página también trae "•" ("Boletín Judicial núm. 1358 • Primera Sala • …")
    if re.search(r"^•", arriba, re.M) or re.search(r"\.{8,}", arriba):
        return None
    m = _CABECERA.search(arriba)
    if m:
        return m.group(3), m.group(2).lower()
    m = _SCJ.search(arriba)
    return (m.group(0), "") if m else None


def cortar_por_cabeceras(crudas: list, limpias: list) -> list:
    """[(datos, páginas)] buscando la cabecera de cada sentencia en el cuerpo del PDF.
    La cabecera se busca en las páginas sin limpiar (la limpieza podría quitarla por repetida)."""
    docs, actual = [], None
    for (num, texto), (_, limpio) in zip(crudas, limpias):
        dueno = _dueno(texto)
        if dueno is None and re.search(r"^Jueces\b", _arriba(texto), re.M | re.I):
            actual = None   # portada de una sala ("Primera Sala · Jueces …"): no es de ninguna sentencia
            continue
        if dueno and (actual is None or dueno[0] != actual[0]["numero"]):
            actual = ({"numero": dueno[0], "fecha": dueno[1], "inicio": num,
                       "cabecera": set(_arriba(texto).splitlines())}, [])
            docs.append(actual)
        if actual is not None:
            actual[1].append((num, limpio))
    # la cabecera de enero 2025 se repite en cada página: se deja solo en la primera
    return [(d, pags[:1] + [(n, "\n".join(l for l in t.splitlines() if l.strip() not in d["cabecera"]))
                            for n, t in pags[1:]]) for d, pags in docs]


def _cargar_por_cabeceras(conn, crudas: list, limpias: list, url: str, existentes: set, aviso) -> int:
    docs = cortar_por_cabeceras(crudas, limpias)
    aviso(f"  {len(crudas)} páginas, {len(docs)} sentencias por cabecera")
    nuevas = 0
    for d, pags in docs:
        ficha = detectar_ficha("\n".join(t for _, t in pags[:3]))
        scj = _SCJ.fullmatch(d["numero"])
        sala = _SALA_SCJ.get(scj.group(1), "") if scj else ""
        ficha["sala"] = sala or ficha["sala"]
        ficha["fecha"] = ficha["fecha"] or d["fecha"]
        # antes de 2022 la numeración vuelve a empezar en cada sala
        ficha["numero"] = d["numero"] if scj else \
            f'{ficha["sala"] or "SCJ"}, núm. {d["numero"]} del {d["fecha"]}'
        if ficha["numero"] in existentes:
            continue
        fragmentos = fragmentar(pags)
        if fragmentos:
            guardar(conn, ficha, fragmentos, "boletin", None, titulo=ficha["materia"] or ficha["numero"],
                    fuente_url=url, pagina=d["inicio"])
            existentes.add(ficha["numero"])
            nuevas += 1
    return nuevas


def ya_cargado(conn, url: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM boletines_cargados WHERE fuente_url = %s", (url,))
        return cur.fetchone() is not None


def cargar_pdf(conn, ruta_pdf: str, url: str, aviso=print) -> int:
    """Guarda las sentencias de un PDF del Boletín ya descargado; devuelve cuántas se agregaron."""
    crudas = extraer_paginas(ruta_pdf)
    paginas = quitar_repetidas(crudas)
    entradas = leer_indice(paginas)
    with conn.cursor() as cur:
        cur.execute("SELECT numero FROM documentos WHERE origen = 'boletin' AND fuente_url = %s", (url,))
        existentes = {f[0] for f in cur.fetchall()}
    nuevas = 0
    # el índice con "|" (desde 2025) trae materia y decisión; los demás se cortan por cabecera
    if sum(1 for e in entradas if e["expediente"]) < max(5, len(entradas) // 2):
        nuevas = _cargar_por_cabeceras(conn, crudas, paginas, url, existentes, aviso)
        entradas = []
    else:
        aviso(f"  {len(paginas)} páginas, {len(entradas)} sentencias en el índice")
    for e, pags in cortar(paginas, entradas):
        if e["numero"] in existentes:
            continue
        cabecera = detectar_ficha("\n".join(t for _, t in pags[:3]))
        ficha = {"numero": e["numero"], "expediente": e["expediente"] or cabecera["expediente"],
                 "sala": e["sala"] or cabecera["sala"], "materia": e["materia"],
                 "decision": e["decision"] or cabecera["decision"], "fecha": cabecera["fecha"]}
        titulo = cabecera["materia"] or f'{e["tipo"]} {e["numero"]}'
        fragmentos = fragmentar(pags)
        if fragmentos:
            guardar(conn, ficha, fragmentos, "boletin", None, titulo=titulo, fuente_url=url, pagina=e["inicio"])
            existentes.add(e["numero"])
            nuevas += 1
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO boletines_cargados (fuente_url, sentencias) VALUES (%s, %s)
                       ON CONFLICT (fuente_url) DO UPDATE SET sentencias = EXCLUDED.sentencias,
                                                              cargado = CURRENT_TIMESTAMP""",
                    (url, len(existentes)))
    conn.commit()
    return nuevas
