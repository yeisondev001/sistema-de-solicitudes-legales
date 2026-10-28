"""
Historial de expedientes (Reporte de Audiencia)
================================================
Usa PostgreSQL (Neon) cuando existe la variable de entorno DATABASE_URL.
Sin ella, guarda en un archivo SQLite local (historial.db) para trabajar
en la computadora sin configurar nada.
"""

import os, pathlib, sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH  = pathlib.Path(__file__).parent / "historial.db"

CAMPOS = (
    "tribunal", "fecha_audiencia", "expediente", "recurrente", "recurrido",
    "agrimensor", "objeto", "parcela", "fallo", "fecha_proxima",
)
CLAVE = ("expediente", "fecha_audiencia")   # mismo reporte = misma entrada

_COLUMNAS = ",\n".join(f"    {c} TEXT NOT NULL DEFAULT ''" for c in CAMPOS)
_DDL_POSTGRES = f"""
CREATE TABLE IF NOT EXISTS expedientes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
{_COLUMNAS},
    creado      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (expediente, fecha_audiencia)
)"""
_DDL_SQLITE = f"""
CREATE TABLE IF NOT EXISTS expedientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
{_COLUMNAS},
    creado      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (expediente, fecha_audiencia)
)"""

_tabla_lista = False


def _ejecutar(sql: str, params=(), leer=False):
    global _tabla_lista
    if DATABASE_URL:
        import psycopg
        conn = psycopg.connect(DATABASE_URL, connect_timeout=20)
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        sql  = sql.replace("%s", "?")
    try:
        cur = conn.cursor()
        if not _tabla_lista:
            cur.execute(_DDL_POSTGRES if DATABASE_URL else _DDL_SQLITE)
            _tabla_lista = True
        cur.execute(sql, params)
        filas = None
        if leer:
            nombres = [c[0] for c in cur.description]
            filas   = [dict(zip(nombres, f)) for f in cur.fetchall()]
        conn.commit()
        return filas
    finally:
        conn.close()


def guardar(entrada: dict):
    """Inserta el expediente o, si ya existe (mismo No. Exp y fecha), lo actualiza."""
    cols   = ", ".join(CAMPOS)
    marcas = ", ".join(["%s"] * len(CAMPOS))
    cambia = ", ".join(f"{c} = excluded.{c}" for c in CAMPOS if c not in CLAVE)
    _ejecutar(
        f"INSERT INTO expedientes ({cols}) VALUES ({marcas}) "
        f"ON CONFLICT (expediente, fecha_audiencia) DO UPDATE SET {cambia}, "
        f"actualizado = CURRENT_TIMESTAMP",
        tuple(entrada.get(c, "") for c in CAMPOS),
    )


def listar() -> list:
    """Expedientes en orden de creación (No.01 es el primero)."""
    return _ejecutar(f"SELECT id, {', '.join(CAMPOS)} FROM expedientes ORDER BY id", leer=True)


def borrar(id_: int):
    _ejecutar("DELETE FROM expedientes WHERE id = %s", (id_,))


def desde_reporte(form: dict) -> dict:
    """Convierte el formulario del Reporte de Audiencia en una entrada del historial."""
    tribunal = form.get("tribunal", "").strip()
    sala     = form.get("sala", "").strip()
    if sala and "tribunal" in sala.lower():
        tribunal = sala
    elif sala:
        tribunal = f"{sala}, {tribunal}" if tribunal else sala
    return {
        "tribunal":        tribunal,
        "fecha_audiencia": form.get("fecha_audiencia", "").strip(),
        "expediente":      form.get("expediente", "").strip(),
        "recurrente":      form.get("demandantes", "").strip(),
        "recurrido":       ", ".join(x.strip() for x in form.get("demandados", []) if x.strip()),
        "agrimensor":      form.get("agrimensor", "").strip(),
        "objeto":          form.get("asunto", "").strip(),
        "parcela":         form.get("parcela", "").strip(),
        "fallo":           form.get("fallo", "").strip(),
        "fecha_proxima":   form.get("fecha_proxima", "").strip(),
    }
