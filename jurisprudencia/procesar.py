"""
Procesamiento de documentos: extraer texto (PDF / Word), detectar la ficha
de la sentencia y partirla en fragmentos para el buscador.
Lo usan por igual los documentos subidos y los boletines.
"""

import re, shutil, subprocess
from pathlib import Path

PALABRAS_POR_FRAGMENTO = 400
SOLAPE = 50
MIN_CARACTERES_POR_PAGINA = 80   # menos que esto: PDF escaneado (sin texto)


class DocumentoSinTexto(Exception):
    """El archivo no tiene texto extraíble (por ejemplo, un PDF escaneado)."""


def _paginas_pdftotext(ruta: Path):
    """pdftotext (poppler) es unas 10 veces más rápido que pypdf con el Boletín (7.000+ páginas)."""
    if not shutil.which("pdftotext"):
        return None
    r = subprocess.run(["pdftotext", "-enc", "UTF-8", str(ruta), "-"], capture_output=True, timeout=1800)
    if r.returncode != 0:
        return None
    partes = r.stdout.decode("utf-8", "replace").split("\f")
    if partes and not partes[-1].strip():
        partes = partes[:-1]
    return [(i + 1, t.replace("\x00", "")) for i, t in enumerate(partes)]


def extraer_paginas(ruta: str) -> list:
    """Lista de (número de página, texto)."""
    ruta = Path(ruta)
    ext = ruta.suffix.lower()
    if ext == ".pdf":
        paginas = _paginas_pdftotext(ruta)
        if paginas is None:
            from pypdf import PdfReader   # licencia BSD (PyMuPDF es AGPL)
            paginas = [(i + 1, (p.extract_text() or "").replace("\x00", ""))
                       for i, p in enumerate(PdfReader(ruta).pages)]
        if not paginas or sum(len(t.strip()) for _, t in paginas) < MIN_CARACTERES_POR_PAGINA * len(paginas) / 2:
            raise DocumentoSinTexto("El PDF no tiene texto (parece escaneado).")
        return paginas
    if ext == ".docx":
        import docx
        texto = "\n".join(p.text for p in docx.Document(ruta).paragraphs)
        if len(texto.strip()) < MIN_CARACTERES_POR_PAGINA:
            raise DocumentoSinTexto("El Word está vacío.")
        return [(1, texto)]
    raise ValueError("Solo se aceptan archivos PDF o Word (.docx).")


_SALAS = [("PRIMERA SALA", "Primera Sala"), ("SEGUNDA SALA", "Segunda Sala"),
          ("TERCERA SALA", "Tercera Sala"), ("SALAS REUNIDAS", "Salas Reunidas"),
          ("PLENO", "Pleno"), ("TRIBUNAL CONSTITUCIONAL", "Tribunal Constitucional")]


def _campo(patron, texto):
    m = re.search(patron, texto, re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip(" .:") if m else ""


def detectar_ficha(texto: str) -> dict:
    """Busca en el inicio del documento los datos de la cabecera de la sentencia."""
    inicio = texto[:4000]
    mayus = inicio.upper()
    sala = next((nombre for clave, nombre in _SALAS if clave in mayus), "")
    return {
        "numero":     _campo(r"\b(SCJ-[A-Z]{2,3}-\d{2}-\d{3,5}|TC/\d{4}/\d{2,4}|\d{3}-\d{3}-\d{4}-SRES-\d+)", inicio),
        "expediente": _campo(r"Exp(?:ediente)?\.?\s*(?:n[úu]m\.?|No\.?)\s*([^\n]{3,60})", inicio),
        # a veces "Materia: … Decisión: … Ponente: …" vienen en la misma línea
        "materia":    _campo(r"Materia:\s*([^\n]{3,120}?)(?:\s+Decisi[óo]n:|\n|$)", inicio),
        "decision":   _campo(r"Decisi[óo]n:\s*([^\n]{3,120}?)(?:\s+Ponente:|\n|$)", inicio),
        "fecha":      _campo(r"en fecha\s+(\d{1,2} de [a-záéíóú]+ de \d{4})", texto[:8000]),
        "sala":       sala,
    }


def fragmentar(paginas: list) -> list:
    """Parte el texto en fragmentos de ~400 palabras; cada uno recuerda su página."""
    palabras = []   # (palabra, página)
    for num, texto in paginas:
        palabras.extend((w, num) for w in texto.split())
    fragmentos, paso = [], PALABRAS_POR_FRAGMENTO - SOLAPE
    for i in range(0, len(palabras), paso):
        trozo = palabras[i:i + PALABRAS_POR_FRAGMENTO]
        if len(trozo) < 30 and fragmentos:
            break
        fragmentos.append({"pagina": trozo[0][1], "texto": " ".join(w for w, _ in trozo)})
    return fragmentos


def guardar(conn, ficha: dict, fragmentos: list, origen: str, usuario_id=None, titulo="",
            fuente_url="", pagina=1) -> int:
    """Inserta el documento y sus fragmentos; devuelve el id del documento."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO documentos (usuario_id, origen, titulo, numero, expediente, sala, materia, "
            "decision, fecha, fuente_url, pagina) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (usuario_id, origen, titulo, ficha.get("numero", ""), ficha.get("expediente", ""),
             ficha.get("sala", ""), ficha.get("materia", ""), ficha.get("decision", ""),
             ficha.get("fecha", ""), fuente_url, pagina))
        doc_id = cur.fetchone()[0]
        cur.executemany(
            "INSERT INTO fragmentos (documento_id, orden, pagina, texto) VALUES (%s, %s, %s, %s)",
            [(doc_id, n, f["pagina"], f["texto"].replace("\x00", "")) for n, f in enumerate(fragmentos)])
    conn.commit()
    return doc_id


# Tierras e Inmobiliario (la materia de los primeros usuarios) reciben vectores antes que el resto
PRIORITARIOS = r"(d.materia || ' ' || d.titulo) ~* 'tierra|inmobiliari|deslinde|saneamiento|registrad|litis'"


def vectorizar_pendientes(conn, documento_id=None, max_neuronas=None, lote=256, solo_prioritarios=False) -> dict:
    """Calcula los vectores que faltan sin pasarse de max_neuronas: primero los documentos
    propios, luego Tierras e Inmobiliario, y dentro de eso los más nuevos."""
    from . import basedatos, vectores
    hechos, gastadas = 0, 0.0
    tipo = basedatos.vector_tipo(conn)
    if not (tipo and vectores.configurado()):
        return {"fragmentos": 0, "neuronas": 0.0, "agotado": False, "saltados": 0}
    filtro, params = ("AND f.documento_id = %s", [documento_id]) if documento_id else ("", [])
    if solo_prioritarios:
        filtro += f" AND {PRIORITARIOS}"
    saltados = []   # los que Cloudflare rechaza se dejan para otra corrida
    while max_neuronas is None or gastadas < max_neuronas:
        with conn.cursor() as cur:
            cur.execute(f"""SELECT f.id, f.texto, d.numero, d.sala, d.materia
                            FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
                            WHERE f.emb IS NULL AND NOT (f.id = ANY(%s)) {filtro}
                            ORDER BY d.origen = 'propio' DESC, {PRIORITARIOS} DESC, f.id DESC
                            LIMIT %s""", [saltados] + params + [lote])
            filas = cur.fetchall()
        if not filas:
            break
        # la cabecera (número, sala, materia) ayuda a ubicar el fragmento
        textos = [" · ".join(p for p in (num, sala, mat) if p) + "\n" + texto for _, texto, num, sala, mat in filas]
        try:
            vecs, neuronas = vectores.de_documentos(textos)
        except vectores.LimiteAlcanzado:
            return {"fragmentos": hechos, "neuronas": gastadas, "agotado": True, "saltados": len(saltados)}
        listos = [(vectores.como_texto(v), fila[0]) for v, fila in zip(vecs, filas) if v]
        saltados += [fila[0] for v, fila in zip(vecs, filas) if not v]
        with conn.cursor() as cur:
            cur.executemany(f"UPDATE fragmentos SET emb = %s::{tipo} WHERE id = %s", listos)
        conn.commit()
        hechos += len(listos)
        gastadas += neuronas
    return {"fragmentos": hechos, "neuronas": gastadas, "agotado": False, "saltados": len(saltados)}


def subir_documento(ruta: str, usuario_id: int, nombre_archivo: str) -> dict:
    """Procesa un archivo subido por un usuario y lo agrega a su parte del buscador."""
    from .basedatos import conectar
    paginas = extraer_paginas(ruta)
    ficha = detectar_ficha("\n".join(t for _, t in paginas[:3]))
    fragmentos = fragmentar(paginas)
    with conectar() as conn:
        doc_id = guardar(conn, ficha, fragmentos, "propio", usuario_id, titulo=nombre_archivo)
        try:   # si falla (sin cuota, sin red) se busca por palabras y el vector se calcula después
            vectorizar_pendientes(conn, documento_id=doc_id)
        except Exception:
            conn.rollback()
    return {"id": doc_id, "fragmentos": len(fragmentos), "paginas": len(paginas), **ficha}


def mis_documentos(usuario_id: int) -> list:
    from .basedatos import consultar
    return consultar(
        "SELECT d.id, d.titulo, d.numero, d.sala, d.materia, d.creado, COUNT(f.id) AS fragmentos "
        "FROM documentos d LEFT JOIN fragmentos f ON f.documento_id = d.id "
        "WHERE d.usuario_id = %s GROUP BY d.id ORDER BY d.id DESC", (usuario_id,))


def borrar_documento(doc_id: int, usuario_id: int):
    from .basedatos import ejecutar
    ejecutar("DELETE FROM documentos WHERE id = %s AND usuario_id = %s", (doc_id, usuario_id))
