"""
Muestra dentro de la app la página del PDF que cita una fuente (sentencia del Boletín,
artículo de ley o comentario), tal como es, como imagen, sin salir de la página.

Los PDFs del Boletín pesan cientos de MB (mayo 2025: 275 MB), así que no se descargan:
  1. qpdf (pikepdf) lee el PDF a pedazos con peticiones HTTP "Range": solo el índice del
     archivo y los objetos de esa página (~2-3 MB, ~2 segundos, medido).
  2. Con esos objetos se arma un PDF de una sola página y pdfium lo dibuja.
Ojo: pdfium no sirve para el paso 1 (para llegar a la página 3.500 lee una por una las
anteriores: ~100 MB y casi un minuto), ni qpdf si se le deja juntar las páginas o copiar
objetos con copy_foreign (recorre todo el árbol de páginas).

Los pedazos ya leídos quedan en memoria (hasta MAX_MB) y los últimos PDFs quedan abiertos,
así la página siguiente sale al instante.
pikepdf (MPL) y pypdfium2 (Apache/BSD); PyMuPDF es AGPL.
"""

import io, re, threading
from collections import OrderedDict

import httpx

BLOQUE = 256 * 1024     # tamaño de cada pedazo que se pide al servidor
MAX_MB = 96             # memoria para pedazos, sumando todos los PDFs
ANCHO = 1100            # ancho de la imagen en píxeles

_bloques = OrderedDict()  # (url, n° de bloque) -> bytes, el más viejo primero
_tamanos = {}             # url -> tamaño del archivo
_candado = threading.Lock()
_cliente = httpx.Client(timeout=60, follow_redirects=True, trust_env=False)
_abiertos = OrderedDict()  # url -> pikepdf.Pdf, los últimos 3 (qpdf no admite dos hilos a la vez)
_candado_pdf = threading.Lock()


def _tamano(url: str) -> int:
    if url not in _tamanos:
        r = _cliente.get(url, headers={"Range": "bytes=0-0"})
        r.raise_for_status()
        rango = r.headers.get("content-range", "")       # "bytes 0-0/274774247"
        _tamanos[url] = int(rango.rsplit("/", 1)[1]) if "/" in rango else len(r.content)
    return _tamanos[url]


def _bloque(url: str, n: int) -> bytes:
    with _candado:
        if (url, n) in _bloques:
            _bloques.move_to_end((url, n))
            return _bloques[(url, n)]
    desde = n * BLOQUE
    r = _cliente.get(url, headers={"Range": f"bytes={desde}-{desde + BLOQUE - 1}"})
    r.raise_for_status()
    datos = r.content if r.status_code == 206 else r.content[desde:desde + BLOQUE]
    with _candado:
        _bloques[(url, n)] = datos
        while len(_bloques) * BLOQUE > MAX_MB * 2 ** 20:
            _bloques.popitem(last=False)
    return datos


class _ArchivoRemoto(io.RawIOBase):
    """Un PDF en internet que se lee como un archivo local."""

    def __init__(self, url: str):
        self.url, self.pos, self.largo = url, 0, _tamano(url)

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, pos, desde=io.SEEK_SET):
        self.pos = {io.SEEK_SET: pos, io.SEEK_CUR: self.pos + pos, io.SEEK_END: self.largo + pos}[desde]
        return self.pos

    def tell(self):
        return self.pos

    def readinto(self, destino):
        fin = min(self.pos + len(destino), self.largo)
        partes = []
        while self.pos < fin:
            n, desplazamiento = divmod(self.pos, BLOQUE)
            trozo = _bloque(self.url, n)[desplazamiento:desplazamiento + fin - self.pos]
            if not trozo:
                break
            partes.append(trozo)
            self.pos += len(trozo)
        datos = b"".join(partes)
        destino[:len(datos)] = datos
        return len(datos)


def _hoja(pdf, n: int):
    """La página n (desde 0) sin leer las demás: se baja por el árbol usando /Count."""
    nodo = pdf.Root.Pages
    while True:
        hijos = nodo.Kids
        if int(nodo.Count) == len(hijos):   # todos son páginas: se va directo
            return hijos[n]
        for hijo in hijos:
            if "/Kids" in hijo:
                if n < int(hijo.Count):
                    nodo = hijo
                    break
                n -= int(hijo.Count)
            elif n == 0:
                return hijo
            else:
                n -= 1
        else:
            raise IndexError("la página no está en el PDF")


def _objetos(obj, orden: list, vistos: set):
    """Los objetos que usa la página (contenido, fuentes, imágenes), sin subir a /Parent."""
    import pikepdf
    if isinstance(obj, pikepdf.Stream):
        hijos = obj.stream_dict.items()
    elif isinstance(obj, pikepdf.Dictionary):
        hijos = obj.items()
    elif isinstance(obj, pikepdf.Array):
        hijos = enumerate(obj)
    else:
        return
    for clave, valor in hijos:
        if clave == "/Parent" or not isinstance(valor, (pikepdf.Dictionary, pikepdf.Array, pikepdf.Stream)):
            continue
        if valor.is_indirect:
            if valor.objgen in vistos:
                continue
            vistos.add(valor.objgen)
            orden.append(valor)
        _objetos(valor, orden, vistos)


def _pdf_de_una_pagina(pdf, n: int) -> bytes:
    """Arma a mano un PDF con la página n (desde 0) y los objetos que usa."""
    import pikepdf
    hoja = _hoja(pdf, n)
    orden, vistos = [], {hoja.objgen}
    _objetos(hoja, orden, vistos)
    numeros = {hoja.objgen: 3, **{o.objgen: i + 4 for i, o in enumerate(orden)}}

    def renumerar(texto: bytes) -> bytes:
        return re.sub(rb"(\d+) (\d+) R",
                      lambda m: b"%d 0 R" % numeros.get((int(m.group(1)), int(m.group(2))), 0), texto)

    cuerpos = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               3: renumerar(re.sub(rb"/Parent \d+ \d+ R", b"/Parent 2 0 R", hoja.unparse(resolved=True)))}
    for o in orden:
        if isinstance(o, pikepdf.Stream):
            crudo = o.read_raw_bytes()
            dic = re.sub(rb"/Length \d+(?: \d+ R)?", b"/Length %d" % len(crudo), o.stream_dict.unparse())
            cuerpos[numeros[o.objgen]] = renumerar(dic) + b"\nstream\n" + crudo + b"\nendstream"
        else:
            cuerpos[numeros[o.objgen]] = renumerar(o.unparse(resolved=True))
    salida, posiciones = io.BytesIO(), {}
    salida.write(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    for num in sorted(cuerpos):
        posiciones[num] = salida.tell()
        salida.write(b"%d 0 obj\n%s\nendobj\n" % (num, cuerpos[num]))
    xref, total = salida.tell(), len(cuerpos) + 1
    salida.write(b"xref\n0 %d\n0000000000 65535 f \n" % total)
    salida.write(b"".join(b"%010d 00000 n \n" % posiciones[i] for i in range(1, total)))
    salida.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (total, xref))
    return salida.getvalue()


def pagina_png(url: str, pagina: int) -> tuple:
    """(imagen PNG de la página, total de páginas del PDF). `pagina` empieza en 1."""
    import pikepdf, pypdfium2 as pdfium
    with _candado_pdf:
        pdf = _abiertos.pop(url, None)
        if pdf is None:
            # inherit_page_attributes=False: si no, qpdf recorre todas las páginas al abrir
            pdf = pikepdf.open(_ArchivoRemoto(url), inherit_page_attributes=False)
        _abiertos[url] = pdf
        while len(_abiertos) > 3:
            _abiertos.popitem(last=False)[1].close()
        total = int(pdf.Root.Pages.Count)
        suelta = _pdf_de_una_pagina(pdf, max(1, min(pagina, total)) - 1)
    hoja = pdfium.PdfDocument(suelta)[0]
    imagen = hoja.render(scale=ANCHO / hoja.get_width()).to_pil()
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue(), total
