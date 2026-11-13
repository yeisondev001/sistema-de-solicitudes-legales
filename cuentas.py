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
  basico   cliente del plan Básico: BASICO_PREGUNTAS_DIA preguntas por día, sin escritos, modelos ni
           documentos propios
  activo   cliente que paga, sin límites
  vencido  no puede entrar
"""

import hashlib, hmac, os, re, secrets, sqlite3, time

from historial import DATABASE_URL, SQLITE_PATH

DURACION_SESION = 30 * 24 * 3600   # 30 días
# En el servidor (Neon) la página es pública: contraseñas largas. En local se permiten cortas para probar.
MIN_CLAVE = 8 if DATABASE_URL else 3
PLANES = ("beta", "prueba", "basico", "activo", "vencido")
DIAS_PRUEBA = int(os.environ.get("PRUEBA_DIAS", "7"))
PREGUNTAS_PRUEBA = int(os.environ.get("PRUEBA_PREGUNTAS_DIA", "20"))
PREGUNTAS_BASICO = int(os.environ.get("BASICO_PREGUNTAS_DIA", "20"))


def tope_diario(plan: str):
    """Cuántas preguntas por día deja el plan, o None si no tiene límite."""
    return {"prueba": PREGUNTAS_PRUEBA, "basico": PREGUNTAS_BASICO}.get(plan)


def con_escritos(plan: str) -> bool:
    """Escritos, modelos y documentos propios: todos los planes menos el Básico."""
    return plan != "basico"

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
        # el escrito que Papiniano redacta al lado de la conversación (JSON: texto y versiones anteriores)
        "ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS escrito TEXT",
        # los modelos de escritos que sube cada abogado: solo los ve él (los de todos están en modelos/)
        """CREATE TABLE IF NOT EXISTS modelos_propios (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            nombre TEXT NOT NULL,
            grupo TEXT NOT NULL DEFAULT '',
            materia TEXT NOT NULL DEFAULT '',
            texto TEXT NOT NULL,
            actualizado BIGINT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS modelos_propios_usuario ON modelos_propios (usuario_id)",
        # las oficinas del plan Despacho: varios abogados, un dueño y un solo plan para todos
        """CREATE TABLE IF NOT EXISTS oficinas (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            nombre TEXT NOT NULL,
            dueno_id BIGINT NOT NULL REFERENCES usuarios(id),
            plan TEXT NOT NULL DEFAULT 'activo',
            creada BIGINT NOT NULL)""",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS oficina_id BIGINT",
        "CREATE INDEX IF NOT EXISTS usuarios_oficina ON usuarios (oficina_id)",
        # los correos que agregó el dueño y todavía no han aceptado
        """CREATE TABLE IF NOT EXISTS oficina_invitaciones (
            oficina_id BIGINT NOT NULL REFERENCES oficinas(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            creada BIGINT NOT NULL,
            PRIMARY KEY (oficina_id, email))""",
        # el abogado comparte un modelo suyo con su oficina
        "ALTER TABLE modelos_propios ADD COLUMN IF NOT EXISTS compartido BOOLEAN NOT NULL DEFAULT FALSE",
        # los asientos que paga la oficina: uno por abogado, el dueño incluido
        "ALTER TABLE oficinas ADD COLUMN IF NOT EXISTS asientos INTEGER NOT NULL DEFAULT 4",
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
        "ALTER TABLE conversaciones ADD COLUMN escrito TEXT",
        """CREATE TABLE IF NOT EXISTS modelos_propios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            nombre TEXT NOT NULL,
            grupo TEXT NOT NULL DEFAULT '',
            materia TEXT NOT NULL DEFAULT '',
            texto TEXT NOT NULL,
            actualizado INTEGER NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS modelos_propios_usuario ON modelos_propios (usuario_id)",
        """CREATE TABLE IF NOT EXISTS oficinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            dueno_id INTEGER NOT NULL REFERENCES usuarios(id),
            plan TEXT NOT NULL DEFAULT 'activo',
            creada INTEGER NOT NULL)""",
        "ALTER TABLE usuarios ADD COLUMN oficina_id INTEGER",
        "CREATE INDEX IF NOT EXISTS usuarios_oficina ON usuarios (oficina_id)",
        """CREATE TABLE IF NOT EXISTS oficina_invitaciones (
            oficina_id INTEGER NOT NULL REFERENCES oficinas(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            creada INTEGER NOT NULL,
            PRIMARY KEY (oficina_id, email))""",
        "ALTER TABLE modelos_propios ADD COLUMN compartido INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE oficinas ADD COLUMN asientos INTEGER NOT NULL DEFAULT 4",
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


# la cuenta con su oficina: el plan de la oficina manda sobre el de cada abogado que está en ella
_CUENTA = ("SELECT u.*, o.nombre AS oficina_nombre, o.plan AS oficina_plan, o.dueno_id AS oficina_dueno "
           "FROM usuarios u LEFT JOIN oficinas o ON o.id = u.oficina_id")


def _plan(u: dict) -> str:
    return u.get("oficina_plan") or u.get("plan") or "activo"


def _limpio(u: dict) -> dict:
    oficina = ({"id": u["oficina_id"], "nombre": u["oficina_nombre"], "es_dueno": u["oficina_dueno"] == u["id"]}
               if u.get("oficina_nombre") else None)
    return {"id": u["id"], "usuario": u["usuario"], "nombre": u["nombre"] or u["usuario"],
            "es_admin": bool(u["es_admin"]), "email": u.get("email") or "", "plan": _plan(u),
            "plantillas": bool(u.get("plantillas")), "tema": u.get("tema") or "", "letra": u.get("letra") or "",
            "prueba_hasta": u.get("prueba_hasta"), "oficina": oficina}


def _bloqueo(u: dict):
    """Motivo por el que la cuenta no puede entrar, o None si puede."""
    plan = _plan(u)
    if not u["activo"]:
        return "Su cuenta está desactivada. Escríbanos para reactivarla."
    if plan == "vencido":
        return ("El plan de su oficina está vencido. Hable con el dueño de la oficina o escríbanos."
                if u.get("oficina_plan") else "Su acceso terminó. Escríbanos para activar su cuenta.")
    if plan == "prueba" and u.get("prueba_hasta") and u["prueba_hasta"] < time.time():
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
    """Para el panel: el plan es el de la cuenta; si está en una oficina, el que vale es el de la oficina."""
    return _ejecutar("SELECT u.id, u.usuario, u.nombre, u.es_admin, u.activo, u.email, u.plan, u.prueba_hasta, "
                     "u.plantillas, u.oficina_id, o.nombre AS oficina FROM usuarios u "
                     "LEFT JOIN oficinas o ON o.id = u.oficina_id ORDER BY u.id", leer=True)


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
    filas = _ejecutar(f"{_CUENTA} WHERE u.usuario = %s", (usuario.strip().lower(),), leer=True)
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
    filas = _ejecutar(f"{_CUENTA} WHERE lower(u.email) = %s", (email,), leer=True)
    if not filas:
        # clave vacía: estas cuentas no pueden entrar con contraseña, solo con Google
        _ejecutar("INSERT INTO usuarios (usuario, nombre, clave, email, plan, prueba_hasta, plantillas) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (_usuario_libre(email.split("@")[0]), (nombre or "").strip(), "", email, "prueba",
                   int(time.time()) + DIAS_PRUEBA * 86400, False))
        filas = _ejecutar(f"{_CUENTA} WHERE lower(u.email) = %s", (email,), leer=True)
    motivo = _bloqueo(filas[0])
    if motivo:
        raise ValueError(motivo)
    return _limpio(filas[0]), _nueva_sesion(filas[0]["id"])


def registrar_pregunta(usuario_id: int, plan: str):
    """Cuenta la pregunta del día. La prueba y el plan Básico tienen un máximo diario: ValueError si se pasa."""
    dia = time.strftime("%Y-%m-%d")
    tope = tope_diario(plan)
    if tope:
        filas = _ejecutar("SELECT preguntas FROM uso WHERE usuario_id = %s AND dia = %s", (usuario_id, dia), leer=True)
        if filas and filas[0]["preguntas"] >= tope:
            raise ValueError(f"Llegó al máximo de {tope} preguntas por día de la prueba gratis. "
                             "Mañana puede seguir, o escríbanos para activar su cuenta." if plan == "prueba" else
                             f"Llegó al máximo de {tope} preguntas por día del plan Básico. Mañana puede seguir, "
                             "o pase al plan Abogado para consultar sin límite.")
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
        "SELECT u.*, o.nombre AS oficina_nombre, o.plan AS oficina_plan, o.dueno_id AS oficina_dueno "
        "FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id LEFT JOIN oficinas o ON o.id = u.oficina_id "
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


# ── El escrito de cada conversación ──────────────
MAX_VERSIONES = 20   # versiones anteriores que se guardan para «Deshacer»


def _leer_escrito(usuario_id: int, conv_id: int):
    import json
    filas = _ejecutar("SELECT escrito FROM conversaciones WHERE id = %s AND usuario_id = %s",
                      (conv_id, usuario_id), leer=True)
    return json.loads(filas[0]["escrito"]) if filas and filas[0]["escrito"] else None


def _poner_escrito(usuario_id: int, conv_id: int, escrito: dict):
    import json
    _ejecutar("UPDATE conversaciones SET escrito = %s, actualizada = %s WHERE id = %s AND usuario_id = %s",
              (json.dumps(escrito, ensure_ascii=False), int(time.time()), conv_id, usuario_id))


def _publico(escrito):
    """Lo que ven las pantallas: el texto y si hay algo que deshacer."""
    return {"texto": escrito["texto"], "deshacer": bool(escrito["anteriores"])} if escrito else None


def leer_escrito(usuario_id: int, conv_id: int):
    return _publico(_leer_escrito(usuario_id, conv_id))


def guardar_escrito(usuario_id: int, conv_id: int, texto: str):
    """Pone el texto nuevo del escrito; el anterior queda para «Deshacer»."""
    actual = _leer_escrito(usuario_id, conv_id) or {"texto": "", "anteriores": []}
    if texto != actual["texto"]:
        anteriores = actual["anteriores"] + ([actual["texto"]] if actual["texto"] else [])
        actual = {"texto": texto, "anteriores": anteriores[-MAX_VERSIONES:]}
        _poner_escrito(usuario_id, conv_id, actual)
    return _publico(actual)


MAX_MODELOS_PROPIOS = 100


# ── Los modelos que sube cada abogado ────────────
def listar_modelos_propios(usuario_id: int) -> list:
    return _ejecutar("SELECT id, nombre, grupo, materia, compartido, usuario_id FROM modelos_propios "
                     "WHERE usuario_id = %s ORDER BY nombre", (usuario_id,), leer=True)


def listar_modelos_oficina(usuario_id: int) -> list:
    """Los que comparten sus colegas de oficina (los suyos están en listar_modelos_propios)."""
    return _ejecutar("SELECT m.id, m.nombre, m.grupo, m.materia, m.compartido, m.usuario_id, "
                     "COALESCE(NULLIF(a.nombre, ''), a.usuario) AS autor FROM modelos_propios m "
                     "JOIN usuarios a ON a.id = m.usuario_id JOIN usuarios yo ON yo.id = %s "
                     "WHERE m.compartido AND a.oficina_id = yo.oficina_id AND a.id <> yo.id ORDER BY m.nombre",
                     (usuario_id,), leer=True)


def leer_modelo_propio(usuario_id: int, modelo_id: int):
    """Uno de los suyos, para cambiarlo."""
    filas = _ejecutar("SELECT id, nombre, grupo, materia, texto, compartido, usuario_id FROM modelos_propios "
                      "WHERE id = %s AND usuario_id = %s", (modelo_id, usuario_id), leer=True)
    return filas[0] if filas else None


def leer_modelo(usuario_id: int, modelo_id: int):
    """Un modelo que el abogado puede usar: suyo o compartido por un colega de su oficina."""
    filas = _ejecutar("SELECT m.id, m.nombre, m.grupo, m.materia, m.texto, m.compartido, m.usuario_id, "
                      "COALESCE(NULLIF(a.nombre, ''), a.usuario) AS autor FROM modelos_propios m "
                      "JOIN usuarios a ON a.id = m.usuario_id JOIN usuarios yo ON yo.id = %s "
                      "WHERE m.id = %s AND (a.id = yo.id OR (m.compartido AND a.oficina_id = yo.oficina_id))",
                      (usuario_id, modelo_id), leer=True)
    return filas[0] if filas else None


def guardar_modelo_propio(usuario_id: int, modelo_id, nombre: str, grupo: str, materia: str, texto: str,
                          compartido: bool = False) -> int:
    """Crea el modelo (modelo_id None) o lo cambia; devuelve su id."""
    ahora = int(time.time())
    if modelo_id:
        if not leer_modelo_propio(usuario_id, modelo_id):
            raise ValueError("Ese modelo ya no existe.")
        _ejecutar("UPDATE modelos_propios SET nombre = %s, grupo = %s, materia = %s, texto = %s, compartido = %s, "
                  "actualizado = %s WHERE id = %s AND usuario_id = %s",
                  (nombre, grupo, materia, texto, compartido, ahora, modelo_id, usuario_id))
        return modelo_id
    if len(listar_modelos_propios(usuario_id)) >= MAX_MODELOS_PROPIOS:
        raise ValueError(f"Ya tiene {MAX_MODELOS_PROPIOS} modelos. Borre alguno para subir otro.")
    _ejecutar("INSERT INTO modelos_propios (usuario_id, nombre, grupo, materia, texto, compartido, actualizado) "
              "VALUES (%s, %s, %s, %s, %s, %s, %s)", (usuario_id, nombre, grupo, materia, texto, compartido, ahora))
    filas = _ejecutar("SELECT id FROM modelos_propios WHERE usuario_id = %s ORDER BY id DESC LIMIT 1",
                      (usuario_id,), leer=True)
    return filas[0]["id"]


def borrar_modelo_propio(usuario_id: int, modelo_id: int):
    _ejecutar("DELETE FROM modelos_propios WHERE id = %s AND usuario_id = %s", (modelo_id, usuario_id))


def deshacer_escrito(usuario_id: int, conv_id: int):
    """Vuelve a la versión anterior del escrito (la de antes del último cambio)."""
    actual = _leer_escrito(usuario_id, conv_id)
    if actual and actual["anteriores"]:
        actual = {"texto": actual["anteriores"][-1], "anteriores": actual["anteriores"][:-1]}
        _poner_escrito(usuario_id, conv_id, actual)
    return _publico(actual)


# ── Las oficinas (plan Despacho) ─────────────────
# Varios abogados con un dueño y un solo plan. El administrador crea la oficina; el dueño agrega abogados
# por su correo y cada uno acepta desde su escritorio. El dueño ve quién usa Papiniano y cuánto, nunca lo
# que pregunta: conversaciones, documentos y escritos siguen siendo de cada abogado.
# La oficina paga asientos (uno por abogado, el dueño incluido, desde 4); los correos agregados que todavía no
# aceptan ya ocupan el suyo.
PLANES_OFICINA = ("activo", "vencido")
ASIENTOS_MINIMOS, ASIENTOS_MAXIMOS = 4, 30
_NOMBRE = "COALESCE(NULLIF({0}.nombre, ''), {0}.usuario)"


def listar_oficinas() -> list:
    return _ejecutar(f"SELECT o.id, o.nombre, o.plan, o.asientos, o.dueno_id, {_NOMBRE.format('d')} AS dueno, "
                     "(SELECT COUNT(*) FROM usuarios m WHERE m.oficina_id = o.id) AS abogados "
                     "FROM oficinas o JOIN usuarios d ON d.id = o.dueno_id ORDER BY o.nombre", leer=True)


def _asientos(asientos) -> int:
    if not isinstance(asientos, int) or not ASIENTOS_MINIMOS <= asientos <= ASIENTOS_MAXIMOS:
        raise ValueError(f"Los asientos van de {ASIENTOS_MINIMOS} a {ASIENTOS_MAXIMOS}.")
    return asientos


def _ocupados(oficina_id: int) -> int:
    """Abogados en la oficina más correos agregados que todavía no aceptan."""
    return _ejecutar("SELECT (SELECT COUNT(*) FROM usuarios WHERE oficina_id = %s) + "
                     "(SELECT COUNT(*) FROM oficina_invitaciones WHERE oficina_id = %s) AS n",
                     (oficina_id, oficina_id), leer=True)[0]["n"]


def _oficina(oficina_id: int) -> dict:
    filas = _ejecutar("SELECT * FROM oficinas WHERE id = %s", (oficina_id,), leer=True)
    if not filas:
        raise ValueError("Esa oficina ya no existe.")
    return filas[0]


def crear_oficina(nombre: str, dueno_id: int, asientos: int = ASIENTOS_MINIMOS) -> int:
    nombre = " ".join(nombre.split())[:80]
    if not nombre:
        raise ValueError("Póngale un nombre a la oficina.")
    asientos = _asientos(asientos)
    dueno = _ejecutar("SELECT oficina_id FROM usuarios WHERE id = %s", (dueno_id,), leer=True)
    if not dueno:
        raise ValueError("Esa cuenta no existe.")
    if dueno[0]["oficina_id"]:
        raise ValueError("Esa cuenta ya está en una oficina.")
    fila = _ejecutar("INSERT INTO oficinas (nombre, dueno_id, asientos, creada) VALUES (%s, %s, %s, %s) RETURNING id",
                     (nombre, dueno_id, asientos, int(time.time())), leer=True)
    _ejecutar("UPDATE usuarios SET oficina_id = %s WHERE id = %s", (fila[0]["id"], dueno_id))
    return fila[0]["id"]


def cambiar_oficina(oficina_id: int, nombre: str = None, plan: str = None, asientos: int = None):
    _oficina(oficina_id)
    if asientos is not None:
        asientos, ocupados = _asientos(asientos), _ocupados(oficina_id)
        if asientos < ocupados:
            raise ValueError(f"La oficina ya ocupa {ocupados} asientos: primero quite abogados o correos.")
        _ejecutar("UPDATE oficinas SET asientos = %s WHERE id = %s", (asientos, oficina_id))
    if nombre is not None:
        nombre = " ".join(nombre.split())[:80]
        if not nombre:
            raise ValueError("Póngale un nombre a la oficina.")
        _ejecutar("UPDATE oficinas SET nombre = %s WHERE id = %s", (nombre, oficina_id))
    if plan is not None:
        if plan not in PLANES_OFICINA:
            raise ValueError(f"Plan desconocido: {plan}")
        _ejecutar("UPDATE oficinas SET plan = %s WHERE id = %s", (plan, oficina_id))


def _sacar(usuario_id: int):
    """Sale de su oficina con todo lo suyo; sus modelos dejan de estar compartidos."""
    _ejecutar("UPDATE modelos_propios SET compartido = %s WHERE usuario_id = %s", (False, usuario_id))
    _ejecutar("UPDATE usuarios SET oficina_id = NULL WHERE id = %s", (usuario_id,))


def borrar_oficina(oficina_id: int):
    """Cada abogado sigue con su cuenta y lo suyo, con el plan que tenía su cuenta antes de entrar."""
    for m in _ejecutar("SELECT id FROM usuarios WHERE oficina_id = %s", (oficina_id,), leer=True):
        _sacar(m["id"])
    _ejecutar("DELETE FROM oficina_invitaciones WHERE oficina_id = %s", (oficina_id,))
    _ejecutar("DELETE FROM oficinas WHERE id = %s", (oficina_id,))


def _cupo(oficina_id: int):
    asientos = _oficina(oficina_id)["asientos"]
    if _ocupados(oficina_id) >= asientos:
        raise ValueError(f"Los {asientos} asientos de la oficina están ocupados. "
                         "Para agregar a otro abogado, escríbanos y le sumamos un asiento.")


def poner_en_oficina(usuario_id: int, oficina_id):
    """El administrador mete o saca una cuenta de una oficina (oficina_id None: la saca)."""
    if _ejecutar("SELECT id FROM oficinas WHERE dueno_id = %s", (usuario_id,), leer=True):
        raise ValueError("Esa cuenta es la dueña de una oficina: para sacarla, borre la oficina.")
    if oficina_id is None:
        _sacar(usuario_id)
        return
    _oficina(oficina_id)
    _cupo(oficina_id)
    _ejecutar("UPDATE modelos_propios SET compartido = %s WHERE usuario_id = %s", (False, usuario_id))
    _ejecutar("UPDATE usuarios SET oficina_id = %s WHERE id = %s", (oficina_id, usuario_id))


def mi_oficina(usuario_id: int):
    """La oficina del abogado y quiénes están; el dueño ve además el uso de cada uno y los correos que agregó.
    None si no está en ninguna."""
    filas = _ejecutar("SELECT o.* FROM oficinas o JOIN usuarios u ON u.oficina_id = o.id WHERE u.id = %s",
                      (usuario_id,), leer=True)
    if not filas:
        return None
    o = filas[0]
    dueno = o["dueno_id"] == usuario_id
    abogados = _ejecutar(
        f"SELECT u.id, {_NOMBRE.format('u')} AS nombre, u.email, MAX(x.dia) AS ultimo, "
        "COALESCE(SUM(CASE WHEN x.dia >= %s THEN x.preguntas ELSE 0 END), 0) AS mes "
        "FROM usuarios u LEFT JOIN uso x ON x.usuario_id = u.id WHERE u.oficina_id = %s "
        "GROUP BY u.id, u.nombre, u.usuario, u.email ORDER BY u.id",
        (time.strftime("%Y-%m-01"), o["id"]), leer=True)
    lista = [{"id": a["id"], "nombre": a["nombre"], "dueno": a["id"] == o["dueno_id"],
              **({"email": a["email"] or "", "ultimo": a["ultimo"], "mes": int(a["mes"])} if dueno else {})}
             for a in abogados]
    pendientes = [f["email"] for f in _ejecutar(
        "SELECT email FROM oficina_invitaciones WHERE oficina_id = %s ORDER BY creada", (o["id"],), leer=True)
    ] if dueno else []
    return {"id": o["id"], "nombre": o["nombre"], "plan": o["plan"], "es_dueno": dueno, "asientos": o["asientos"],
            "abogados": lista, "pendientes": pendientes}


def _del_dueno(usuario_id: int) -> dict:
    filas = _ejecutar("SELECT * FROM oficinas WHERE dueno_id = %s", (usuario_id,), leer=True)
    if not filas:
        raise PermissionError("Solo el dueño de la oficina puede hacer esto.")
    return filas[0]


def invitar(dueno_id: int, email: str):
    """El dueño agrega a un abogado por su correo; entra a la oficina cuando él acepte."""
    o = _del_dueno(dueno_id)
    email = _validar_email(email)
    if _ejecutar("SELECT id FROM usuarios WHERE lower(email) = %s AND oficina_id = %s", (email, o["id"]), leer=True):
        raise ValueError(f"{email} ya está en la oficina.")
    if _ejecutar("SELECT email FROM oficina_invitaciones WHERE oficina_id = %s AND email = %s",
                 (o["id"], email), leer=True):
        raise ValueError(f"Ya agregó a {email}: falta que entre y acepte.")
    _cupo(o["id"])
    _ejecutar("INSERT INTO oficina_invitaciones (oficina_id, email, creada) VALUES (%s, %s, %s)",
              (o["id"], email, int(time.time())))


def cancelar_invitacion(dueno_id: int, email: str):
    o = _del_dueno(dueno_id)
    _ejecutar("DELETE FROM oficina_invitaciones WHERE oficina_id = %s AND email = %s",
              (o["id"], email.strip().lower()))


def quitar_abogado(dueno_id: int, abogado_id: int):
    o = _del_dueno(dueno_id)
    if abogado_id == dueno_id:
        raise ValueError("Usted es el dueño: no puede quitarse de su oficina.")
    if not _ejecutar("SELECT id FROM usuarios WHERE id = %s AND oficina_id = %s", (abogado_id, o["id"]), leer=True):
        raise ValueError("Ese abogado ya no está en la oficina.")
    _sacar(abogado_id)


def invitaciones_de(u: dict) -> list:
    """Las oficinas que agregaron el correo de esta cuenta y esperan que acepte."""
    if not u.get("email"):
        return []
    return _ejecutar(f"SELECT o.id, o.nombre, {_NOMBRE.format('d')} AS dueno FROM oficina_invitaciones i "
                     "JOIN oficinas o ON o.id = i.oficina_id JOIN usuarios d ON d.id = o.dueno_id "
                     "WHERE i.email = %s ORDER BY i.creada", (u["email"].lower(),), leer=True)


def aceptar_invitacion(u: dict, oficina_id: int):
    email = (u.get("email") or "").lower()
    if not _ejecutar("SELECT email FROM oficina_invitaciones WHERE oficina_id = %s AND email = %s",
                     (oficina_id, email), leer=True):
        raise ValueError("Esa invitación ya no está.")
    if u.get("oficina"):
        raise ValueError(f"Usted ya está en «{u['oficina']['nombre']}». Primero salga de esa oficina.")
    _ejecutar("UPDATE usuarios SET oficina_id = %s WHERE id = %s", (oficina_id, u["id"]))
    _ejecutar("DELETE FROM oficina_invitaciones WHERE oficina_id = %s AND email = %s", (oficina_id, email))


def rechazar_invitacion(u: dict, oficina_id: int):
    _ejecutar("DELETE FROM oficina_invitaciones WHERE oficina_id = %s AND email = %s",
              (oficina_id, (u.get("email") or "").lower()))


def salir_de_oficina(u: dict):
    if not u.get("oficina"):
        raise ValueError("Usted no está en ninguna oficina.")
    if u["oficina"]["es_dueno"]:
        raise ValueError("Usted es el dueño de la oficina. Para cerrarla, escríbanos.")
    _sacar(u["id"])
