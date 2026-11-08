"""
Carga las leyes y reglamentos de jurisprudencia/leyes.py (hoy: la Ley 108-05 y los 4
reglamentos de 2022 de la Jurisdicción Inmobiliaria) y los libros de leyes comentadas (hoy:
la Ley 108-05 comentada por Registradores de Títulos) en la base principal, un documento
por artículo, y calcula sus vectores con Cloudflare (CF_ACCOUNT_ID, CF_API_TOKEN).

    python cargar_leyes.py                      # descarga las normas y los libros, los carga y calcula vectores
    python cargar_leyes.py --solo-comentarios   # solo los libros comentados (las leyes ya están)
    python cargar_leyes.py --probar             # solo lee los PDFs y dice cuántos artículos salen (sin base)
    python cargar_leyes.py --carpeta pdfs/      # usa PDFs ya descargados (mismo nombre que en la URL)
    python cargar_leyes.py --sin-vectores       # los vectores quedan para la carga diaria del Boletín
    python cargar_leyes.py --quitar-comentarios # borra los libros comentados (si el autor lo pide)

Se puede volver a correr: cada norma reemplaza sus artículos, no se duplican.
Van en la principal porque ocupan poco (~6 MB las leyes y ~4 MB el libro, con vectores) y ahí hay lugar.
"""

import argparse, sys, tempfile
from pathlib import Path

from jurisprudencia import basedatos, leyes
from jurisprudencia.boletin import descargar
from jurisprudencia.procesar import extraer_paginas, vectorizar_pendientes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--carpeta", help="carpeta con los PDFs ya descargados")
    ap.add_argument("--probar", action="store_true", help="solo leer los PDFs, sin tocar la base")
    ap.add_argument("--neuronas", type=float, default=3000, help="neuronas de Cloudflare para los vectores")
    ap.add_argument("--sin-vectores", action="store_true")
    ap.add_argument("--solo-comentarios", action="store_true", help="no vuelve a cargar las leyes")
    ap.add_argument("--quitar-comentarios", action="store_true", help="borra los libros comentados y termina")
    a = ap.parse_args()

    if not a.probar and not basedatos.configurada():
        sys.exit("Falta la variable JURIS_DATABASE_URL.")
    if a.quitar_comentarios:
        with basedatos.conectar() as conn:
            print(f"Se borraron {leyes.quitar_obras(conn)} comentarios.")
        return
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for norma in ([] if a.solo_comentarios else leyes.NORMAS) + leyes.OBRAS:
            es_obra = norma in leyes.OBRAS
            nombre = norma["url"].rsplit("/", 1)[-1]
            ruta = Path(a.carpeta or tmp) / nombre
            if not ruta.exists() and not descargar(norma["url"], ruta):
                print(f"{norma['corto']}: no se pudo descargar {norma['url']}")
                continue
            paginas = extraer_paginas(str(ruta))
            lista = leyes.comentarios(paginas, norma) if es_obra else leyes.articulos(paginas, norma)
            nums = [x["articulo"] for x in lista]
            faltan = [n for n in range(1, max(nums, default=0) + 1) if n not in nums]
            print(f"{'Comentario ' if es_obra else ''}{norma['corto']}: {len(lista)} artículos"
                  + (f" (faltan {faltan})" if faltan else ""))
            # si el lector falla (otro pdftotext, otro formato), mejor no reemplazar lo que hay
            if es_obra and len(lista) < 10:
                print(f"  salieron muy pocos comentarios: no se guarda nada de {norma['corto']}")
                import re   # pistas para corregir el lector
                for num, pag in paginas[99:102]:
                    print(f"  pág. {num}:", [l[:60] for l in pag.splitlines() if l.strip()][:4])
                print("  líneas con COMENTADOS:", sum(len(re.findall(r"COMENTADOS", p, re.I)) for _, p in paginas),
                      "con REFERENCIAS:", sum(len(re.findall(r"REFERENCIAS", p)) for _, p in paginas))
                continue
            if not a.probar:
                with basedatos.conectar() as conn:
                    (leyes.guardar_obra if es_obra else leyes.guardar_norma)(conn, norma, lista)
            total += len(lista)
    print(f"Listo: {total} artículos y comentarios.")
    if a.probar:
        return

    # no se recalculan las palabras comunes de la principal: con solo leyes saldrían comunes
    # "registro" o "inmueble", y la búsqueda por palabras dejaría de usarlas
    with basedatos.conectar() as conn:
        if not a.sin_vectores:
            r = vectorizar_pendientes(conn, max_neuronas=a.neuronas)
            if r["fragmentos"]:
                conn.commit()
                conn.autocommit = True
                conn.execute("VACUUM fragmentos")
            print(f"{r['fragmentos']} vectores nuevos"
                  + ("; se acabó la cuota de hoy, la carga diaria sigue mañana" if r["agotado"] else ""))
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*), COUNT(f.emb) FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
                           WHERE d.origen IN ('ley', 'doctrina')""" if basedatos.vector_tipo(conn) else
                        "SELECT COUNT(*), 0 FROM fragmentos f JOIN documentos d ON d.id = f.documento_id "
                        "WHERE d.origen IN ('ley', 'doctrina')")
            fragmentos, con_vector = cur.fetchone()
        print(f"Base principal: {con_vector} de {fragmentos} fragmentos de leyes y comentarios con vector, "
              f"{basedatos.tamano_mb(conn):.0f} MB")


if __name__ == "__main__":
    main()
