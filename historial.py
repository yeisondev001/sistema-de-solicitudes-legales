"""
Historial de expedientes (Reporte de Audiencia)
================================================
Usa PostgreSQL (Neon) cuando existe la variable de entorno DATABASE_URL.
Sin ella, guarda en un archivo SQLite local (historial.db) para trabajar
en la computadora sin configurar nada.
"""

import json, os, pathlib, sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH  = pathlib.Path(__file__).parent / "historial.db"

CAMPOS = (
    "tribunal", "fecha_audiencia", "expediente", "recurrente", "recurrido",
    "agrimensor", "objeto", "parcela", "fallo", "fecha_proxima",
)
CLAVE = ("expediente", "fecha_audiencia")   # mismo reporte = misma entrada
# Además se guarda el formulario completo (columna "datos", JSON) para poder
# editar un reporte o usarlo como base de uno nuevo.

_COLUMNAS = ",\n".join(f"    {c} TEXT NOT NULL DEFAULT ''" for c in CAMPOS)
_DDL_POSTGRES = f"""
CREATE TABLE IF NOT EXISTS expedientes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
{_COLUMNAS},
    datos       TEXT NOT NULL DEFAULT '',
    creado      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (expediente, fecha_audiencia)
)"""
_DDL_SQLITE = f"""
CREATE TABLE IF NOT EXISTS expedientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
{_COLUMNAS},
    datos       TEXT NOT NULL DEFAULT '',
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
            _agregar_columna_datos(cur)
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


def _agregar_columna_datos(cur):
    """Tablas creadas antes de existir la columna "datos"."""
    if DATABASE_URL:
        cur.execute("ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS datos TEXT NOT NULL DEFAULT ''")
    else:
        try:
            cur.execute("ALTER TABLE expedientes ADD COLUMN datos TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass   # ya existe


def guardar(entrada: dict, datos: dict = None, id_: int = None):
    """
    Con id_: actualiza ese expediente (modo editar).
    Sin id_: inserta, o actualiza si ya existe el mismo No. Exp con la misma fecha.
    """
    columnas = CAMPOS + ("datos",)
    valores  = tuple(entrada.get(c, "") for c in CAMPOS) + (json.dumps(datos or {}, ensure_ascii=False),)
    if id_:
        asignar = ", ".join(f"{c} = %s" for c in columnas)
        _ejecutar(f"UPDATE expedientes SET {asignar}, actualizado = CURRENT_TIMESTAMP WHERE id = %s",
                  valores + (id_,))
        return
    marcas = ", ".join(["%s"] * len(columnas))
    cambia = ", ".join(f"{c} = excluded.{c}" for c in columnas if c not in CLAVE)
    _ejecutar(
        f"INSERT INTO expedientes ({', '.join(columnas)}) VALUES ({marcas}) "
        f"ON CONFLICT (expediente, fecha_audiencia) DO UPDATE SET {cambia}, "
        f"actualizado = CURRENT_TIMESTAMP",
        valores,
    )


def listar() -> list:
    """Expedientes en orden de creación (No.01 es el primero), con el formulario en "datos"."""
    filas = _ejecutar(f"SELECT id, {', '.join(CAMPOS)}, datos FROM expedientes ORDER BY id", leer=True)
    for f in filas:
        try:
            f["datos"] = json.loads(f["datos"] or "{}")
        except ValueError:
            f["datos"] = {}
    return filas


def contar() -> int:
    return _ejecutar("SELECT COUNT(*) AS n FROM expedientes", leer=True)[0]["n"]


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
