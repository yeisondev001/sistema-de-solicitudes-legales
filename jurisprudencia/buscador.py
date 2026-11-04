"""
Búsqueda de texto en español sobre los fragmentos (PostgreSQL full-text).
Cada usuario busca en el Boletín Judicial (público) y en sus propios documentos.
"""

import re

from .basedatos import consultar

_PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-/]*")


def _tsquery(texto: str) -> str:
    """'litis derechos registrados' -> 'litis | derechos | registrados' (cualquiera suma)."""
    palabras = [p for p in _PALABRA.findall(texto) if len(p) > 2]
    return " | ".join(dict.fromkeys(palabras))


def buscar(consultas, usuario_id: int, limite: int = 8) -> list:
    """Fragmentos más relevantes para una o varias consultas, sin repetir."""
    if isinstance(consultas, str):
        consultas = [consultas]
    mejores = {}
    for q in consultas:
        tq = _tsquery(q)
        if not tq:
            continue
        filas = consultar(
            """SELECT f.id, f.pagina, f.texto, d.id AS documento_id, d.origen, d.titulo, d.numero,
                      d.expediente, d.sala, d.materia, d.decision, d.fecha, d.fuente_url,
                      ts_rank_cd(f.tsv, q) AS puntaje,
                      ts_headline('spanish', f.texto, q,
                                  'MaxWords=45, MinWords=20, MaxFragments=2, FragmentDelimiter=" … "') AS extracto
               FROM fragmentos f
               JOIN documentos d ON d.id = f.documento_id,
                    to_tsquery('spanish', f_unaccent(%s)) q
               WHERE f.tsv @@ q AND (d.usuario_id IS NULL OR d.usuario_id = %s)
               ORDER BY puntaje DESC
               LIMIT %s""",
            (tq, usuario_id, limite * 2))
        for f in filas:
            if f["id"] not in mejores or f["puntaje"] > mejores[f["id"]]["puntaje"]:
                mejores[f["id"]] = f
    resultado = sorted(mejores.values(), key=lambda f: f["puntaje"], reverse=True)
    # como máximo 2 fragmentos por documento, para variar las fuentes
    por_doc, final = {}, []
    for f in resultado:
        if por_doc.get(f["documento_id"], 0) < 2:
            por_doc[f["documento_id"]] = por_doc.get(f["documento_id"], 0) + 1
            final.append(f)
        if len(final) == limite:
            break
    return final


def referencia(f: dict) -> str:
    """Cómo se cita una fuente: número, sala, origen y página."""
    partes = [f["numero"] or f["titulo"] or "Documento", f["sala"], f["materia"]]
    origen = "Boletín Judicial" if f["origen"] == "boletin" else "Documento propio"
    return f'{" · ".join(p for p in partes if p)} — {origen}, pág. {f["pagina"]}'
