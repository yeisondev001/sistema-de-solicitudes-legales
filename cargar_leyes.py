"""
Carga las leyes y reglamentos de jurisprudencia/leyes.py (hoy: la Ley 108-05 y los 4
reglamentos de 2022 de la Jurisdicción Inmobiliaria) en la base principal, un documento
por artículo, y calcula sus vectores con Cloudflare (CF_ACCOUNT_ID, CF_API_TOKEN).

    python cargar_leyes.py                      # descarga las 5 normas, las carga y calcula vectores
    python cargar_leyes.py --probar             # solo lee los PDFs y dice cuántos artículos salen (sin base)
    python cargar_leyes.py --carpeta pdfs/      # usa PDFs ya descargados (mismo nombre que en la URL)
    python cargar_leyes.py --sin-vectores       # los vectores quedan para la carga diaria del Boletín

Se puede volver a correr: cada norma reemplaza sus artículos, no se duplican.
Van en la principal porque ocupan poco (~15 MB con vectores) y ahí hay lugar.
"""

import argparse, sys, tempfile
from pathlib import Path

from jurisprudencia import basedatos, leyes
from jurisprudencia.boletin import descargar
from jurisprudencia.procesar import vectorizar_pendientes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--carpeta", help="carpeta con los PDFs ya descargados")
    ap.add_argument("--probar", action="store_true", help="solo leer los PDFs, sin tocar la base")
    ap.add_argument("--neuronas", type=float, default=3000, help="neuronas de Cloudflare para los vectores")
    ap.add_argument("--sin-vectores", action="store_true")
    a = ap.parse_args()

    if not a.probar and not basedatos.configurada():
        sys.exit("Falta la variable JURIS_DATABASE_URL.")
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for norma in leyes.NORMAS:
            nombre = norma["url"].rsplit("/", 1)[-1]
            ruta = Path(a.carpeta or tmp) / nombre
            if not ruta.exists() and not descargar(norma["url"], ruta):
                print(f"{norma['corto']}: no se pudo descargar {norma['url']}")
                continue
            lista = leyes.leer(str(ruta), norma)
            nums = [x["articulo"] for x in lista]
            faltan = [n for n in range(1, max(nums, default=0) + 1) if n not in nums]
            print(f"{norma['corto']}: {len(lista)} artículos" + (f" (faltan {faltan})" if faltan else ""))
            if not a.probar:
                with basedatos.conectar() as conn:
                    leyes.guardar_norma(conn, norma, lista)
            total += len(lista)
    print(f"Listo: {total} artículos.")
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
                           WHERE d.origen = 'ley'""" if basedatos.vector_tipo(conn) else
                        "SELECT COUNT(*), 0 FROM fragmentos f JOIN documentos d ON d.id = f.documento_id "
                        "WHERE d.origen = 'ley'")
            fragmentos, con_vector = cur.fetchone()
        print(f"Base principal: {con_vector} de {fragmentos} fragmentos de leyes con vector, "
              f"{basedatos.tamano_mb(conn):.0f} MB")


if __name__ == "__main__":
    main()
