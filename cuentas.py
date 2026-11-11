"""
Cuentas de usuario y sesiones
=============================
Misma base que el historial: PostgreSQL (DATABASE_URL) o SQLite local.
Las contraseñas se guardan con scrypt (nunca en texto plano).

Se entra con usuario y contraseña (cuentas que crea el administrador) o con Google.
Quien entra con Google por primera vez queda en plan "prueba": unos días y un máximo
de preguntas por día. El administrador cambia el plan desde el panel de usuarios:
  beta     sin límites y sin cobro (primeros usuarios que prueban la app)
  prueba   PRUEBA_DIAS días y PRUEBA_PREGUNTAS_DIA preguntas por día
  activo   cliente que paga, sin límites
  vencido  no puede entrar
"""

import hashlib, hmac, os, re, secrets, sqlite3, time

from historial import DATABASE_URL, SQLITE_PATH

DURACION_SESION = 30 * 24 * 3600   # 30 días
# En el servidor (Neon) la página es pública: contraseñas largas. En local se permiten cortas para probar.
MIN_CLAVE = 8 if DATABASE_URL else 3
PLANES = ("beta", "prueba", "activo", "vencido")
DIAS_PRUEBA = int(os.environ.get("PRUEBA_DIAS", "5"))
PREGUNTAS_PRUEBA = int(os.environ.get("PRUEBA_PREGUNTAS_DIA", "20"))

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
# Columnas agregadas después (las bases ya creadas se actualizan solas)
_MIGRACIONES = {
    "postgres": [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'activo'",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS prueba_hasta BIGINT",
        "CREATE UNIQUE INDEX IF NOT EXISTS usuarios_email ON usuarios (lower(email))",
        """CREATE TABLE IF NOT EXISTS uso (
            usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            dia TEXT NOT NULL,
            preguntas INT NOT NULL DEFAULT 0,
            PRIMARY KEY (usuario_id, dia))""",
        # las plantillas quedan para las cuentas que ya las usaban; las nuevas las tienen apagadas
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plantillas BOOLEAN",
        "UPDATE usuarios SET plantillas = (plan = 'activo') WHERE plantillas IS NULL",
        # conversaciones del asistente de jurisprudencia (los mensajes y sus fuentes, en JSON)
        """CREATE TABLE IF NOT EXISTS conversaciones (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            titulo TEXT NOT NULL,
            actualizada BIGINT NOT NULL,
            mensajes TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS conversaciones_usuario ON conversaciones (usuario_id, actualizada DESC)",
        # tema de colores que eligió en Mi cuenta → Apariencia (vacío: el de la marca)
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tema TEXT",
        # tamaño de letra que eligió en Apariencia (vacío: normal)
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS letra TEXT",
    ],
    "sqlite": [
        "ALTER TABLE usuarios ADD COLUMN email TEXT",
        "ALTER TABLE usuarios ADD COLUMN plan TEXT NOT NULL DEFAULT 'activo'",
        "ALTER TABLE usuarios ADD COLUMN prueba_hasta INTEGER",
        "CREATE UNIQUE INDEX IF NOT EXISTS usuarios_email ON usuarios (lower(email))",
        """CREATE TABLE IF NOT EXISTS uso (
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            dia TEXT NOT NULL,
            preguntas INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (usuario_id, dia))""",
        "ALTER TABLE usuarios ADD COLUMN plantillas INTEGER",
        "UPDATE usuarios SET plantillas = (plan = 'activo') WHERE plantillas IS NULL",
        """CREATE TABLE IF NOT EXISTS conversaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            titulo TEXT NOT NULL,
            actualizada INTEGER NOT NULL,
            mensajes TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS conversaciones_usuario ON conversaciones (usuario_id, actualizada DESC)",
        "ALTER TABLE usuarios ADD COLUMN tema TEXT",
        "ALTER TABLE usuarios ADD COLUMN letra TEXT",
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
            for m in _MIGRACIONES[motor]:
                try:
                    cur.execute(m)
                except sqlite3.OperationalError:
                    pass   # SQLite no tiene ADD COLUMN IF NOT EXISTS: la columna ya estaba
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
            "es_admin": bool(u["es_admin"]), "email": u.get("email") or "", "plan": u.get("plan") or "activo",
            "plantillas": bool(u.get("plantillas")), "tema": u.get("tema") or "", "letra": u.get("letra") or "",
            "prueba_hasta": u.get("prueba_hasta")}


def _bloqueo(u: dict):
    """Motivo por el que la cuenta no puede entrar, o None si puede."""
    if not u["activo"]:
        return "Su cuenta está desactivada. Escríbanos para reactivarla."
    if u.get("plan") == "vencido":
        return "Su acceso terminó. Escríbanos para activar su cuenta."
    if u.get("plan") == "prueba" and u.get("prueba_hasta") and u["prueba_hasta"] < time.time():
        return "Su prueba gratis terminó. Escríbanos para activar su cuenta."
    return None


def _nueva_sesion(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _ejecutar("INSERT INTO sesiones (token, usuario_id, vence) VALUES (%s, %s, %s)",
              (token, usuario_id, int(time.time()) + DURACION_SESION))
    return token


def hay_usuarios() -> bool:
    return _ejecutar("SELECT COUNT(*) AS n FROM usuarios", leer=True)[0]["n"] > 0


def crear_usuario(usuario: str, clave: str, nombre: str = "", es_admin: bool = False, email: str = "",
                  plantillas: bool = False):
    usuario = usuario.strip().lower()
    if len(usuario) < 3:
        raise ValueError("El usuario debe tener al menos 3 caracteres.")
    if len(clave) < MIN_CLAVE:
        raise ValueError(f"La contraseña debe tener al menos {MIN_CLAVE} caracteres.")
    if _ejecutar("SELECT id FROM usuarios WHERE usuario = %s", (usuario,), leer=True):
        raise ValueError(f'El usuario "{usuario}" ya existe.')
    email = _validar_email(email) if email.strip() else None
    _ejecutar("INSERT INTO usuarios (usuario, nombre, clave, es_admin, email, plantillas) VALUES (%s, %s, %s, %s, %s, %s)",
              (usuario, nombre.strip(), _hash(clave), es_admin, email, plantillas))


def listar_usuarios() -> list:
    return _ejecutar("SELECT id, usuario, nombre, es_admin, activo, email, plan, prueba_hasta, plantillas "
                     "FROM usuarios ORDER BY id", leer=True)


def cambiar_activo(usuario_id: int, activo: bool):
    _ejecutar("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, usuario_id))
    if not activo:
        _ejecutar("DELETE FROM sesiones WHERE usuario_id = %s", (usuario_id,))


def cambiar_tema(usuario_id: int, tema: str):
    """Guarda el tema de colores que eligió (Mi cuenta → Apariencia); se usa en todos sus equipos."""
    _ejecutar("UPDATE usuarios SET tema = %s WHERE id = %s", (tema, usuario_id))


def cambiar_letra(usuario_id: int, letra: str):
    """Guarda el tamaño de letra que eligió (normal, grande o muy grande); se usa en todos sus equipos."""
    _ejecutar("UPDATE usuarios SET letra = %s WHERE id = %s", (letra, usuario_id))


def cambiar_plantillas(usuario_id: int, plantillas: bool):
    """Las plantillas de solicitudes son solo para quien se le activen; los demás ven la jurisprudencia."""
    _ejecutar("UPDATE usuarios SET plantillas = %s WHERE id = %s", (plantillas, usuario_id))


def cambiar_plan(usuario_id: int, plan: str):
    """Pasar a "prueba" vuelve a dar PRUEBA_DIAS días desde hoy."""
    if plan not in PLANES:
        raise ValueError(f"Plan desconocido: {plan}")
    if plan == "prueba":
        _ejecutar("UPDATE usuarios SET plan = %s, prueba_hasta = %s WHERE id = %s",
                  (plan, int(time.time()) + DIAS_PRUEBA * 86400, usuario_id))
    else:
        _ejecutar("UPDATE usuarios SET plan = %s WHERE id = %s", (plan, usuario_id))
    if plan == "vencido":
        _ejecutar("DELETE FROM sesiones WHERE usuario_id = %s", (usuario_id,))


def _validar_email(email: str) -> str:
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
        raise ValueError(f"«{email}» no parece un correo.")
    return email


def asignar_email(usuario_id: int, email: str):
    """Enlaza un correo a una cuenta: con él puede entrar con Google a esa misma cuenta."""
    email = _validar_email(email) if email.strip() else None
    if email and _ejecutar("SELECT id FROM usuarios WHERE lower(email) = %s AND id <> %s",
                           (email, usuario_id), leer=True):
        raise ValueError(f"El correo {email} ya está en otra cuenta.")
    _ejecutar("UPDATE usuarios SET email = %s WHERE id = %s", (email, usuario_id))


def iniciar_sesion(usuario: str, clave: str):
    """Devuelve (usuario, token) si la clave es correcta; si no, None."""
    filas = _ejecutar("SELECT * FROM usuarios WHERE usuario = %s", (usuario.strip().lower(),), leer=True)
    if not filas or _bloqueo(filas[0]) or not _verificar(clave, filas[0]["clave"]):
        return None
    return _limpio(filas[0]), _nueva_sesion(filas[0]["id"])


def _usuario_libre(base: str) -> str:
    base = re.sub(r"[^a-z0-9._-]", "", base.lower())[:30] or "usuario"
    base = base if len(base) >= 3 else f"{base}-g"
    nombre, n = base, 1
    while _ejecutar("SELECT id FROM usuarios WHERE usuario = %s", (nombre,), leer=True):
        n += 1
        nombre = f"{base}{n}"
    return nombre


def entrar_con_google(email: str, nombre: str = "", verificado: bool = False):
    """Entra con la cuenta de Google; la primera vez la registra en plan "prueba".
    Devuelve (usuario, token); si no puede entrar, ValueError con el motivo."""
    email = (email or "").strip().lower()
    if not email or not verificado:
        raise ValueError("Google no confirmó el correo de esta cuenta.")
    filas = _ejecutar("SELECT * FROM usuarios WHERE lower(email) = %s", (email,), leer=True)
    if not filas:
        # clave vacía: estas cuentas no pueden entrar con contraseña, solo con Google
        _ejecutar("INSERT INTO usuarios (usuario, nombre, clave, email, plan, prueba_hasta, plantillas) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (_usuario_libre(email.split("@")[0]), (nombre or "").strip(), "", email, "prueba",
                   int(time.time()) + DIAS_PRUEBA * 86400, False))
        filas = _ejecutar("SELECT * FROM usuarios WHERE lower(email) = %s", (email,), leer=True)
    motivo = _bloqueo(filas[0])
    if motivo:
        raise ValueError(motivo)
    return _limpio(filas[0]), _nueva_sesion(filas[0]["id"])


def registrar_pregunta(usuario_id: int, plan: str):
    """Cuenta la pregunta del día. En plan "prueba" hay un máximo diario: ValueError si se pasa."""
    dia = time.strftime("%Y-%m-%d")
    if plan == "prueba":
        filas = _ejecutar("SELECT preguntas FROM uso WHERE usuario_id = %s AND dia = %s", (usuario_id, dia), leer=True)
        if filas and filas[0]["preguntas"] >= PREGUNTAS_PRUEBA:
            raise ValueError(f"Llegó al máximo de {PREGUNTAS_PRUEBA} preguntas por día de la prueba gratis. "
                             "Mañana puede seguir, o escríbanos para activar su cuenta.")
    _ejecutar("INSERT INTO uso (usuario_id, dia, preguntas) VALUES (%s, %s, 1) "
              "ON CONFLICT (usuario_id, dia) DO UPDATE SET preguntas = uso.preguntas + 1", (usuario_id, dia))


def preguntas_de_hoy(usuario_id: int) -> int:
    """Cuántas preguntas lleva hoy (para mostrar lo que le queda de la prueba)."""
    filas = _ejecutar("SELECT preguntas FROM uso WHERE usuario_id = %s AND dia = %s",
                      (usuario_id, time.strftime("%Y-%m-%d")), leer=True)
    return filas[0]["preguntas"] if filas else 0


def usuario_de_sesion(token: str):
    if not token:
        return None
    filas = _ejecutar(
        "SELECT u.* FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token = %s AND s.vence > %s", (token, int(time.time())), leer=True)
    return _limpio(filas[0]) if filas and not _bloqueo(filas[0]) else None


def cerrar_sesion(token: str):
    if token:
        _ejecutar("DELETE FROM sesiones WHERE token = %s", (token,))


# ── Conversaciones del asistente ─────────────────
MAX_CONVERSACIONES = 100   # por usuario; las más viejas se borran solas (la base gratis es chica)
MAX_TEXTO_FUENTE = 2000    # de cada fuente se guarda lo que la IA necesita para seguir la conversación


def _titulo(mensajes: list) -> str:
    primera = next((m["texto"] for m in mensajes if m.get("rol") == "usuario"), "Conversación")
    primera = " ".join(primera.split())
    return primera if len(primera) <= 60 else primera[:57].rsplit(" ", 1)[0] + "…"


def guardar_conversacion(usuario_id: int, conv_id, mensajes: list):
    """Guarda la conversación (nueva si conv_id es None) y devuelve su id."""
    import json
    livianos = [{**m, "fuentes": [{**f, "texto": (f.get("texto") or "")[:MAX_TEXTO_FUENTE]}
                                  for f in m.get("fuentes") or []]} for m in mensajes]
    datos = json.dumps(livianos, ensure_ascii=False, default=str)
    ahora = int(time.time())
    if conv_id:
        _ejecutar("UPDATE conversaciones SET mensajes = %s, actualizada = %s WHERE id = %s AND usuario_id = %s",
                  (datos, ahora, conv_id, usuario_id))
        return conv_id
    fila = _ejecutar("INSERT INTO conversaciones (usuario_id, titulo, actualizada, mensajes) "
                     "VALUES (%s, %s, %s, %s) RETURNING id",
                     (usuario_id, _titulo(mensajes), ahora, datos), leer=True)
    _ejecutar("""DELETE FROM conversaciones WHERE usuario_id = %s AND id NOT IN (
                     SELECT id FROM conversaciones WHERE usuario_id = %s ORDER BY actualizada DESC LIMIT %s)""",
              (usuario_id, usuario_id, MAX_CONVERSACIONES))
    return fila[0]["id"]


def listar_conversaciones(usuario_id: int) -> list:
    return _ejecutar("SELECT id, titulo, actualizada FROM conversaciones WHERE usuario_id = %s "
                     "ORDER BY actualizada DESC", (usuario_id,), leer=True)


def abrir_conversacion(usuario_id: int, conv_id: int) -> list:
    import json
    filas = _ejecutar("SELECT mensajes FROM conversaciones WHERE id = %s AND usuario_id = %s",
                      (conv_id, usuario_id), leer=True)
    return json.loads(filas[0]["mensajes"]) if filas else []


def borrar_conversacion(usuario_id: int, conv_id: int):
    _ejecutar("DELETE FROM conversaciones WHERE id = %s AND usuario_id = %s", (conv_id, usuario_id))
