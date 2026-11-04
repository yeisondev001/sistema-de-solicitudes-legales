"""
Cuentas de usuario y sesiones
=============================
Misma base que el historial: PostgreSQL (DATABASE_URL) o SQLite local.
Las contraseñas se guardan con scrypt (nunca en texto plano).
"""

import hashlib, hmac, os, secrets, sqlite3, time

from historial import DATABASE_URL, SQLITE_PATH

DURACION_SESION = 30 * 24 * 3600   # 30 días

_DDL = {
    "postgres": [
        """CREATE TABLE IF NOT EXISTS usuarios (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            usuario TEXT NOT NULL UNIQUE,
            nombre  TEXT NOT NULL DEFAULT '',
            clave   TEXT NOT NULL,
            es_admin BOOLEAN NOT NULL DEFAULT FALSE,
            activo   BOOLEAN NOT NULL DEFAULT TRUE,
            creado  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS sesiones (
            token TEXT PRIMARY KEY,
            usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            vence BIGINT NOT NULL)""",
    ],
    "sqlite": [
        """CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            nombre  TEXT NOT NULL DEFAULT '',
            clave   TEXT NOT NULL,
            es_admin INTEGER NOT NULL DEFAULT 0,
            activo   INTEGER NOT NULL DEFAULT 1,
            creado  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS sesiones (
            token TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            vence INTEGER NOT NULL)""",
    ],
}
_tablas_listas = False


def _ejecutar(sql: str, params=(), leer=False):
    global _tablas_listas
    if DATABASE_URL:
        import psycopg
        conn, motor = psycopg.connect(DATABASE_URL, connect_timeout=20), "postgres"
    else:
        conn, motor = sqlite3.connect(SQLITE_PATH), "sqlite"
        sql = sql.replace("%s", "?")
    try:
        cur = conn.cursor()
        if not _tablas_listas:
            for ddl in _DDL[motor]:
                cur.execute(ddl)
            _tablas_listas = True
        cur.execute(sql, params)
        filas = None
        if leer:
            nombres = [c[0] for c in cur.description]
            filas   = [dict(zip(nombres, f)) for f in cur.fetchall()]
        conn.commit()
        return filas
    finally:
        conn.close()


def _hash(clave: str, sal: bytes = None) -> str:
    sal = sal or os.urandom(16)
    h = hashlib.scrypt(clave.encode("utf-8"), salt=sal, n=2**14, r=8, p=1)
    return f"scrypt${sal.hex()}${h.hex()}"


def _verificar(clave: str, guardado: str) -> bool:
    try:
        _, sal, h = guardado.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(_hash(clave, bytes.fromhex(sal)), guardado)


def _limpio(u: dict) -> dict:
    return {"id": u["id"], "usuario": u["usuario"], "nombre": u["nombre"] or u["usuario"],
            "es_admin": bool(u["es_admin"])}


def hay_usuarios() -> bool:
    return _ejecutar("SELECT COUNT(*) AS n FROM usuarios", leer=True)[0]["n"] > 0


def crear_usuario(usuario: str, clave: str, nombre: str = "", es_admin: bool = False):
    usuario = usuario.strip().lower()
    if len(usuario) < 3:
        raise ValueError("El usuario debe tener al menos 3 caracteres.")
    if len(clave) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if _ejecutar("SELECT id FROM usuarios WHERE usuario = %s", (usuario,), leer=True):
        raise ValueError(f'El usuario "{usuario}" ya existe.')
    _ejecutar("INSERT INTO usuarios (usuario, nombre, clave, es_admin) VALUES (%s, %s, %s, %s)",
              (usuario, nombre.strip(), _hash(clave), es_admin))


def listar_usuarios() -> list:
    return _ejecutar("SELECT id, usuario, nombre, es_admin, activo FROM usuarios ORDER BY id", leer=True)


def cambiar_activo(usuario_id: int, activo: bool):
    _ejecutar("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, usuario_id))
    if not activo:
        _ejecutar("DELETE FROM sesiones WHERE usuario_id = %s", (usuario_id,))


def iniciar_sesion(usuario: str, clave: str):
    """Devuelve (usuario, token) si la clave es correcta; si no, None."""
    filas = _ejecutar("SELECT * FROM usuarios WHERE usuario = %s", (usuario.strip().lower(),), leer=True)
    if not filas or not filas[0]["activo"] or not _verificar(clave, filas[0]["clave"]):
        return None
    token = secrets.token_urlsafe(32)
    _ejecutar("INSERT INTO sesiones (token, usuario_id, vence) VALUES (%s, %s, %s)",
              (token, filas[0]["id"], int(time.time()) + DURACION_SESION))
    return _limpio(filas[0]), token


def usuario_de_sesion(token: str):
    if not token:
        return None
    filas = _ejecutar(
        "SELECT u.* FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token = %s AND s.vence > %s AND u.activo = %s",
        (token, int(time.time()), True), leer=True)
    return _limpio(filas[0]) if filas else None


def cerrar_sesion(token: str):
    if token:
        _ejecutar("DELETE FROM sesiones WHERE token = %s", (token,))
