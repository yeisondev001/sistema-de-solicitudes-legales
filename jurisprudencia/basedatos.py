"""
Base de datos de jurisprudencia (PostgreSQL, variable JURIS_DATABASE_URL).
Va separada del historial para no llenar su espacio gratis.
Los documentos del Boletín Judicial tienen usuario_id NULL (los ve todo el mundo);
los documentos subidos por un usuario solo los ve ese usuario.
"""

import os

JURIS_DATABASE_URL = os.environ.get("JURIS_DATABASE_URL", "").strip()

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
]
_lista = False


def configurada() -> bool:
    return bool(JURIS_DATABASE_URL)


def conectar():
    """Conexión lista para usar (crea las tablas la primera vez)."""
    global _lista
    import psycopg
    conn = psycopg.connect(JURIS_DATABASE_URL, connect_timeout=20)
    if not _lista:
        with conn.cursor() as cur:
            for ddl in _DDL:
                cur.execute(ddl)
        conn.commit()
        _lista = True
    return conn


def consultar(sql: str, params=()) -> list:
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        nombres = [c[0] for c in cur.description]
        return [dict(zip(nombres, f)) for f in cur.fetchall()]


def ejecutar(sql: str, params=()):
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
