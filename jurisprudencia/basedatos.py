"""
Base de datos de jurisprudencia (PostgreSQL, variable JURIS_DATABASE_URL).
Va separada del historial para no llenar su espacio gratis.
Los documentos del Boletín Judicial tienen usuario_id NULL (los ve todo el mundo);
los documentos subidos por un usuario solo los ve ese usuario.

Cuando el Boletín no cabe en el 1 GB gratis de un proyecto de Neon, se agregan más
proyectos en JURIS_ARCHIVO_URLS (separados por espacios o comas): todas las bases
tienen las mismas tablas, el cargador las va llenando y el buscador busca en todas.
Los documentos de los usuarios van siempre en la principal.
"""

import os, re

def _cadenas(texto: str) -> list:
    """Cadenas de conexión que hay en el texto; se ignora lo demás (por ejemplo, el nombre
    del proyecto pegado delante: "jurisprudencia-archivo-1, postgresql://...")."""
    return [u for u in re.split(r"[\s,;]+", texto) if u.startswith(("postgresql://", "postgres://"))]


# También se pueden poner todas en una sola variable: la primera es la principal
_todas = list(dict.fromkeys(_cadenas(os.environ.get("JURIS_DATABASE_URL", ""))
                            + _cadenas(os.environ.get("JURIS_ARCHIVO_URLS", ""))))
JURIS_DATABASE_URL = _todas[0] if _todas else ""
JURIS_ARCHIVO_URLS = _todas[1:]
LIMITE_MB = int(os.environ.get("JURIS_LIMITE_MB", "870"))   # Neon gratis: 1 GB por proyecto
RESERVA_MB = 200    # en la principal se deja lugar para los documentos que suben los usuarios

_DDL = [
    # quita tildes para que "casación" y "casacion" coincidan (sin depender de extensiones)
    """CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
       LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
       AS $$ SELECT translate($1, 'áéíóúüÁÉÍÓÚÜ', 'aeiouuAEIOUU') $$""",
    """CREATE TABLE IF NOT EXISTS documentos (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        usuario_id  BIGINT,
        origen      TEXT NOT NULL,
        titulo      TEXT NOT NULL DEFAULT '',
        numero      TEXT NOT NULL DEFAULT '',
        expediente  TEXT NOT NULL DEFAULT '',
        sala        TEXT NOT NULL DEFAULT '',
        materia     TEXT NOT NULL DEFAULT '',
        decision    TEXT NOT NULL DEFAULT '',
        fecha       TEXT NOT NULL DEFAULT '',
        fuente_url  TEXT NOT NULL DEFAULT '',
        pagina      INT  NOT NULL DEFAULT 1,
        creado      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    "CREATE INDEX IF NOT EXISTS documentos_usuario ON documentos (usuario_id)",
    """CREATE UNIQUE INDEX IF NOT EXISTS documentos_boletin_unico
       ON documentos (numero, fuente_url) WHERE origen = 'boletin'""",
    """CREATE TABLE IF NOT EXISTS fragmentos (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        documento_id BIGINT NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
        orden   INT  NOT NULL,
        pagina  INT  NOT NULL,
        texto   TEXT NOT NULL,
        tsv     tsvector GENERATED ALWAYS AS (to_tsvector('spanish', f_unaccent(texto))) STORED)""",
    "CREATE INDEX IF NOT EXISTS fragmentos_tsv ON fragmentos USING GIN (tsv)",
    "CREATE INDEX IF NOT EXISTS fragmentos_documento ON fragmentos (documento_id)",
    # meses del Boletín ya cargados por completo (para no descargarlos otra vez)
    """CREATE TABLE IF NOT EXISTS boletines_cargados (
        fuente_url  TEXT PRIMARY KEY,
        sentencias  INT  NOT NULL,
        cargado     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    # palabras que salen en casi todas las sentencias ("casación", "tribunal"…): no sirven
    # para distinguir y harían la búsqueda por palabras muy lenta
    "CREATE TABLE IF NOT EXISTS terminos_comunes (palabra TEXT PRIMARY KEY)",
]
_listas = set()

# Vectores de significado (pgvector). En Neon (pgvector 0.7+) se guardan en media
# precisión (halfvec, 2 KB por fragmento) con un índice binario liviano; con versiones
# viejas se usa vector normal sin índice.
DIMENSIONES = 1024
_vectores = {}      # base -> (tipo: "halfvec", "vector" o None, ¿tiene índice binario?)


def configurada() -> bool:
    return bool(JURIS_DATABASE_URL)


def bases() -> list:
    """Todas las bases: la principal primero."""
    return [JURIS_DATABASE_URL] + JURIS_ARCHIVO_URLS if JURIS_DATABASE_URL else []


def clave(conn) -> tuple:
    """Identifica la base de una conexión (sin la contraseña)."""
    return conn.info.host, conn.info.port, conn.info.dbname


def vector_tipo(conn):
    return _vectores.get(clave(conn), (None, False))[0]


def indice_binario(conn) -> bool:
    return _vectores.get(clave(conn), (None, False))[1]


def _preparar_vectores(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("SELECT 1 FROM pg_type WHERE typname = 'halfvec'")
            tipo = "halfvec" if cur.fetchone() else "vector"
            cur.execute(f"ALTER TABLE fragmentos ADD COLUMN IF NOT EXISTS emb {tipo}({DIMENSIONES})")
            cur.execute("SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                        "WHERE attrelid = 'fragmentos'::regclass AND attname = 'emb'")
            tipo = cur.fetchone()[0].split("(")[0]
            if tipo == "halfvec":
                cur.execute(f"""CREATE INDEX IF NOT EXISTS fragmentos_emb_bin ON fragmentos
                    USING hnsw ((binary_quantize(emb)::bit({DIMENSIONES})) bit_hamming_ops)""")
        conn.commit()
        _vectores[clave(conn)] = (tipo, tipo == "halfvec")
    except Exception:
        conn.rollback()
        _vectores[clave(conn)] = (None, False)


def conectar(url: str = None):
    """Conexión lista para usar (crea las tablas la primera vez). Sin url: la principal."""
    import psycopg
    url = url or JURIS_DATABASE_URL
    conn = psycopg.connect(url, connect_timeout=20)
    if url not in _listas:
        with conn.cursor() as cur:
            for ddl in _DDL:
                cur.execute(ddl)
        conn.commit()
        _preparar_vectores(conn)
        _listas.add(url)
    return conn


def tamano_mb(conn) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database())")
        return cur.fetchone()[0] / 2 ** 20


def limite_mb(url: str) -> float:
    return LIMITE_MB - (RESERVA_MB if url == JURIS_DATABASE_URL else 0)


def actualizar_terminos_comunes(conn, proporcion: float = 0.2) -> int:
    """Recalcula las palabras que aparecen en más del 20 % de los fragmentos."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM terminos_comunes")
        cur.execute("""INSERT INTO terminos_comunes (palabra)
                       SELECT word FROM ts_stat('SELECT tsv FROM fragmentos')
                       WHERE ndoc > %s * (SELECT COUNT(*) FROM fragmentos)""", (proporcion,))
        n = cur.rowcount
    conn.commit()
    return n


def filas(conn, sql: str, params=()) -> list:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        nombres = [c[0] for c in cur.description]
        return [dict(zip(nombres, f)) for f in cur.fetchall()]


def consultar(sql: str, params=(), url: str = None) -> list:
    with conectar(url) as conn:
        return filas(conn, sql, params)


def ejecutar(sql: str, params=(), url: str = None):
    with conectar(url) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
