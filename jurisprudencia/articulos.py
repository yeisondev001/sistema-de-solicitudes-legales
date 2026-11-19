"""
Que el escrito no cite artículos que no están en la biblioteca.

La IA a veces pone de memoria «el artículo 1975 del Código Civil» con un contenido inventado. Regla del
dueño: si el artículo no está en la base de datos de Papiniano, no va en el escrito. Aquí se encuentran las
citas de artículos de un texto, se dice a qué norma son y se quitan las que no existen en la base
(se cambian por [ARTÍCULO POR VERIFICAR], para que el abogado vea que ahí faltaba la base legal).
"""

import re

from . import leyes

# «el artículo 1184 del Código Civil», «los artículos 1315 y 1382 del Código Civil», «art. 81 de la Ley 108-05»
_CITA = re.compile(
    r"(?:\b(?:el|los|del|al)\s+)?\bart(?:[íi]culos?|s?\.)\s*(\d{1,4})((?:\s*(?:,|y|e)\s*\d{1,4})*)", re.I)
# lo que nombra una norma que no reconocemos (no está cargada): se quita igual
_NORMA_DESCONOCIDA = re.compile(
    r"^\W{0,3}(?:[\w\s,.ºo°]{0,30}?)\b(?:del?|de\s+la)\s+(?:"
    r"Ley\s*(?:Org[áa]nica\s*)?(?:n[úu]m\.?|No\.?|número)?\s*\d[\d-]*(?:\s+de\s+\d{4})?"
    r"|Constituci[óo]n(?:\s+(?:de\s+la\s+)?Rep[úu]blica)?(?:\s+Dominicana)?"
    r"|C[óo]digo\s+(?:de\s+|del\s+)?[A-Za-zÁÉÍÓÚáéíóú]+(?:\s+[A-Za-zÁÉÍÓÚáéíóú]+)?"
    r"|Reglamento\s+[^,.;]{3,60}|Resoluci[óo]n\s+[^,.;]{3,40}|Decreto\s+[^,.;]{3,40})",
    re.I)
POR_VERIFICAR = "[ARTÍCULO POR VERIFICAR]"


def _sin_tildes(t: str) -> str:
    return t.upper().translate(str.maketrans("ÁÉÍÓÚÜ", "AEIOUU"))


def citas(texto: str) -> list:
    """[{"texto": la cita tal como está, "inicio", "fin", "claves": ["CODIGO CIVIL, ART. 1184", …] o None si
    la norma no está cargada}] de las citas de artículos de una norma con nombre. Las que no nombran norma
    («el artículo anterior») no cuentan."""
    salida = []
    for m in _CITA.finditer(texto):
        numeros = [int(m.group(1))] + [int(n) for n in re.findall(r"\d{1,4}", m.group(2) or "")]
        resto = texto[m.end():m.end() + 90]
        # la norma que se nombra más cerca después del número
        nombradas = []
        for norma in leyes.NORMAS + leyes.OBRAS:
            if not norma.get("alias"):
                continue
            a = re.search(norma["alias"], resto, re.I)
            if a and not re.search(r"[.;]\s", resto[:a.start()]):
                nombradas.append((a.start(), a.end(), norma))
        if nombradas:
            inicio_norma, fin_norma, norma = min(nombradas, key=lambda x: x[0])
            # «del Código Penal derogado» y «del Código Penal (Ley 74-25)»: el alias más largo que empieza ahí
            mismos = [x for x in nombradas if x[0] == inicio_norma]
            inicio_norma, fin_norma, norma = max(mismos, key=lambda x: x[1])
            claves = [_sin_tildes(leyes.numero(norma, n)) for n in numeros]
            salida.append({"texto": texto[m.start():m.end() + fin_norma], "inicio": m.start(),
                           "fin": m.end() + fin_norma, "claves": claves})
            continue
        d = _NORMA_DESCONOCIDA.match(resto)
        if d:
            salida.append({"texto": texto[m.start():m.end() + d.end()], "inicio": m.start(),
                           "fin": m.end() + d.end(), "claves": None})
    return salida


def sin_respaldo(texto: str, existen, exentas: set = frozenset()) -> list:
    """Las citas del texto cuyos artículos no están en la base. existen(claves) -> set de las que sí están.
    exentas: claves que ya estaban (el escrito que el abogado está cambiando), que no se tocan."""
    lista = citas(texto)
    todas = {c for x in lista if x["claves"] for c in x["claves"]} - set(exentas)
    try:
        hay = existen(sorted(todas)) if todas else set()
    except Exception:
        return []   # sin poder revisar la base no se quita nada
    malas = []
    for x in lista:
        if x["claves"] is None:
            malas.append(x)
        elif any(c not in hay and c not in exentas for c in x["claves"]):
            malas.append(x)
    return malas


def quitar(texto: str, malas: list) -> str:
    """Cambia cada cita sin respaldo por [ARTÍCULO POR VERIFICAR] (de atrás hacia adelante)."""
    for x in sorted(malas, key=lambda x: x["inicio"], reverse=True):
        texto = texto[:x["inicio"]] + POR_VERIFICAR + texto[x["fin"]:]
    return texto


def claves_de(texto: str) -> set:
    """Las claves de los artículos que cita un texto (para dejar exentas las del escrito que ya estaba)."""
    return {c for x in citas(texto) if x["claves"] for c in x["claves"]}
