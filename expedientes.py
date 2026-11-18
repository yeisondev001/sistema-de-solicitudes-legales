"""
Expedientes y agenda
====================
Un expediente es la carpeta de un caso: el cliente, el asunto, el número, el tribunal, la contraparte, quién lo
lleva y unas notas. La agenda son las fechas (audiencias, plazos, reuniones), de un expediente o sueltas.

En una oficina (plan Despacho) los dos son de la oficina: todos sus abogados ven y cambian los mismos, y cada cosa
dice quién la lleva. Fuera de una oficina, cada abogado ve solo lo suyo. Si un abogado sale de la oficina, lo de la
oficina se queda en ella; si se cierra la oficina, cada cosa vuelve a quien la creó (cuentas.borrar_oficina).

Las conversaciones con Papiniano y los documentos siguen siendo de cada abogado: un expediente muestra solo los
que guardó en él el abogado que lo mira, nunca los de sus colegas.

Ley 172-13: los datos del cliente se guardan en la base de Papiniano y no se le mandan a la IA. No hay campo de
cédula: no hace falta para llevar el caso.

Las tablas se crean con las de cuentas.py (_MIGRACIONES). La de los expedientes se llama «casos»: «expedientes» ya
es la del historial de reportes de audiencia (historial.py), en la misma base. Errores: ValueError (dato mal puesto)
y LookupError (no existe o no es suyo).
"""

import time
from datetime import date, datetime, timedelta, timezone

from cuentas import _NOMBRE, _ejecutar

ZONA_RD = timezone(timedelta(hours=-4))
ESTADOS = ("activo", "cerrado")
TIPOS = ("audiencia", "plazo", "reunion", "otro")
MAX_EXPEDIENTES = 2000   # por oficina, o por abogado sin oficina (la base gratis es chica)
MAX_FECHAS = 5000
# lo más largo que se guarda de cada dato
LARGOS = {"cliente": 120, "asunto": 160, "numero": 60, "tribunal": 160, "contraparte": 160, "notas": 4000}
LARGOS_FECHA = {"titulo": 160, "lugar": 160, "notas": 2000}


def hoy() -> date:
    return datetime.now(ZONA_RD).date()


def _quien(u: dict) -> tuple:
    """(id del abogado, id de su oficina o None)"""
    return u["id"], (u.get("oficina") or {}).get("id")


def _visible(alias: str) -> str:
    """Lo que puede ver el abogado: lo suyo sin oficina y lo de su oficina. Va con los parámetros de _quien."""
    return (f"(({alias}.oficina_id IS NULL AND {alias}.usuario_id = %s) "
            f"OR ({alias}.oficina_id IS NOT NULL AND {alias}.oficina_id = %s))")


def _limpio(datos: dict, campo: str, largo: int) -> str:
    texto = str(datos.get(campo) or "")
    # las notas conservan sus renglones; lo demás es de una línea
    texto = texto.replace("\r\n", "\n").strip() if campo == "notas" else " ".join(texto.split())
    return texto[:largo]


def _responsable(u: dict, responsable_id) -> int:
    """Quién lleva el caso o la fecha: el mismo abogado o un colega de su oficina."""
    uid, oid = _quien(u)
    if not responsable_id or responsable_id == uid:
        return uid
    if oid and _ejecutar("SELECT id FROM usuarios WHERE id = %s AND oficina_id = %s", (responsable_id, oid), leer=True):
        return responsable_id
    raise ValueError("Ese abogado no está en su oficina.")


def _con_responsable(fila: dict) -> dict:
    nombre = fila.pop("responsable", None)
    rid = fila.pop("responsable_id", None)
    fila["responsable"] = {"id": rid, "nombre": nombre} if rid and nombre else None
    fila["de_oficina"] = fila.pop("oficina_id", None) is not None
    fila.pop("usuario_id", None)
    return fila


# ── Expedientes ──────────────────────────────────
_COLUMNAS = ("x.id, x.cliente, x.asunto, x.numero, x.tribunal, x.contraparte, x.notas, x.estado, x.responsable_id, "
             f"x.oficina_id, x.usuario_id, x.creado, x.actualizado, {_NOMBRE.format('r')} AS responsable")


def _expediente(u: dict, exp_id: int) -> dict:
    filas = _ejecutar(f"SELECT {_COLUMNAS} FROM casos x LEFT JOIN usuarios r ON r.id = x.responsable_id "
                      f"WHERE x.id = %s AND {_visible('x')}", (exp_id, *_quien(u)), leer=True)
    if not filas:
        raise LookupError("Ese expediente ya no existe.")
    return filas[0]


def listar(u: dict) -> list:
    """Todos los que ve el abogado (activos y cerrados), con su próxima fecha; los que se tocaron último, primero."""
    filas = _ejecutar(f"SELECT {_COLUMNAS} FROM casos x LEFT JOIN usuarios r ON r.id = x.responsable_id "
                      f"WHERE {_visible('x')} ORDER BY x.actualizado DESC", _quien(u), leer=True)
    proximas = {}
    for f in _ejecutar("SELECT a.expediente_id, a.fecha, a.hora, a.tipo, a.titulo FROM agenda a "
                       f"JOIN casos x ON x.id = a.expediente_id WHERE a.fecha >= %s AND {_visible('x')} "
                       "ORDER BY a.fecha, a.hora", (hoy().isoformat(), *_quien(u)), leer=True):
        proximas.setdefault(f.pop("expediente_id"), f)
    for f in filas:
        f.pop("notas")
        f["proxima"] = proximas.get(f["id"])
    return [_con_responsable(f) for f in filas]


def leer(u: dict, exp_id: int) -> dict:
    """El expediente con sus fechas, y las conversaciones y documentos que el abogado guardó en él."""
    x = _con_responsable(_expediente(u, exp_id))
    x["fechas"] = [_con_responsable(f) for f in _ejecutar(
        f"SELECT a.id, a.tipo, a.titulo, a.fecha, a.hora, a.lugar, a.notas, a.responsable_id, a.oficina_id, "
        f"{_NOMBRE.format('r')} AS responsable FROM agenda a LEFT JOIN usuarios r ON r.id = a.responsable_id "
        "WHERE a.expediente_id = %s ORDER BY a.fecha, a.hora", (exp_id,), leer=True)]
    x["conversaciones"] = [
        {"id": c["id"], "titulo": c["titulo"], "actualizada": c["actualizada"], "con_escrito": bool(c["escrito"])}
        for c in _ejecutar("SELECT id, titulo, actualizada, escrito FROM conversaciones "
                           "WHERE usuario_id = %s AND expediente_id = %s ORDER BY actualizada DESC",
                           (u["id"], exp_id), leer=True)]
    x["documentos"] = _ejecutar("SELECT doc_id AS id, nombre FROM caso_documentos "
                                "WHERE expediente_id = %s AND usuario_id = %s ORDER BY nombre",
                                (exp_id, u["id"]), leer=True)
    return x


def guardar(u: dict, exp_id, datos: dict) -> int:
    """Crea el expediente (exp_id None) o lo cambia; devuelve su id."""
    campos = {k: _limpio(datos, k, n) for k, n in LARGOS.items()}
    if not campos["cliente"]:
        raise ValueError("Escriba el nombre del cliente.")
    estado = datos.get("estado") or "activo"
    if estado not in ESTADOS:
        raise ValueError("El estado es «activo» o «cerrado».")
    responsable = _responsable(u, datos.get("responsable_id"))
    ahora = int(time.time())
    if exp_id:
        _expediente(u, exp_id)
        _ejecutar("UPDATE casos SET cliente = %s, asunto = %s, numero = %s, tribunal = %s, contraparte = %s, "
                  "notas = %s, estado = %s, responsable_id = %s, actualizado = %s WHERE id = %s",
                  (*campos.values(), estado, responsable, ahora, exp_id))
        return exp_id
    uid, oid = _quien(u)
    if _ejecutar(f"SELECT COUNT(*) AS n FROM casos x WHERE {_visible('x')}", (uid, oid),
                 leer=True)[0]["n"] >= MAX_EXPEDIENTES:
        raise ValueError(f"Ya hay {MAX_EXPEDIENTES} expedientes. Borre los que ya no necesite para crear otro.")
    fila = _ejecutar("INSERT INTO casos (usuario_id, oficina_id, responsable_id, cliente, asunto, numero, "
                     "tribunal, contraparte, notas, estado, creado, actualizado) "
                     "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                     (uid, oid, responsable, *campos.values(), estado, ahora, ahora), leer=True)
    return fila[0]["id"]


def borrar(u: dict, exp_id: int):
    """Borra el expediente y sus fechas; las conversaciones y los documentos quedan, sueltos."""
    _expediente(u, exp_id)
    _ejecutar("DELETE FROM agenda WHERE expediente_id = %s", (exp_id,))
    _ejecutar("DELETE FROM caso_documentos WHERE expediente_id = %s", (exp_id,))
    _ejecutar("UPDATE conversaciones SET expediente_id = NULL WHERE expediente_id = %s", (exp_id,))
    _ejecutar("DELETE FROM casos WHERE id = %s", (exp_id,))


def _tocado(exp_id: int):
    """Sube el expediente en la lista: se acaba de trabajar en él."""
    _ejecutar("UPDATE casos SET actualizado = %s WHERE id = %s", (int(time.time()), exp_id))


# ── Agenda ───────────────────────────────────────
def _fecha(texto) -> str:
    try:
        return date.fromisoformat(str(texto or "").strip()).isoformat()
    except ValueError:
        raise ValueError("Elija la fecha.") from None


def _hora(texto) -> str:
    """HH:MM, o vacía si es para todo el día (un plazo que vence ese día)."""
    texto = str(texto or "").strip()
    if not texto:
        return ""
    try:
        return datetime.strptime(texto, "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError("La hora no se entiende.") from None


def _fila_fecha(u: dict, fecha_id: int) -> dict:
    filas = _ejecutar(f"SELECT a.* FROM agenda a WHERE a.id = %s AND {_visible('a')}",
                      (fecha_id, *_quien(u)), leer=True)
    if not filas:
        raise LookupError("Esa fecha ya no está en la agenda.")
    return filas[0]


def agenda(u: dict, desde: str, hasta: str) -> list:
    """Las fechas entre dos días (los dos incluidos), con el cliente del expediente y quién la lleva."""
    filas = _ejecutar(
        "SELECT a.id, a.tipo, a.titulo, a.fecha, a.hora, a.lugar, a.notas, a.expediente_id, a.responsable_id, "
        f"a.oficina_id, x.cliente, x.asunto, {_NOMBRE.format('r')} AS responsable FROM agenda a "
        "LEFT JOIN casos x ON x.id = a.expediente_id LEFT JOIN usuarios r ON r.id = a.responsable_id "
        f"WHERE a.fecha >= %s AND a.fecha <= %s AND {_visible('a')} ORDER BY a.fecha, a.hora",
        (_fecha(desde), _fecha(hasta), *_quien(u)), leer=True)
    for f in filas:
        exp_id, cliente, asunto = f.pop("expediente_id"), f.pop("cliente"), f.pop("asunto")
        f["expediente"] = {"id": exp_id, "cliente": cliente, "asunto": asunto} if exp_id and cliente else None
    return [_con_responsable(f) for f in filas]


def guardar_fecha(u: dict, fecha_id, datos: dict) -> int:
    """Crea la fecha (fecha_id None) o la cambia; devuelve su id. Si es de un expediente, es de su oficina."""
    titulo = _limpio(datos, "titulo", LARGOS_FECHA["titulo"])
    if not titulo:
        raise ValueError("Escriba qué es: por ejemplo, «Audiencia de fondo».")
    tipo = datos.get("tipo") or "audiencia"
    if tipo not in TIPOS:
        raise ValueError("Tipo de fecha desconocido.")
    fecha, hora = _fecha(datos.get("fecha")), _hora(datos.get("hora"))
    lugar = _limpio(datos, "lugar", LARGOS_FECHA["lugar"])
    notas = _limpio(datos, "notas", LARGOS_FECHA["notas"])
    responsable = _responsable(u, datos.get("responsable_id"))
    uid, oid = _quien(u)
    exp_id = datos.get("expediente_id") or None
    if exp_id:
        oid = _expediente(u, exp_id)["oficina_id"]
    if fecha_id:
        _fila_fecha(u, fecha_id)
        _ejecutar("UPDATE agenda SET tipo = %s, titulo = %s, fecha = %s, hora = %s, lugar = %s, notas = %s, "
                  "expediente_id = %s, responsable_id = %s, oficina_id = %s WHERE id = %s",
                  (tipo, titulo, fecha, hora, lugar, notas, exp_id, responsable, oid, fecha_id))
    else:
        if _ejecutar(f"SELECT COUNT(*) AS n FROM agenda a WHERE {_visible('a')}", _quien(u),
                     leer=True)[0]["n"] >= MAX_FECHAS:
            raise ValueError(f"La agenda ya tiene {MAX_FECHAS} fechas. Borre las viejas para agregar otra.")
        fecha_id = _ejecutar("INSERT INTO agenda (usuario_id, oficina_id, responsable_id, expediente_id, tipo, titulo, "
                             "fecha, hora, lugar, notas, creado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                             "RETURNING id", (uid, oid, responsable, exp_id, tipo, titulo, fecha, hora, lugar, notas,
                                              int(time.time())), leer=True)[0]["id"]
    if exp_id:
        _tocado(exp_id)
    return fecha_id


def borrar_fecha(u: dict, fecha_id: int):
    _fila_fecha(u, fecha_id)
    _ejecutar("DELETE FROM agenda WHERE id = %s", (fecha_id,))


# ── Lo que el abogado guarda en un expediente ────
def poner_conversacion(u: dict, conv_id: int, exp_id):
    """Guarda la conversación (y su escrito) en un expediente; exp_id None la saca del que estaba."""
    if exp_id:
        _expediente(u, exp_id)
    if not _ejecutar("SELECT id FROM conversaciones WHERE id = %s AND usuario_id = %s", (conv_id, u["id"]), leer=True):
        raise LookupError("Esa conversación ya no existe.")
    _ejecutar("UPDATE conversaciones SET expediente_id = %s WHERE id = %s AND usuario_id = %s",
              (exp_id or None, conv_id, u["id"]))
    if exp_id:
        _tocado(exp_id)


def de_conversacion(u: dict, conv_id: int):
    """El expediente donde está guardada la conversación ({id, cliente}), o None (también si ya no lo ve)."""
    filas = _ejecutar("SELECT expediente_id FROM conversaciones WHERE id = %s AND usuario_id = %s",
                      (conv_id, u["id"]), leer=True)
    if not filas or not filas[0]["expediente_id"]:
        return None
    try:
        x = _expediente(u, filas[0]["expediente_id"])
    except LookupError:
        return None
    return {"id": x["id"], "cliente": x["cliente"]}


def poner_documento(u: dict, exp_id: int, doc_id: int, nombre: str):
    """Guarda en el expediente uno de sus documentos de la Biblioteca (servidor.py revisa que sea suyo)."""
    _expediente(u, exp_id)
    if not _ejecutar("SELECT doc_id FROM caso_documentos WHERE expediente_id = %s AND usuario_id = %s "
                     "AND doc_id = %s", (exp_id, u["id"], doc_id), leer=True):
        _ejecutar("INSERT INTO caso_documentos (expediente_id, usuario_id, doc_id, nombre) "
                  "VALUES (%s, %s, %s, %s)", (exp_id, u["id"], doc_id, " ".join(nombre.split())[:200]))
    _tocado(exp_id)


def quitar_documento(u: dict, exp_id: int, doc_id: int):
    _expediente(u, exp_id)
    _ejecutar("DELETE FROM caso_documentos WHERE expediente_id = %s AND usuario_id = %s AND doc_id = %s",
              (exp_id, u["id"], doc_id))
