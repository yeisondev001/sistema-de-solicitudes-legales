"""
Los modelos de escritos: escritos reales convertidos en formato, sin ningún dato del caso (Ley 172-13).

Cada modelo es un .txt de esta carpeta con el formato del escrito (generators/escrito.py) y su ficha en
catalogo.json. Papiniano los sugiere cuando le piden un escrito, y el abogado también los elige en «Modelos».
Los datos por llenar van entre corchetes y en mayúsculas ([NOMBRE DE SU CLIENTE]); los del abogado
([NOMBRE DEL ABOGADO]…) y [FECHA DE HOY] los llena la app sola.

Cada abogado también sube los suyos («Mis modelos»): se guardan en su cuenta (cuentas.py) y solo los ve él.
Su clave es «propio-<id>». Al subirlo, el Word se convierte aquí, sin la IA, y se le quitan solos los datos
que se reconocen (cédulas, RNC, correos, teléfonos, montos y fechas); los nombres los marca el abogado.
"""

import io
import json
import re
import unicodedata
from pathlib import Path

CARPETA = Path(__file__).parent

GRUPOS = {
    "actos": "Actos de alguacil",
    "demandas": "Demandas",
    "conclusiones": "Escritos de conclusiones",
    "defensas": "Escritos de defensa",
    "recursos": "Recursos y casación",
    "cartas": "Cartas y oficios",
}
MATERIAS = {"tierras": "Tierras", "administrativo": "Administrativo", "civil": "Civil", "laboral": "Laboral",
            "oficina": "Oficina"}

CATALOGO = json.loads((CARPETA / "catalogo.json").read_text(encoding="utf-8"))
_POR_CLAVE = {m["clave"]: m for m in CATALOGO}
_FICHA = ("clave", "nombre", "grupo", "materia", "tribunal", "cuando")

# palabras que no dicen qué documento es
_VACIAS = {"para", "como", "sobre", "contra", "entre", "desde", "donde", "porque", "este", "esta", "esto", "unos",
           "unas", "redacteme", "redacte", "hagame", "haga", "hacer", "preparar", "prepareme", "escriba",
           "necesito", "quiero", "favor", "documento", "escrito", "modelo", "cliente", "senor", "senora"}


def lista() -> list:
    return [{k: m[k] for k in _FICHA} for m in CATALOGO]


def ficha(clave: str):
    m = _POR_CLAVE.get(clave)
    return {k: m[k] for k in _FICHA} if m else None


def texto(clave: str):
    if clave not in _POR_CLAVE:
        return None
    return (CARPETA / f"{clave}.txt").read_text(encoding="utf-8").strip()


def _raices(t: str) -> list:
    """«Conclusiones de deslindes» → ["conclus", "de", "deslind"]: sin tildes, en minúsculas y cortadas a 7
    letras, así «conclusión» y «conclusiones» o «apelación» y «apelaciones» cuentan igual."""
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [p[:7] for p in re.findall(r"[a-z0-9]+", t)]


def propio(fila: dict) -> dict:
    """Un modelo del abogado (fila de cuentas.listar_modelos_propios) con la misma forma que los de todos."""
    return {"clave": f"propio-{fila['id']}", "nombre": fila["nombre"], "grupo": fila["grupo"] or "",
            "materia": fila["materia"] or "", "tribunal": "", "cuando": "Su modelo.", "propio": True}


def id_propio(clave: str):
    """«propio-12» → 12; None si es de los de todos."""
    m = re.fullmatch(r"propio-(\d+)", clave or "")
    return int(m.group(1)) if m else None


# Qué documento es. Si el abogado lo dice («unas conclusiones», «un acto»), el modelo tiene que ser de ese
# tipo: el primero de estos que aparece en el pedido y en el nombre del modelo, y los que le sirven a cada uno
_TIPOS = {
    "conclus": {"conclus"},
    "defensa": {"defensa", "memoria"},
    "memoria": {"memoria", "defensa", "recurso"},
    "recurso": {"recurso", "memoria", "instanc"},
    "casacio": {"recurso", "memoria", "defensa"},
    "demanda": {"demanda"},
    "acto": {"acto"},
    "citacio": {"acto"},
    "notific": {"acto"},
    "emplaza": {"acto"},
    "carta": {"carta"},
    "informe": {"carta"},
    "solicit": {"carta"},
    "instanc": {"instanc"},
}


def _tipo(raices: list):
    return next((r for r in raices if r in _TIPOS), None)


def sugerir(pedido: str, maximo: int = 3, propios: list = ()) -> list:
    """Los modelos que sirven para lo que pide el abogado («unas conclusiones para un deslinde»), del que
    más se parece al que menos; [] si ninguno se parece lo suficiente. Los suyos (propios) van primero si
    se parecen igual."""
    raices = _raices(pedido)
    frase = " " + " ".join(raices) + " "
    tipo = _tipo(raices)
    vacias = {_raices(v)[0] for v in _VACIAS} | {tipo}
    # lo que dice del caso (deslinde, laboral, justiprecio…), sin las palabras de relleno ni el tipo
    sueltas = {r for r in raices if len(r) > 3 and r not in vacias}
    puntos = []
    for m in [propio(f) for f in propios] + CATALOGO:
        nombre = _raices(f"{m['nombre']} {m['tribunal']}")
        # los del abogado sin tipo reconocible se ofrecen por su nombre, sea cual sea el tipo pedido
        tipo_modelo = _tipo(_raices(m["nombre"]))
        if tipo and tipo_modelo and tipo_modelo not in _TIPOS[tipo]:
            continue
        p = 0
        for palabra in m.get("palabras", []):
            r = _raices(palabra)
            propias = [x for x in r if len(x) > 3 and x not in vacias]
            if propias and f" {' '.join(r)} " in frase:
                p += 2 * len(propias)   # las frases largas que coinciden enteras pesan más
        # los del abogado no tienen palabras clave: cuenta su nombre, y una sola palabra que coincida basta
        p += len(sueltas & set(nombre)) * (3 if m.get("propio") else 1)
        puntos.append((p, m))
    puntos.sort(key=lambda x: -x[0])
    # si dijo qué documento es, basta con que coincida algo del caso; si no, tiene que parecerse más
    minimo = 1 if tipo else 3
    if not puntos or puntos[0][0] < minimo:
        return []
    corte = max(minimo, puntos[0][0] * 0.6)
    return [{k: m[k] for k in (*_FICHA, "propio") if k in m} for p, m in puntos[:maximo] if p >= corte]


# ── Un Word del abogado convertido en modelo ─────
def de_word(contenido: bytes) -> str:
    """El texto del Word en el formato del escrito: un párrafo por bloque, separados por una línea en blanco."""
    import docx
    d = docx.Document(io.BytesIO(contenido))
    bloques = [p.text.strip() for p in d.paragraphs]
    for tabla in d.tables:
        for fila in tabla.rows:
            celdas = list(dict.fromkeys(c.text.strip() for c in fila.cells if c.text.strip()))
            bloques.append(" ".join(celdas))
    texto = "\n\n".join(b for b in bloques if b)
    return re.sub(r"[ \t]+", " ", texto).strip()


# lo que se reconoce sin la IA; cada valor distinto lleva su número: [CÉDULA 1], [CÉDULA 2]
_DATOS = [
    ("CORREO", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("CÉDULA", re.compile(r"\b\d{3}-?\d{7}-?\d\b")),
    ("RNC", re.compile(r"\b\d-?\d{2}-?\d{5}-?\d\b")),
    ("TELÉFONO", re.compile(r"\(?\b8[024]9\)?[-\s.]?\d{3}[-\s.]?\d{4}\b")),
    ("MONTO", re.compile(r"(?:RD|US)?\$\s?\d[\d.,]*\d")),
    ("FECHA", re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")),
]


def quitar_datos(texto: str) -> tuple:
    """(texto con los datos que se reconocen cambiados por datos por llenar, cuántos se cambiaron)."""
    cambios = 0
    for nombre, patron in _DATOS:
        vistos = {}

        def poner(m):
            nonlocal cambios
            cambios += 1
            valor = re.sub(r"\D", "", m.group(0)) or m.group(0)
            vistos.setdefault(valor, len(vistos) + 1)
            return f"[{nombre} {vistos[valor]}]"
        texto = patron.sub(poner, texto)
    return texto, cambios
