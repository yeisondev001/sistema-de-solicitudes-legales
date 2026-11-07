# %% [markdown]
# # Huellas (vectores) del Boletín Judicial con la GPU de Kaggle
#
# Calcula una sola vez las huellas de todos los fragmentos del Boletín que todavía no tienen,
# con el mismo modelo que usa Cloudflare (Qwen3-Embedding-0.6B, que es abierto), y las guarda
# en las bases de Neon. Después la carga diaria de GitHub sigue con Cloudflare solo para los
# meses nuevos.
#
# **Antes de correrlo**
# 1. *Settings* (panel derecho) → **Accelerator: GPU T4 x2** e **Internet: On**
#    (Kaggle pide verificar el teléfono para las dos cosas).
# 2. *Add-ons → Secrets* → **Add secret** con el nombre `JURIS_URLS` y como valor las cadenas
#    `postgresql://...` de todas las bases (las mismas de `JURIS_DATABASE_URL` en Render; pueden ir
#    con su nombre delante o separadas por espacios o renglones). Marque la casilla para que el
#    cuaderno lo pueda leer.
# 3. **Save Version → Save & Run All (Commit)**: corre en segundo plano aunque se cierre el navegador.
#
# Primero compara 64 huellas con las que ya calculó Cloudflare: si no salen iguales, se detiene sin
# guardar nada. Solo toca el Boletín: los documentos que suben los usuarios no salen de Cloudflare.
# Si se corta (límite de horas de Kaggle), se vuelve a correr y sigue donde quedó.

# %%
import importlib.util, subprocess, sys

if importlib.util.find_spec("psycopg") is None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "psycopg[binary]"], check=True)
import transformers
if tuple(int(x) for x in transformers.__version__.split(".")[:2]) < (4, 51):   # Qwen3 necesita 4.51+
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers>=4.51"], check=True)
    sys.exit("Se actualizó transformers: vuelva a correr el cuaderno (Run All).")

import os, re, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np, psycopg, torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

MODELO = "Qwen/Qwen3-Embedding-0.6B"
MAX_CARACTERES = 6000     # lo mismo que se le manda a Cloudflare (jurisprudencia/vectores.py)
TANDA = 2048              # fragmentos que se leen, calculan y guardan juntos
TOKENS_POR_LOTE = 24000   # tamaño de cada lote en la GPU
LIMITE_MB = 990           # Neon gratis llega a 1 GB por proyecto (y cuenta ~24 MB más)
VACUUM_CADA = 5           # tandas entre cada VACUUM: cada huella reescribe su fila y así se reusa el lugar
# como en jurisprudencia/procesar.py: primero Tierras e Inmobiliario
PRIORITARIOS = r"(d.materia || ' ' || d.titulo) ~* 'tierra|inmobiliari|deslinde|saneamiento|registrad|litis'"


def leer_urls():
    texto = os.environ.get("JURIS_URLS", "")
    if not texto:
        from kaggle_secrets import UserSecretsClient
        texto = UserSecretsClient().get_secret("JURIS_URLS")
    urls = [u for u in re.split(r"[\s,;]+", texto) if u.startswith(("postgresql://", "postgres://"))]
    return list(dict.fromkeys(urls))


URLS = leer_urls()
assert URLS, "El secreto JURIS_URLS no tiene ninguna cadena postgresql://"
print(f"{len(URLS)} bases")

# %%
GPUS = [f"cuda:{i}" for i in range(torch.cuda.device_count())] or ["cpu"]
tipo_num = torch.float16 if GPUS[0] != "cpu" else torch.float32
tok = AutoTokenizer.from_pretrained(MODELO, padding_side="left")
modelos = [AutoModel.from_pretrained(MODELO).to(device=g, dtype=tipo_num).eval() for g in GPUS]
print("Calculando en:", ", ".join(torch.cuda.get_device_name(i) for i in range(len(GPUS))) if GPUS[0] != "cpu"
      else "procesador (sin GPU: va a ser muy lento)")


def _lotes(textos):
    """Índices agrupados por largo parecido, para no rellenar de más."""
    largos = [len(tok(t, truncation=True, max_length=8192)["input_ids"]) for t in textos]
    orden = sorted(range(len(textos)), key=lambda i: largos[i])
    lote, maximo = [], 0
    for i in orden:
        if lote and max(maximo, largos[i]) * (len(lote) + 1) > TOKENS_POR_LOTE:
            yield lote
            lote, maximo = [], 0
        lote.append(i)
        maximo = max(maximo, largos[i])
    if lote:
        yield lote


def _en_gpu(modelo, textos):
    b = tok(textos, padding=True, truncation=True, max_length=8192, return_tensors="pt").to(modelo.device)
    with torch.no_grad():
        h = modelo(**b).last_hidden_state[:, -1]   # relleno a la izquierda: el último token es el de cada texto
    return F.normalize(h.float(), p=2, dim=1).cpu().numpy()


def huellas(textos):
    """Una huella normalizada por texto, repartiendo los lotes entre las GPU."""
    salida = np.zeros((len(textos), 1024), dtype=np.float32)
    lotes = list(_lotes(textos))
    with ThreadPoolExecutor(len(modelos)) as hilos:
        for n in range(0, len(lotes), len(modelos)):
            grupo = lotes[n:n + len(modelos)]
            for lote, vec in zip(grupo, hilos.map(lambda par: _en_gpu(par[0], [textos[i] for i in par[1]]),
                                                  zip(modelos, grupo))):
                salida[lote] = vec
    return salida


def texto_de(texto, numero, sala, materia):
    # la cabecera (número, sala, materia) igual que en jurisprudencia/procesar.py
    return (" · ".join(p for p in (numero, sala, materia) if p) + "\n" + texto)[:MAX_CARACTERES]


def como_texto(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

# %% [markdown]
# ## 1. Comparación con Cloudflare

# %%
def comparar(n=64):
    for url in URLS:
        with psycopg.connect(url, connect_timeout=30) as c:
            filas = c.execute("""SELECT f.texto, d.numero, d.sala, d.materia, f.emb::text
                                 FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
                                 WHERE f.emb IS NOT NULL AND d.origen = 'boletin'
                                 ORDER BY random() LIMIT %s""", (n,)).fetchall()
        if len(filas) >= 16:
            break
    else:
        print("Ninguna base tiene huellas de Cloudflare para comparar; se sigue sin comparación.")
        return
    nube = np.array([[float(x) for x in e.strip("[]").split(",")] for *_, e in filas], dtype=np.float32)
    nube /= np.linalg.norm(nube, axis=1, keepdims=True)
    textos = [texto_de(*f[:4]) for f in filas]
    coseno = np.nan_to_num((nube * huellas(textos)).sum(axis=1), nan=-1)
    print(f"{len(filas)} huellas comparadas con Cloudflare: similitud promedio {coseno.mean():.4f}, "
          f"mínima {coseno.min():.4f}")
    if coseno.min() < 0.99 and modelos[0].dtype == torch.float16:
        print("En media precisión no salen iguales: se prueba en precisión completa (más lento).")
        for m in modelos:
            m.float()
        coseno = np.nan_to_num((nube * huellas(textos)).sum(axis=1), nan=-1)
        print(f"  similitud promedio {coseno.mean():.4f}, mínima {coseno.min():.4f}")
    assert coseno.min() >= 0.99, "Las huellas no salen iguales a las de Cloudflare: no se guarda nada."
    print("Salen iguales: se sigue.")


comparar(int(os.environ.get("HUELLAS_COMPARAR", "64")))

# %% [markdown]
# ## 2. Cálculo y guardado

# %%
def tamano_mb(url):
    with psycopg.connect(url, connect_timeout=30) as c:
        return c.execute("SELECT pg_database_size(current_database())").fetchone()[0] / 2 ** 20


def vacuum(url):
    with psycopg.connect(url, connect_timeout=30, autocommit=True) as c:
        c.execute("VACUUM fragmentos")


def guardar(url, ids, vectores):
    with psycopg.connect(url, connect_timeout=30) as c, c.cursor() as cur:
        cur.execute("CREATE TEMP TABLE _huellas (id BIGINT PRIMARY KEY, emb TEXT) ON COMMIT DROP")
        with cur.copy("COPY _huellas (id, emb) FROM STDIN") as copia:
            for i, v in zip(ids, vectores):
                copia.write_row((i, como_texto(v)))
        # halfvec en Neon; vector en Postgres con pgvector viejo
        tipo = cur.execute("""SELECT format_type(atttypid, atttypmod) FROM pg_attribute
                              WHERE attrelid = 'fragmentos'::regclass AND attname = 'emb'""").fetchone()[0]
        cur.execute(f"""UPDATE fragmentos f SET emb = h.emb::{tipo} FROM _huellas h
                        WHERE f.id = h.id AND f.emb IS NULL""")
        return cur.rowcount


def procesar(i, url):
    nombre = "principal" if i == 0 else f"archivo {i}"
    with psycopg.connect(url, connect_timeout=30) as c:
        pendientes = [r[0] for r in c.execute(f"""
            SELECT f.id FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
            WHERE f.emb IS NULL AND d.origen = 'boletin'
            ORDER BY {PRIORITARIOS} DESC, f.id DESC""").fetchall()]
    pendientes = pendientes[:int(os.environ.get("HUELLAS_MAXIMO", "0")) or None]   # para probar con pocos
    print(f"\nBase {nombre}: {len(pendientes)} fragmentos sin huella, {tamano_mb(url):.0f} MB")
    hechos, inicio = 0, time.time()
    for t, desde in enumerate(range(0, len(pendientes), TANDA), start=1):
        if tamano_mb(url) > LIMITE_MB:
            print(f"  La base llegó a {LIMITE_MB} MB: se detiene aquí para no llenarla.")
            break
        ids = pendientes[desde:desde + TANDA]
        with psycopg.connect(url, connect_timeout=30) as c:
            filas = c.execute("""SELECT f.id, f.texto, d.numero, d.sala, d.materia
                                 FROM fragmentos f JOIN documentos d ON d.id = f.documento_id
                                 WHERE f.id = ANY(%s) AND f.emb IS NULL""", (ids,)).fetchall()
        if not filas:
            continue
        vectores = huellas([texto_de(*f[1:]) for f in filas])
        buenos = np.isfinite(vectores).all(axis=1)   # si alguno sale mal, lo deja para Cloudflare
        hechos += guardar(url, [f[0] for f, ok in zip(filas, buenos) if ok], vectores[buenos])
        if t % VACUUM_CADA == 0:
            vacuum(url)
        seg = time.time() - inicio
        falta = seg / (desde + len(ids)) * (len(pendientes) - desde - len(ids))
        print(f"  {hechos}/{len(pendientes)} ({seg / 60:.0f} min; faltan ~{falta / 60:.0f} min)", flush=True)
    if hechos:
        vacuum(url)
    print(f"Base {nombre}: {hechos} huellas nuevas, {tamano_mb(url):.0f} MB")
    return hechos


total = sum(procesar(i, url) for i, url in enumerate(URLS))
print(f"\nListo: {total} huellas nuevas en total.")
