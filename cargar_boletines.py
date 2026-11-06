"""
Carga el Boletín Judicial en las bases de jurisprudencia (JURIS_DATABASE_URL y, si
hay, JURIS_ARCHIVO_URLS) y calcula los vectores que falten con Cloudflare
(CF_ACCOUNT_ID, CF_API_TOKEN).

    python cargar_boletines.py                      # últimos 60 meses publicados que falten + vectores del día
    python cargar_boletines.py --meses 12           # solo los últimos 12 meses publicados
    python cargar_boletines.py --mes 2025-05        # un mes concreto
    python cargar_boletines.py --mes 2025-05 --pdf MAYO.pdf   # con un PDF ya descargado
    python cargar_boletines.py --solo-vectores      # no descarga nada, solo vectores

El Boletín sale con más de un año de atraso, así que los meses se cuentan desde el
último publicado. Los meses ya cargados se saltan, así que se puede correr todos los días:
los nuevos se van sumando y no se borra nada (salvo que se pida con --conservar).
Cada mes va a la primera base con espacio: primero las de archivo y al final la principal,
que se deja con lugar para los documentos de los usuarios.
"""

import argparse, datetime, sys, tempfile
from pathlib import Path

from jurisprudencia import basedatos, boletin
from jurisprudencia.procesar import PRIORITARIOS, vectorizar_pendientes

MAX_ESPERA = 36   # meses sin publicar que se aceptan antes del último boletín


def meses_publicados(cuantos: int) -> list:
    """[(año, mes, url o None)] de los últimos `cuantos` meses, desde el último Boletín publicado."""
    hoy = datetime.date.today()
    anio, mes, lista, sin_publicar = hoy.year, hoy.month, [], 0
    while len(lista) < cuantos and sin_publicar <= MAX_ESPERA:
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
        url = boletin.buscar_url(anio, mes)
        if url is None and not lista:
            sin_publicar += 1    # todavía no se llega al último publicado
            continue
        lista.append((anio, mes, url))
    return lista


def _nombre(i: int) -> str:
    return "principal" if i == 0 else f"archivo {i}"


def borrar_viejos(urls: list, desde: tuple) -> list:
    """Quita los boletines anteriores a `desde` (año, mes); devuelve las bases que liberaron espacio."""
    liberadas = []
    for i, url in enumerate(urls):
        with basedatos.conectar(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT fuente_url FROM documentos WHERE origen = 'boletin'")
                viejos = [u for (u,) in cur.fetchall() if (boletin.mes_de_url(u) or desde) < desde]
                if not viejos:
                    continue
                cur.execute("DELETE FROM documentos WHERE origen = 'boletin' AND fuente_url = ANY(%s)", (viejos,))
                print(f"Base {_nombre(i)}: se quitaron {cur.rowcount} sentencias de {len(viejos)} meses viejos.")
                cur.execute("DELETE FROM boletines_cargados WHERE fuente_url = ANY(%s)", (viejos,))
            conn.commit()
            # VACUUM deja el espacio listo para el mes nuevo (la base no se achica, pero se reusa)
            conn.autocommit = True
            conn.execute("VACUUM documentos, fragmentos")
            liberadas.append(url)
    return liberadas


def elegir_base(orden: list, liberadas: list):
    """Primera base donde cabe un mes más contando los vectores que faltan; si todas están
    llenas, una que acaba de liberar espacio."""
    for url in orden:
        with basedatos.conectar(url) as conn:
            if basedatos.tamano_final_mb(conn) + basedatos.MARGEN_MES_MB <= basedatos.limite_mb(url):
                return url
    return liberadas.pop(0) if liberadas else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meses", type=int, default=60, help="cuántos meses publicados hacia atrás (por defecto 60)")
    ap.add_argument("--mes", help="un mes concreto, AAAA-MM")
    ap.add_argument("--pdf", help="usar este PDF en vez de descargarlo (con --mes)")
    ap.add_argument("--max-meses", type=int, default=12, help="máximo de meses a descargar en esta corrida")
    ap.add_argument("--neuronas", type=float, default=7000,
                    help="neuronas de Cloudflare para vectores en esta corrida (deja el resto para respuestas)")
    ap.add_argument("--conservar", type=int, default=0,
                    help="borra los boletines más viejos que estos meses publicados (por defecto 0: no borra nada)")
    ap.add_argument("--solo-vectores", action="store_true")
    ap.add_argument("--sin-vectores", action="store_true")
    a = ap.parse_args()

    if not basedatos.configurada():
        sys.exit("Falta la variable JURIS_DATABASE_URL.")
    urls = basedatos.bases()
    for i, url in enumerate(urls):
        with basedatos.conectar(url) as conn:
            tipo = basedatos.vector_tipo(conn)
            print(f"Base {_nombre(i)}: {basedatos.tamano_mb(conn):.0f} MB "
                  f"({basedatos.tamano_final_mb(conn):.0f} MB con todos los vectores) de {basedatos.limite_mb(url):.0f}, "
                  f"vectores {tipo or 'no disponibles'}"
                  + (" con índice binario" if basedatos.indice_binario(conn) else ""))

    if not a.solo_vectores:
        if a.mes:
            anio, mes = (int(x) for x in a.mes.split("-"))
            # aunque el PDF ya esté descargado, se guarda la URL real (el enlace "ver en el Boletín")
            lista = [(anio, mes, boletin.buscar_url(anio, mes) or boletin.url_mes(anio, mes))]
        else:
            todos = meses_publicados(max(a.meses, a.conservar))
            if todos:
                print(f"Último Boletín publicado: {todos[0][0]}-{todos[0][1]:02d}")
            lista = todos[:a.meses]

        cambiadas, liberadas = set(), []
        # se conservan solo los últimos N meses publicados, para no llenar las bases
        if not a.mes and a.conservar and len(todos) >= a.conservar:
            anio, mes, _ = todos[a.conservar - 1]
            liberadas = borrar_viejos(urls, (anio, mes))
            cambiadas.update(liberadas)

        cargados = {}   # url del boletín -> base donde está
        for url in urls:
            for f in basedatos.consultar("SELECT fuente_url FROM boletines_cargados", url=url):
                cargados[f["fuente_url"]] = url
        orden_carga = urls[1:] + urls[:1]   # la principal al final
        descargados = 0
        with tempfile.TemporaryDirectory() as tmp:
            for anio, mes, url in lista:
                if url is None or (url in cargados and not a.pdf):
                    continue
                if descargados >= a.max_meses:
                    print("Se alcanzó --max-meses; el resto queda para la próxima corrida.")
                    break
                destino = cargados.get(url) or elegir_base(orden_carga, liberadas)
                if destino is None:
                    print("Todas las bases están llenas: agregue otro proyecto en JURIS_ARCHIVO_URLS.")
                    break
                print(f"{anio}-{mes:02d}: {url} -> base {_nombre(urls.index(destino))}")
                if a.pdf:
                    ruta = Path(a.pdf)
                else:
                    ruta = Path(tmp) / f"{anio}-{mes:02d}.pdf"
                    if not boletin.descargar(url, ruta):
                        print("  no se pudo descargar")
                        continue
                    descargados += 1
                with basedatos.conectar(destino) as conn:
                    nuevas = boletin.cargar_pdf(conn, str(ruta), url)
                print(f"  {nuevas} sentencias nuevas guardadas")
                cargados[url] = destino
                cambiadas.add(destino)
                if not a.pdf:
                    ruta.unlink(missing_ok=True)
        for url in cambiadas:
            with basedatos.conectar(url) as conn:
                n = basedatos.actualizar_terminos_comunes(conn)
            print(f"Base {_nombre(urls.index(url))}: {n} palabras comunes")

    if not a.sin_vectores:
        restantes, hechos = a.neuronas, [0] * len(urls)
        # primero Tierras e Inmobiliario en todas las bases, después el resto
        for solo_prioritarios in (True, False):
            for i, url in enumerate(urls):
                if restantes <= 0:
                    break
                with basedatos.conectar(url) as conn:
                    r = vectorizar_pendientes(conn, max_neuronas=restantes, solo_prioritarios=solo_prioritarios)
                    if r["fragmentos"]:
                        # cada vector reescribe su fila: VACUUM deja reusable el lugar de las versiones viejas
                        # (si no, la base crece el doble hasta que Postgres limpie por su cuenta)
                        conn.commit()   # la última consulta deja una transacción abierta
                        conn.autocommit = True
                        conn.execute("VACUUM fragmentos")
                restantes -= r["neuronas"]
                hechos[i] += r["fragmentos"]
                if r["agotado"]:
                    restantes = 0
        if restantes <= 0:
            print("Se acabó la cuota de vectores de hoy; sigue mañana.")
        for i, url in enumerate(urls):
            with basedatos.conectar(url) as conn, conn.cursor() as cur:
                cur.execute(f"""SELECT COUNT(*), COUNT(f.emb), COUNT(*) FILTER (WHERE {PRIORITARIOS}),
                                       COUNT(f.emb) FILTER (WHERE {PRIORITARIOS})
                                FROM fragmentos f JOIN documentos d ON d.id = f.documento_id"""
                            if basedatos.vector_tipo(conn) else
                            "SELECT COUNT(*), 0, 0, 0 FROM fragmentos")
                total, con_vector, tierras, tierras_con = cur.fetchone()
                print(f"Base {_nombre(i)}: {hechos[i]} vectores nuevos; {con_vector} de {total} fragmentos con "
                      f"vector (Tierras e Inmobiliario: {tierras_con} de {tierras}), {basedatos.tamano_mb(conn):.0f} MB "
                      f"({basedatos.tamano_final_mb(conn):.0f} MB con todos los vectores)")


if __name__ == "__main__":
    main()
