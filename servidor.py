"""
Servidor de la app nueva: la API para las pantallas de React (carpeta web/)
==========================================================================
Python sigue haciendo el trabajo de fondo (cuentas, búsqueda, IA, prestaciones, Word y PDF);
este archivo solo lo ofrece por HTTP y entrega las pantallas ya armadas (web/dist).
La app de Flet (main.py) sigue funcionando aparte hasta que se cambie en Render.

En local, en dos terminales:
    uvicorn servidor:app --reload --port 8000
    cd web && npm run dev          → http://localhost:5173 (pasa /api al puerto 8000)

La sesión es la misma de siempre (tabla sesiones de cuentas.py), guardada en una cookie
que el navegador no deja leer a JavaScript.
"""

import json, logging, os, pathlib, queue, re, secrets, threading, time, uuid
from html import escape
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote, urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

import cuentas
import expedientes
import historial
import modelos
import pagos
import redaccion
import redactar
import temas
from generators import generar_expedientes, generar_escrito, pdf_escrito, nombre_escrito
from jurisprudencia import basedatos as juris_db, buscador as juris_buscar, ia as juris_ia, procesar as juris_proc
from jurisprudencia import visor as juris_visor, prestaciones as juris_prestaciones

ZONA_RD      = timezone(timedelta(hours=-4))   # República Dominicana no cambia la hora en verano
COOKIE       = "sesion"
DIR_SUBIDAS  = pathlib.Path("uploads")
MAX_MB_SUBIDA = 20
PANTALLAS    = pathlib.Path(__file__).parent / "web" / "dist"
# en Render (o con APP_URL en https) la cookie solo viaja por https
SEGURO       = bool(os.environ.get("RENDER")) or os.environ.get("APP_URL", "").startswith("https")
# el visor solo abre PDFs de estas fuentes oficiales (no cualquier dirección que llegue en la petición)
FUENTES_PERMITIDAS = (
    "https://consultaglobal.blob.core.windows.net/boletines/",            # Boletín Judicial
    "https://ri.gob.do/",                                                 # Registro Inmobiliario
    "https://transparencia.poderjudicial.gob.do/",                        # resoluciones del Poder Judicial
    "https://cdn.jsdelivr.net/gh/yeisondev001/sistema-de-solicitudes-legales@",   # leyes/ de este repo
)

app = FastAPI(title="Papiniano", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def _cabeceras_de_seguridad(request: Request, call_next):
    """Cabeceras que cierran puertas comunes: que otra página no meta esta en un marco (clickjacking), que el
    navegador no adivine tipos de archivo, que no regale la dirección completa al salir y que solo se pueda usar
    el micrófono desde aquí (el dictado). En https, que el navegador no vuelva a pedir http."""
    r = await call_next(request)
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    r.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    r.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=(), payment=()")
    if SEGURO:
        r.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return r


@app.exception_handler(Exception)
async def _error_inesperado(request: Request, ex: Exception):
    """Un fallo que no previmos: queda en el registro y en el panel «Errores» del administrador, y el abogado ve un
    mensaje claro. Se guarda el tipo de error, dónde ocurrió y a qué cuenta le pasó (solo eso; nunca el contenido
    de lo que subió)."""
    import traceback
    logging.getLogger("papiniano").exception("Error en %s %s", request.method, request.url.path)
    uid = None
    try:
        uid = (cuentas.usuario_de_sesion(request.cookies.get(COOKIE, "")) or {}).get("id")
    except Exception:
        pass   # sin sesión no se sabe quién fue; el error se registra igual
    try:
        cuentas.registrar_error(request.method, request.url.path, type(ex).__name__, str(ex),
                                "".join(traceback.format_exception(type(ex), ex, ex.__traceback__)), uid)
        if uid is not None:
            _abiertos().add((uid, request.url.path))
    except Exception:
        pass   # si ni el panel se puede escribir, el registro de Render igual lo tiene
    return JSONResponse({"detail": "Algo falló de nuestro lado y ya quedó registrado. Intente de nuevo; "
                                   "si sigue, escríbanos a soportepapiniano@gmail.com."}, status_code=500)


# ── SESIÓN ───────────────────────────────────────
def _poner_sesion(respuesta: Response, token: str):
    respuesta.set_cookie(COOKIE, token, max_age=cuentas.DURACION_SESION, httponly=True, samesite="lax",
                         secure=SEGURO, path="/")


# los errores que esperan que la cuenta vuelva a intentarlo: si entra bien a la misma ruta, quedan marcados como resueltos
_ABIERTOS: set | None = None


def _abiertos() -> set:
    global _ABIERTOS
    if _ABIERTOS is None:
        _ABIERTOS = {(x["usuario_id"], x["ruta"]) for x in cuentas.errores_abiertos()}
    return _ABIERTOS


def _si_resuelve(usuario_id: int, ruta: str):
    """Si esta cuenta tenía un error abierto en esta ruta y el pedido entró bien, ese error queda resuelto."""
    try:
        if (usuario_id, ruta) in _abiertos():
            cuentas.marcar_resuelto(usuario_id, ruta)
            _abiertos().discard((usuario_id, ruta))
    except Exception:
        pass   # marcar el resuelto no puede estorbar el pedido del abogado


def usuario_actual(request: Request) -> dict:
    try:
        u = cuentas.usuario_de_sesion(request.cookies.get(COOKIE, ""))
    except Exception:
        raise HTTPException(503, "No se pudo conectar con la base de datos. Intente en un momento.")
    if not u:
        raise HTTPException(401, "Su sesión terminó. Entre otra vez.")
    _si_resuelve(u["id"], request.url.path)
    return u


def usuario_para_pagar(request: Request) -> dict:
    """Como usuario_actual, pero también deja pasar a quien solo le falta pagar (prueba terminada o plan vencido)."""
    try:
        u = cuentas.usuario_de_sesion(request.cookies.get(COOKIE, ""), para_pagar=True)
    except Exception:
        raise HTTPException(503, "No se pudo conectar con la base de datos. Intente en un momento.")
    if not u:
        raise HTTPException(401, "Su sesión terminó. Entre otra vez.")
    return u


def _colores(clave) -> dict:
    t = temas.tema(clave)
    return {**{n: t[n] for n in temas.NOMBRES}, "oscuro": t["oscuro"]}


def _perfil(u: dict) -> dict:
    """Lo que las pantallas necesitan saber de la cuenta: datos, tema y, en prueba, lo que le queda."""
    perfil = {k: u[k] for k in ("id", "usuario", "nombre", "es_admin", "email", "plan", "plantillas", "oficina")}
    perfil["tema"] = u["tema"] or temas.MARCA
    perfil["colores"] = _colores(u["tema"])
    perfil["letra"] = u.get("letra") or "normal"
    perfil["propios"] = cuentas.con_propios(u["plan"])
    perfil["por_pagar"] = bool(u.get("por_pagar"))
    perfil["prueba"] = perfil["basico"] = None
    # la cajita de lo que le queda: solo en la prueba y en el Aspirante (el Abogado no ve su tope)
    tope = cuentas.tope_diario(u["plan"]) if u["plan"] in ("prueba", "basico") else None
    if tope:
        try:
            hoy = cuentas.preguntas_de_hoy(u["id"])
        except Exception:
            hoy = 0
        if u["plan"] == "prueba":
            perfil["prueba"] = {"dias": max(0, int(((u.get("prueba_hasta") or 0) - time.time() + 86399) // 86400)),
                                "preguntas_hoy": hoy, "tope": tope}
        else:
            perfil["basico"] = {"preguntas_hoy": hoy, "tope": tope}
    return perfil


# ── ENTRADA ──────────────────────────────────────
def _google() -> tuple:
    """(id de cliente, secreto) si Entrar con Google está configurado; si no, None.
    En Google Cloud, la URL de redirección autorizada es <dirección de la app>/oauth_callback."""
    cliente = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    secreto = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    return (cliente, secreto) if cliente and secreto else None


def _vuelta_google(request: Request) -> str:
    # Render pone la dirección pública en RENDER_EXTERNAL_URL; en local, APP_URL o la del navegador
    base = os.environ.get("APP_URL") or os.environ.get("RENDER_EXTERNAL_URL") or str(request.base_url)
    return base.rstrip("/") + "/oauth_callback"


@app.get("/api/entrada")
def entrada():
    """Cómo se muestra la entrada: la primera vez se crea el administrador; si no, Google y usuario."""
    try:
        primera_vez = not cuentas.hay_usuarios()
    except Exception as ex:
        raise HTTPException(503, f"No se pudo conectar con la base de datos: {ex}")
    pide_codigo = primera_vez and bool(historial.DATABASE_URL)
    return {"primera_vez": primera_vez, "google": bool(_google()) and not primera_vez, "pide_codigo": pide_codigo,
            "falta_codigo": pide_codigo and not os.environ.get("CODIGO_INSTALACION", "").strip(),
            "dias_prueba": cuentas.DIAS_PRUEBA, "preguntas_prueba": cuentas.PREGUNTAS_PRUEBA,
            "preguntas_basico": cuentas.PREGUNTAS_BASICO, "colores": _colores(temas.MARCA)}


class Credenciales(BaseModel):
    usuario: str
    clave: str


class NuevoAdmin(BaseModel):
    nombre: str = ""
    usuario: str
    clave: str
    clave2: str
    codigo: str = ""


# ── Candados contra bots ─────────────────────────
# Van en la memoria del servidor: apenas pesan y se reinician cuando el servicio se reinicia.

def _ip(request: Request) -> str:
    # Render pone la IP real del visitante en este encabezado
    return request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else "?")

_INTENTOS: dict = {}   # (ip, clave) → (momento del último intento fallido, cuántos fallidos seguidos)
_NUEVAS: dict = {}     # ip → momentos de las cuentas nuevas creadas desde esa conexión


def _demasiados_intentos(request: Request, clave: str) -> bool:
    """Fuerza bruta: 6 intentos fallidos de entrada en 15 minutos bloquean esa IP y usuario 15 minutos."""
    ip, ahora = _ip(request), time.time()
    for k in [k for k in _INTENTOS if ahora - _INTENTOS[k][0] > 900]:
        _INTENTOS.pop(k)   # van venciendo solos, sin crecer de más
    ultimo, n = _INTENTOS.get((ip, clave), (0, 0))
    return ahora - ultimo <= 900 and n >= 6


def _fallo(request: Request, clave: str):
    k = (_ip(request), clave)
    ultimo, n = _INTENTOS.get(k, (0, 0))
    _INTENTOS[k] = (time.time(), n + 1 if time.time() - ultimo <= 900 else 1)


def _demasiados_registros(request: Request) -> bool:
    """Fábricas de cuentas de prueba: máximo 20 cuentas nuevas de Google por hora desde la misma IP."""
    ip, ahora = _ip(request), time.time()
    _NUEVAS[ip] = [t for t in _NUEVAS.get(ip, []) if ahora - t < 3600]
    return len(_NUEVAS[ip]) >= 20


def _cuenta_nueva(request: Request):
    _NUEVAS.setdefault(_ip(request), []).append(time.time())


def _entrar(respuesta: Response, usuario: str, clave: str, request: Request = None) -> dict:
    clave_entrada = "entrar:" + usuario.strip().lower()
    if request is not None and _demasiados_intentos(request, clave_entrada):
        raise HTTPException(429, "Demasiados intentos seguidos. Espere unos minutos y vuelva a intentar.")
    try:
        r = cuentas.iniciar_sesion(usuario, clave)
    except Exception as ex:
        raise HTTPException(503, f"No se pudo conectar: {ex}")
    if not r:
        if request is not None:
            _fallo(request, clave_entrada)
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    if request is not None:
        _INTENTOS.pop((_ip(request), clave_entrada), None)   # entró bien: se limpia su cuenta de fallos
    _poner_sesion(respuesta, r[1])
    return _perfil(r[0])


@app.post("/api/entrar")
def entrar(datos: Credenciales, respuesta: Response, request: Request):
    return _entrar(respuesta, datos.usuario, datos.clave, request)


@app.post("/api/crear-admin")
def crear_admin(datos: NuevoAdmin, respuesta: Response, request: Request):
    """Solo la primera vez: crea la cuenta principal (en el servidor exige el código de instalación)."""
    if cuentas.hay_usuarios():
        raise HTTPException(409, "El administrador ya existe. Entre con su usuario.")
    codigo = os.environ.get("CODIGO_INSTALACION", "").strip()
    if historial.DATABASE_URL and (not codigo or datos.codigo.strip() != codigo):
        raise HTTPException(403, "Código de instalación incorrecto.")
    if datos.clave != datos.clave2:
        raise HTTPException(400, "Las contraseñas no coinciden.")
    try:
        cuentas.crear_usuario(datos.usuario, datos.clave, datos.nombre, es_admin=True, plantillas=True)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return _entrar(respuesta, datos.usuario, datos.clave, request)


@app.get("/api/google")
def google_ir(request: Request):
    g = _google()
    if not g:
        raise HTTPException(404, "Entrar con Google no está configurado.")
    estado = secrets.token_urlsafe(24)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": g[0], "redirect_uri": _vuelta_google(request), "response_type": "code",
        "scope": "openid email profile", "state": estado, "prompt": "select_account"})
    r = RedirectResponse(url, 302)
    # el estado se compara a la vuelta: así nadie puede meter a otra persona en su cuenta
    r.set_cookie("google_estado", estado, max_age=600, httponly=True, samesite="lax", secure=SEGURO, path="/")
    return r


@app.get("/oauth_callback")
def google_vuelta(request: Request, code: str = "", state: str = "", error: str = ""):
    def volver(motivo):
        r = RedirectResponse("/entrar?error=" + quote(motivo), 302)
        r.delete_cookie("google_estado", path="/")
        return r

    g = _google()
    if not g or error or not code or not state or state != request.cookies.get("google_estado"):
        return volver("No se completó la entrada con Google. Intente otra vez.")
    if _demasiados_registros(request):
        return volver("Se crearon demasiadas cuentas desde esta conexión. Intente más tarde.")
    try:
        tok = httpx.post("https://oauth2.googleapis.com/token", timeout=20, data={
            "code": code, "client_id": g[0], "client_secret": g[1],
            "redirect_uri": _vuelta_google(request), "grant_type": "authorization_code"})
        tok.raise_for_status()
        datos = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", timeout=20,
                          headers={"Authorization": f"Bearer {tok.json()['access_token']}"}).json()
        u, token = cuentas.entrar_con_google(datos.get("email", ""), datos.get("name", ""),
                                             bool(datos.get("email_verified")))
    except ValueError as ex:
        return volver(str(ex))
    except Exception:
        return volver("No se pudo entrar con Google. Intente otra vez en un momento.")
    _cuenta_nueva(request)
    r = RedirectResponse("/", 302)
    r.delete_cookie("google_estado", path="/")
    _poner_sesion(r, token)
    return r


@app.post("/api/salir")
def salir(request: Request, respuesta: Response):
    try:
        cuentas.cerrar_sesion(request.cookies.get(COOKIE, ""))
    except Exception:
        pass
    respuesta.delete_cookie(COOKIE, path="/")
    return {"ok": True}


# ── CUENTA ───────────────────────────────────────
@app.get("/api/sesion")
def sesion(u=Depends(usuario_para_pagar)):
    return _perfil(u)


# ── PAGOS (Polar) ────────────────────────────────
def _direccion(request: Request) -> str:
    base = os.environ.get("APP_URL") or os.environ.get("RENDER_EXTERNAL_URL") or str(request.base_url)
    return base.rstrip("/")


@app.get("/api/pagos")
def pagos_estado(u=Depends(usuario_para_pagar)):
    return {"activo": pagos.configurado(), "oficina": bool(u.get("oficina"))}


class PedidoPago(BaseModel):
    plan: str
    ciclo: str


@app.post("/api/pagos/pagar")
def pagos_pagar(datos: PedidoPago, request: Request, u=Depends(usuario_para_pagar)):
    try:
        return {"url": pagos.crear_pago(u, datos.plan, datos.ciclo, _direccion(request) + "/plan?pago=ok")}
    except pagos.ErrorPago as ex:
        raise HTTPException(400, str(ex))


@app.post("/api/pagos/portal")
def pagos_portal(u=Depends(usuario_para_pagar)):
    try:
        return {"url": pagos.crear_portal(u)}
    except pagos.ErrorPago as ex:
        raise HTTPException(400, str(ex))


@app.post("/api/pagos/aviso")
async def pagos_aviso(request: Request):
    """Polar avisa aquí cada pago, cambio o cancelación. Solo vale si trae la firma correcta."""
    cuerpo = await request.body()
    if not pagos.firma_valida(cuerpo, request.headers):
        raise HTTPException(401, "Firma no válida.")
    try:
        hecho = pagos.procesar(cuerpo)
    except ValueError:
        raise HTTPException(400, "Aviso mal formado.")
    logging.getLogger("papiniano").info("Aviso de Polar: %s", hecho)
    return {"ok": True, "hecho": hecho}


@app.get("/api/temas")
def lista_temas():
    return [{"clave": k, "nombre": t["nombre"], "descripcion": t["descripcion"], "colores": _colores(k)}
            for k, t in temas.TEMAS.items()]


LETRAS = ("normal", "grande", "muy_grande")


class Tema(BaseModel):
    tema: str


class Letra(BaseModel):
    letra: str


@app.post("/api/letra")
def cambiar_letra(datos: Letra, u=Depends(usuario_actual)):
    if datos.letra not in LETRAS:
        raise HTTPException(400, "Ese tamaño de letra no existe.")
    cuentas.cambiar_letra(u["id"], "" if datos.letra == "normal" else datos.letra)
    return _perfil({**u, "letra": datos.letra})


@app.post("/api/tema")
def cambiar_tema(datos: Tema, u=Depends(usuario_actual)):
    if datos.tema not in temas.TEMAS:
        raise HTTPException(400, "Ese tema no existe.")
    cuentas.cambiar_tema(u["id"], "" if datos.tema == temas.MARCA else datos.tema)
    return _perfil({**u, "tema": datos.tema})


# ── ESCRITORIO ───────────────────────────────────
def _dias_para(fecha: str):
    """Días que faltan para una fecha DD/MM/AAAA (None si no se entiende)."""
    try:
        return (datetime.strptime(fecha.strip(), "%d/%m/%Y").date() - datetime.now(ZONA_RD).date()).days
    except ValueError:
        return None


@app.get("/api/audiencias")
def audiencias(u=Depends(usuario_actual)):
    """Las audiencias de los próximos 7 días, del historial de reportes (solo cuentas con plantillas)."""
    if not u["plantillas"]:
        return []
    proximas = []
    for ent in historial.listar():
        dias = _dias_para(ent["fecha_proxima"] or "")
        if dias is not None and 0 <= dias <= 7:
            proximas.append({"id": ent["id"], "dias": dias, "fecha": ent["fecha_proxima"].strip(),
                             **{k: ent[k] for k in ("recurrente", "expediente", "tribunal")}})
    return sorted(proximas, key=lambda a: a["dias"])


# ── ASISTENTE ────────────────────────────────────
# el plan Aspirante redacta pocos escritos al mes y solo con los modelos de todos: sus propios modelos y
# documentos son del plan Abogado
SIN_PROPIOS = ("Sus propios modelos y documentos vienen con el plan Abogado. Con el plan Aspirante puede usar "
               "nuestros modelos. Para pasar al plan Abogado, escríbanos.")


def _plan_topes(u: dict) -> str:
    """El plan que manda en los topes de preguntas y escritos: los administradores no tienen."""
    return "beta" if u.get("es_admin") else u["plan"]


def _sin_escritos(u: dict) -> str | None:
    """El aviso si ya hizo este mes los escritos nuevos de su plan; None si le quedan."""
    try:
        cuentas.revisar_escritos(u["id"], _plan_topes(u))
    except ValueError as ex:
        return str(ex)
    except Exception:
        pass   # si no se puede contar, no se le niega el escrito
    return None


def _con_referencia(mensajes: list) -> list:
    """Cada fuente lleva cómo se cita, así las pantallas no repiten esa regla."""
    for m in mensajes:
        for f in m.get("fuentes") or []:
            f["referencia"] = juris_buscar.referencia(f)
    return mensajes


@app.get("/api/conversaciones")
def conversaciones(u=Depends(usuario_actual)):
    return cuentas.listar_conversaciones(u["id"])


@app.get("/api/conversaciones/{conv_id}")
def conversacion(conv_id: int, u=Depends(usuario_actual)):
    mensajes = cuentas.abrir_conversacion(u["id"], conv_id)
    if not mensajes:
        raise HTTPException(404, "Esa conversación ya no existe.")
    try:
        expediente = expedientes.de_conversacion(u, conv_id) if cuentas.con_propios(u["plan"]) else None
    except Exception:
        expediente = None   # si no se puede leer, la conversación se abre igual
    return {"id": conv_id, "mensajes": _con_referencia(mensajes), "escrito": cuentas.leer_escrito(u["id"], conv_id),
            "expediente": expediente}


@app.delete("/api/conversaciones/{conv_id}")
def borrar_conversacion(conv_id: int, u=Depends(usuario_actual)):
    cuentas.borrar_conversacion(u["id"], conv_id)
    return {"ok": True}


class Pregunta(BaseModel):
    texto: str
    conv_id: int | None = None
    # el modelo que eligió el abogado para el escrito; "ninguno": lo quiere sin modelo
    modelo: str | None = None
    # una conversación nueva que empieza desde un expediente queda guardada en él
    expediente_id: int | None = None


def _modelo(clave: str, u: dict):
    """(ficha, texto) de un modelo de todos, de los del abogado o de los que comparte su oficina;
    (None, None) si no existe."""
    propio = modelos.id_propio(clave)
    if propio is None:
        return modelos.ficha(clave), modelos.texto(clave)
    fila = cuentas.leer_modelo(u["id"], propio)
    return (modelos.propio(fila, u["id"]), fila["texto"]) if fila else (None, None)


def _modelos_del_abogado(u: dict) -> list:
    """Los suyos y los que comparten sus colegas de oficina, con la misma forma que los de todos."""
    filas = cuentas.listar_modelos_propios(u["id"])
    if u.get("oficina"):
        filas += cuentas.listar_modelos_oficina(u["id"])
    return [modelos.propio(f, u["id"]) for f in filas]


def _usar_modelo(clave: str, hay_escrito: bool, u: dict) -> dict:
    """Pone el modelo en la hoja tal cual, sin la IA, y le pide al abogado los datos por llenar."""
    ficha, texto = _modelo(clave, u)
    if not texto:
        return {"rol": "asistente", "texto": "_Ese modelo ya no está. Elija otro en «Modelos»._"}
    return {"rol": "asistente", "escrito_nuevo": texto, "escrito": "cambiado" if hay_escrito else "nuevo",
            "pedir_datos": True,
            "texto": f"Listo, puse el modelo **«{ficha['nombre']}»** en la hoja. Ahora llene los datos del caso: "
                     "lo que no tenga a mano déjelo en blanco y le aviso antes de descargar. Si quiere cambiar "
                     "algo del modelo, dígamelo aquí."}


def _sugerir_modelos(q: str, plan: dict, u: dict) -> dict | None:
    """Antes de redactar un escrito nuevo, Papiniano ofrece los modelos que sirven para eso (también los suyos
    y los de su oficina)."""
    try:
        propios = _modelos_del_abogado(u)
    except Exception:
        propios = []   # si no se pueden leer los suyos, se ofrecen los de todos
    sugeridos = modelos.sugerir(f"{q} {plan['consulta']}", propios=propios)
    if not sugeridos:
        return None
    uno = len(sugeridos) == 1
    return {"rol": "asistente", "modelos": sugeridos, "pedido": q,
            "texto": ("Para eso tengo un modelo. ¿Lo usamos?" if uno else
                      f"Para eso tengo {len(sugeridos)} modelos. ¿Usamos uno?")
                     + " Le pido los datos del caso y no se me escapa ninguno. Si prefiere, lo redacto sin modelo."}


def _escribir(q: str, plan: dict, historial_chat: list, actual: str, u: dict, avance) -> dict:
    """Papiniano redacta el escrito o lo cambia. El texto nuevo va en turno["escrito_nuevo"]."""
    turno = {"rol": "asistente", "texto": "", "fuentes": [], "citadas": []}
    # «agréguele eso al escrito» justo después de una consulta: se usan las sentencias de esa respuesta
    previa = next((t for t in reversed(historial_chat) if t.get("rol") == "asistente"), {})
    fuentes = [] if previa.get("escrito") else (previa.get("fuentes") or [])
    if plan["busquedas"]:
        avance("Buscando las leyes y sentencias para el escrito…", True)
        try:
            fuentes = juris_buscar.buscar(plan["busquedas"], u["id"], limite=juris_ia.MAX_FUENTES,
                                          pregunta=plan["consulta"]) or []
        except Exception as ex:
            print(f"La búsqueda falló: {ex}", flush=True)   # el escrito se arma igual, sin fuentes
    avance("Cambiando el escrito…" if actual else "Escribiendo el escrito…", True)
    try:
        r = juris_ia.escribir(q, actual, fuentes, juris_buscar.referencia, historial_chat,
                              existen=juris_buscar.articulos_existentes)
    except juris_ia.LimiteAlcanzado:
        turno["texto"] = "_Se alcanzó el límite gratis de la IA por ahora; intente en un minuto._"
        return turno
    except (ValueError, KeyError) as ex:
        print(f"El escrito falló: {ex}", flush=True)
        turno["texto"] = "_No pude hacer eso en el escrito. Dígamelo con otras palabras o intente de nuevo._"
        return turno
    turno.update(texto=r["mensaje"], citadas=r["citadas"], fuentes=fuentes, ia=True)
    if r["escrito"]:
        turno["escrito_nuevo"] = r["escrito"]
        turno["escrito"] = "cambiado" if actual else "nuevo"
    return turno


def _responder(q: str, historial_chat: list, u: dict, avance, escrito: str = "", modelo: str | None = None) -> dict:
    """La respuesta del asistente a una pregunta (lo mismo que hacía la pantalla de Flet), o el escrito."""
    turno = {"rol": "asistente", "texto": "", "fuentes": [], "citadas": []}
    plan = (juris_ia.preparar_busqueda(q, historial_chat, hay_escrito=bool(escrito)) if juris_ia.disponible()
            else {"tipo": "nueva", "consulta": q, "busquedas": [q]})
    if plan["tipo"] == "escrito":
        # cambiar el escrito que ya está no cuenta; uno nuevo, sí
        aviso = None if escrito else _sin_escritos(u)
        if aviso:
            turno["texto"] = aviso
            return turno
        # un escrito nuevo: primero se ofrecen los modelos (salvo que ya dijo que lo quiere sin modelo)
        if not escrito and modelo != "ninguno":
            sugerencia = _sugerir_modelos(q, plan, u)
            if sugerencia:
                return sugerencia
        return _escribir(q, plan, historial_chat, escrito, u, avance)
    anteriores = next((t["fuentes"] for t in reversed(historial_chat) if t.get("fuentes")), [])
    if plan["tipo"] == "no_juridica":
        turno["texto"] = juris_ia.no_es_consulta(q)
        return turno
    if plan["tipo"] == "seguimiento" and anteriores:
        fuentes = anteriores   # "explíquelo más simple": las mismas sentencias
    else:
        avance("Buscando en las sentencias…")
        try:
            fuentes = juris_buscar.buscar(plan["busquedas"] or [plan["consulta"]], u["id"],
                                          limite=juris_ia.MAX_FUENTES, pregunta=plan["consulta"])
        except Exception as ex:
            print(f"La búsqueda falló: {ex}", flush=True)
            fuentes = None   # la biblioteca no respondió (la base gratis puede estar despertando)
    turno["fuentes"] = fuentes or []
    # prestaciones con salario y tiempo: los montos los calcula la app con las fórmulas fijas, la IA solo
    # los explica; así la tabla sale aunque no haya fuentes, la biblioteca no responda o la IA no esté
    calculo = juris_prestaciones.calcular(q) or juris_prestaciones.calcular(plan["consulta"])
    tabla = juris_prestaciones.para_mostrar(calculo) + "\n\n" if calculo else ""
    if fuentes is None:
        turno["texto"] = tabla + ("_No pude conectarme con la biblioteca de sentencias en este momento. "
                                  "Intente de nuevo en un minuto._")
    elif not fuentes:
        turno["texto"] = tabla + ("No encontré sentencias sobre eso. Pruebe a decirlo con otras palabras, "
                                  "o suba sus propios documentos en la Biblioteca.")
    elif juris_ia.disponible():
        avance("Analizando las sentencias…")
        try:
            r = juris_ia.responder(q, fuentes, juris_buscar.referencia, historial_chat, calculo)
            turno.update(texto=r["texto"], citadas=r["citadas"], ia=True)
        except juris_ia.LimiteAlcanzado:
            turno["texto"] = tabla + ("_Se alcanzó el límite gratis de la IA por ahora; intente en un minuto. "
                                      "Mientras tanto, abajo están las sentencias encontradas._")
    else:
        print(f"IA no disponible (claves: {juris_ia.estado()})", flush=True)
        turno["texto"] = tabla + ("_Papiniano no puede analizar en este momento. "
                                  "Abajo están las sentencias encontradas._")
    return turno


@app.post("/api/asistente")
def preguntar(datos: Pregunta, u=Depends(usuario_actual)):
    """Responde por partes (una línea JSON por evento): primero los avances («Buscando…»)
    y al final {"turno": …, "conv_id": …}. La conversación se guarda en la base."""
    q = datos.texto.strip()
    if len(q) < 2:
        raise HTTPException(400, "Escriba su consulta.")
    if not juris_db.configurada():
        raise HTTPException(503, "Falta configurar el buscador (variable JURIS_DATABASE_URL).")
    historial_chat = cuentas.abrir_conversacion(u["id"], datos.conv_id) if datos.conv_id else []
    try:
        escrito = (cuentas.leer_escrito(u["id"], datos.conv_id) or {}).get("texto", "") if datos.conv_id else ""
    except Exception:
        escrito = ""

    def linea(evento: dict) -> str:
        return json.dumps(evento, ensure_ascii=False, default=str) + "\n"

    def eventos():
        pregunta = {"rol": "usuario", "texto": q}
        guardar = True
        # eligió un modelo: va a la hoja sin pasar por la IA (no cuenta como consulta)
        if datos.modelo and datos.modelo != "ninguno":
            aviso = None if escrito else _sin_escritos(u)
            turno = {"rol": "asistente", "texto": aviso} if aviso else _usar_modelo(datos.modelo, bool(escrito), u)
        # un saludo o una prueba ("hola") no se busca: siempre saldría "lo más parecido"
        elif not juris_ia.parece_consulta(q):
            turno = {"rol": "asistente", "texto": juris_ia.no_es_consulta(q)}
        else:
            # cada plan tiene un máximo de preguntas por día
            try:
                cuentas.registrar_pregunta(u["id"], _plan_topes(u))
                limite = None
            except ValueError as ex:
                limite = str(ex)
            except Exception:
                limite = None   # si no se puede contar, no se le niega la pregunta
            if limite:
                turno, guardar = {"rol": "asistente", "texto": limite}, False
            else:
                yield linea({"avance": "Pensando…"})
                # la respuesta se arma en otro hilo para ir mandando los avances mientras tanto
                cola = queue.Queue()

                def trabajo():
                    try:
                        # avance(texto, True): está trabajando en el escrito (la pantalla abre la hoja)
                        cola.put(("turno", _responder(q, historial_chat, u,
                                                      lambda t, e=False: cola.put(("avance", (t, e))), escrito,
                                                      datos.modelo)))
                    except Exception as ex:
                        print(f"La consulta falló: {ex}", flush=True)
                        cola.put(("turno", {"rol": "asistente",
                                            "texto": "_No pude completar la consulta. Intente de nuevo en un momento._"}))

                threading.Thread(target=trabajo, daemon=True).start()
                while True:
                    tipo, valor = cola.get()
                    if tipo == "turno":
                        turno = valor
                        break
                    yield linea({"avance": valor[0], **({"escrito": True} if valor[1] else {})})
        conv_id = datos.conv_id
        # el escrito no va en los mensajes: se guarda aparte, con sus versiones para «Deshacer»
        nuevo_escrito = turno.pop("escrito_nuevo", None)
        if nuevo_escrito and turno.get("escrito") == "nuevo":
            try:
                cuentas.contar_escrito(u["id"])
            except Exception:
                pass   # si no se puede contar, el escrito igual se entrega
        escrito_listo = None
        if guardar:
            try:
                nueva = not conv_id
                conv_id = cuentas.guardar_conversacion(u["id"], conv_id, historial_chat + [pregunta, turno])
                if nueva and datos.expediente_id and cuentas.con_propios(u["plan"]):
                    try:
                        expedientes.poner_conversacion(u, conv_id, datos.expediente_id)
                    except (LookupError, ValueError):
                        pass   # el expediente ya no existe: la conversación queda suelta
                if nuevo_escrito:
                    escrito_listo = cuentas.guardar_escrito(u["id"], conv_id, nuevo_escrito)
            except Exception:
                pass   # si no se puede guardar, la respuesta igual se muestra
        if nuevo_escrito and not escrito_listo:
            escrito_listo = {"texto": nuevo_escrito, "deshacer": False}
        yield linea({"turno": _con_referencia([turno])[0], "conv_id": conv_id,
                     **({"escrito": escrito_listo} if escrito_listo else {})})

    return StreamingResponse(eventos(), media_type="application/x-ndjson")


# ── Sala «Redacción»: un escrito a partir del documento de la otra parte ─────
# Ley 172-13: el documento se lee y se le quitan los datos de las personas aquí, sin la IA (redactar.py).
# El abogado ve el texto ya sin datos antes de mandarlo; la lista de qué dato es cada uno vuelve solo a su
# navegador. A la IA y a la base de Papiniano solo llega el texto con [PERSONA 1], [CÉDULA 1]…
MAX_MB_REDACTAR = 20


@app.get("/api/redactar")
def redactar_tipos(u=Depends(usuario_actual)):
    """Los tipos de escrito, con lo que hay que subir, las preguntas de «Hacerlo yo mismo» y sus modelos."""
    return [{"clave": k, "nombre": t["nombre"], "documento": t["documento"], "preguntas": redactar.preguntas(k),
             "modelos": redactar.modelos_del_tipo(k)} for k, t in redactar.TIPOS.items()]


@app.post("/api/redactar/leer")
async def redactar_leer(request: Request, u=Depends(usuario_actual)):
    """Lee el PDF o Word y le quita los datos de las personas. No guarda nada ni usa la IA."""
    nombre = unquote(request.headers.get("X-Nombre", "")).strip() or "documento"
    contenido = await request.body()
    if len(contenido) > MAX_MB_REDACTAR * 1024 * 1024:
        raise HTTPException(413, f"«{nombre}» pesa más de {MAX_MB_REDACTAR} MB.")
    try:
        texto = redactar.leer(contenido, nombre)
    except ValueError as ex:
        raise HTTPException(422, str(ex))
    texto, mapa, cuenta = redactar.quitar_datos_caso(texto)
    return {"nombre": nombre, "texto": texto, "mapa": mapa, "cuenta": cuenta}


class PedidoRedactar(BaseModel):
    tipo: str
    # «documento»: a partir del documento de la otra parte; «propio»: con las respuestas del abogado
    modo: str = "documento"
    # el documento ya sin los datos de las personas (lo que devolvió /api/redactar/leer, quizá corregido)
    texto: str = ""
    nombre: str = "documento"
    indicaciones: str = ""
    # «Hacerlo yo mismo»: clave de la pregunta → respuesta, y el modelo que eligió (None: que elija Papiniano)
    respuestas: dict = {}
    modelo: str | None = None


def _guardar_redaccion(u: dict, pedido_usuario: str, texto: str, fuentes: list, r: dict) -> int:
    """La conversación nueva con el escrito en la hoja; cuenta como un escrito del mes."""
    mensajes = [{"rol": "usuario", "texto": pedido_usuario},
                {"rol": "asistente", "texto": texto, "fuentes": fuentes, "citadas": r["citadas"], "ia": True,
                 "escrito": "nuevo"}]
    conv_id = cuentas.guardar_conversacion(u["id"], None, mensajes)
    cuentas.guardar_escrito(u["id"], conv_id, r["escrito"])
    try:
        cuentas.contar_escrito(u["id"])
    except Exception:
        pass   # si no se puede contar, el escrito igual se entrega
    return conv_id


def _fuentes_para(busquedas: list, u: dict, avance) -> list:
    if not busquedas or not juris_db.configurada():
        return []
    avance("Buscando las leyes y sentencias…")
    try:
        return juris_buscar.buscar(busquedas, u["id"], limite=juris_ia.MAX_FUENTES, pregunta=busquedas[0]) or []
    except Exception as ex:
        print(f"La búsqueda falló: {ex}", flush=True)   # el escrito se arma igual, sin fuentes
        return []


def _redactar_propio(datos: PedidoRedactar, u: dict, avance) -> dict:
    """«Hacerlo yo mismo»: con las respuestas del abogado, el modelo y lo que se encuentre en la biblioteca."""
    t = redactar.TIPOS[datos.tipo]
    respuestas, mapa = redactar.respuestas_sin_datos(datos.tipo, datos.respuestas)

    avance("Eligiendo el modelo…")
    ficha = None
    if datos.modelo and datos.modelo != "ninguno":
        ficha, _ = _modelo(datos.modelo, u)
    if not ficha and datos.modelo != "ninguno":
        try:
            propios = _modelos_del_abogado(u) if cuentas.con_propios(u["plan"]) else []
        except Exception:
            propios = []
        ficha = redactar.elegir_modelo(datos.tipo, respuestas, propios)
    modelo_texto = (_modelo(ficha["clave"], u)[1] or "") if ficha else ""

    # las búsquedas salen de los hechos y los motivos: de ahí, los artículos de la biblioteca que encajan
    avance("Pensando qué buscar…")
    try:
        busquedas = juris_ia.generar_busquedas(f"{t['nombre']}. {respuestas[:1800]}")
    except juris_ia.LimiteAlcanzado:
        busquedas = []
    if not busquedas:
        busquedas = [" ".join(str(datos.respuestas.get(k) or "") for k in ("objeto", "motivos"))[:150]]
    fuentes = _fuentes_para([b for b in busquedas if b.strip()], u, avance)

    avance("Escribiendo el escrito…")
    r = juris_ia.escribir(redactar.pedido_propio(datos.tipo, respuestas, bool(modelo_texto)), modelo_texto, fuentes,
                          juris_buscar.referencia, None, existen=juris_buscar.articulos_existentes,
                          actual_es_del_abogado=False)
    if not r["escrito"]:
        raise ValueError("La IA no devolvió el escrito.")
    con_modelo = (f"con el modelo **«{ficha['nombre']}»**" if ficha else "sin modelo")
    texto = (f"Redacté {t['nombre'].lower()} {con_modelo}, con lo que me contó y las leyes y sentencias de la "
             f"biblioteca. Está en la hoja: revíselo y pídame los cambios que quiera.\n\n{r['mensaje']}\n\n"
             "_Los nombres, cédulas y domicilios van como datos por llenar y se ponen solo al descargar._")
    conv_id = _guardar_redaccion(u, f"{t['nombre']} con mis datos\n\n{respuestas}", texto, fuentes, r)
    return {"conv_id": conv_id, "mapa": mapa}


def _redactar(datos: PedidoRedactar, u: dict, avance) -> dict:
    """Analiza el documento, elige el modelo, busca las fuentes y redacta. Devuelve {"conv_id"}."""
    t = redactar.TIPOS[datos.tipo]
    avance("Leyendo el documento…")
    que_hacer = f"{t['nombre']}: {t['pedido']}" + (f". Indicaciones: {datos.indicaciones}" if datos.indicaciones else "")
    analisis = juris_ia.analizar_documento(redactar.para_ia(datos.texto), que_hacer)
    resumen = juris_ia.analisis_en_texto(analisis)

    avance("Eligiendo el modelo…")
    try:
        propios = _modelos_del_abogado(u) if cuentas.con_propios(u["plan"]) else []
    except Exception:
        propios = []
    caso = " ".join(str(analisis.get(k) or "") for k in ("materia", "documento", "pide_o_decide"))
    ficha = redactar.elegir_modelo(datos.tipo, caso, propios, str(analisis.get("materia") or ""))
    modelo_texto = (_modelo(ficha["clave"], u)[1] or "") if ficha else ""

    fuentes = _fuentes_para(analisis["busquedas"], u, avance)

    avance("Escribiendo el escrito…")
    pedido = redactar.pedido(datos.tipo, resumen, datos.indicaciones, bool(modelo_texto))
    r = juris_ia.escribir(pedido, modelo_texto, fuentes, juris_buscar.referencia, None,
                          existen=juris_buscar.articulos_existentes, actual_es_del_abogado=False)
    if not r["escrito"]:
        raise ValueError("La IA no devolvió el escrito.")

    con_modelo = (f"con el modelo **«{ficha['nombre']}»**" if ficha
                  else "sin modelo, porque todavía no tengo uno de este tipo")
    texto = (f"Leí «{datos.nombre}» y redacté {t['nombre'].lower()} {con_modelo}. Está en la hoja: revíselo "
             f"y pídame los cambios que quiera.\n\n{resumen}\n\n{r['mensaje']}\n\n"
             "_Los nombres, cédulas y domicilios del documento no se le mandaron a la IA: en el escrito van como "
             "[PERSONA 1], [CÉDULA 1]… y se llenan en «Datos por llenar» solo al descargar._")
    pedido_usuario = (f"{t['nombre']} a partir de «{datos.nombre}»"
                      + (f"\n\n{datos.indicaciones}" if datos.indicaciones else ""))
    conv_id = _guardar_redaccion(u, pedido_usuario, texto, fuentes, r)
    return {"conv_id": conv_id}


@app.post("/api/redactar")
def redactar_escrito(datos: PedidoRedactar, u=Depends(usuario_actual)):
    """Por partes (una línea JSON por evento): los avances y al final {"conv_id": …} o {"error": …}."""
    if datos.tipo not in redactar.TIPOS:
        raise HTTPException(400, "Elija qué quiere redactar.")
    if datos.modo == "propio":
        faltan = redactar.faltan(datos.tipo, datos.respuestas)
        if faltan:
            raise HTTPException(400, "Falta responder: " + "; ".join(faltan) + ".")
    elif len(datos.texto.strip()) < 200:
        raise HTTPException(400, "El documento casi no tiene texto.")
    datos.texto = datos.texto[:redactar.MAX_CARACTERES]
    datos.indicaciones = datos.indicaciones.strip()[:1500]

    def linea(evento: dict) -> str:
        return json.dumps(evento, ensure_ascii=False, default=str) + "\n"

    def eventos():
        aviso = _sin_escritos(u)
        if aviso:
            yield linea({"error": aviso})
            return
        if not juris_ia.disponible():
            yield linea({"error": "Papiniano no puede redactar en este momento. Intente más tarde."})
            return
        yield linea({"avance": "Pensando…"})
        cola = queue.Queue()

        def trabajo():
            try:
                hacer = _redactar_propio if datos.modo == "propio" else _redactar
                cola.put(("fin", hacer(datos, u, lambda t: cola.put(("avance", t)))))
            except juris_ia.LimiteAlcanzado:
                cola.put(("error", "Se alcanzó el límite gratis de la IA por ahora; intente en un minuto."))
            except Exception as ex:
                print(f"La redacción falló: {ex}", flush=True)
                cola.put(("error", "No pude redactar el escrito. Intente de nuevo en un momento."))

        threading.Thread(target=trabajo, daemon=True).start()
        while True:
            tipo, valor = cola.get()
            if tipo == "avance":
                yield linea({"avance": valor})
            elif tipo == "error":
                yield linea({"error": valor})
                return
            else:
                yield linea(valor)
                return

    return StreamingResponse(eventos(), media_type="application/x-ndjson")


class TextoEscrito(BaseModel):
    texto: str


def con_propios(u=Depends(usuario_actual)) -> dict:
    """Sus propios modelos y documentos: todos los planes menos el Aspirante."""
    if not cuentas.con_propios(u["plan"]):
        raise HTTPException(403, SIN_PROPIOS)
    return u


MAX_ESCRITO = 60_000   # caracteres: una demanda larga cabe de sobra


def _texto_escrito(e: TextoEscrito) -> str:
    texto = e.texto.replace("\r\n", "\n").strip()
    if not texto:
        raise HTTPException(400, "El escrito está vacío.")
    if len(texto) > MAX_ESCRITO:
        raise HTTPException(413, "El escrito es demasiado largo.")
    return texto


@app.put("/api/conversaciones/{conv_id}/escrito")
def escrito_guardar(conv_id: int, e: TextoEscrito, u=Depends(usuario_actual)):
    """Lo que el abogado corrigió a mano en el escrito."""
    if not cuentas.abrir_conversacion(u["id"], conv_id):
        raise HTTPException(404, "Esa conversación ya no existe.")
    return cuentas.guardar_escrito(u["id"], conv_id, _texto_escrito(e))


@app.post("/api/conversaciones/{conv_id}/escrito/deshacer")
def escrito_deshacer(conv_id: int, u=Depends(usuario_actual)):
    escrito = cuentas.deshacer_escrito(u["id"], conv_id)
    if not escrito:
        raise HTTPException(404, "Esa conversación no tiene escrito.")
    return escrito


@app.get("/api/modelos")
def modelos_lista(u=Depends(usuario_actual)):
    """Los modelos de escritos, para elegir uno por grupo y materia, los que subió el abogado y los que
    comparten sus colegas de oficina."""
    try:
        suyos = _modelos_del_abogado(u)
    except Exception:
        suyos = []
    return {"modelos": modelos.lista(), "propios": [m for m in suyos if m["propio"]],
            "oficina": [m for m in suyos if m.get("oficina")], "grupos": modelos.GRUPOS, "materias": modelos.MATERIAS}


@app.get("/api/modelos/{clave}")
def modelo_ver(clave: str, u=Depends(usuario_actual)):
    ficha, texto = _modelo(clave, u)
    if not texto:
        raise HTTPException(404, "Ese modelo no existe.")
    return {**ficha, "texto": texto}


MAX_MB_MODELO = 5


@app.post("/api/modelos/leer")
async def modelo_leer(request: Request, u=Depends(con_propios)):
    """Convierte el Word que sube el abogado en el texto de un modelo, sin guardarlo todavía: primero lo
    revisa y marca los nombres. Los datos que se reconocen (cédulas, montos…) ya salen como datos por llenar.
    El Word no se guarda ni pasa por la IA."""
    nombre = unquote(request.headers.get("X-Nombre", "")).strip() or "modelo"
    if pathlib.Path(nombre).suffix.lower() != ".docx":
        raise HTTPException(400, f"«{nombre}»: suba el modelo en Word (.docx). Si es un .doc, ábralo en Word y "
                                 "guárdelo como .docx.")
    contenido = await request.body()
    if len(contenido) > MAX_MB_MODELO * 1024 * 1024:
        raise HTTPException(413, f"«{nombre}» pesa más de {MAX_MB_MODELO} MB.")
    try:
        texto = modelos.de_word(contenido)
    except Exception:
        raise HTTPException(422, f"«{nombre}» no se pudo leer. Verifique que sea un Word válido.")
    if not texto:
        raise HTTPException(422, f"«{nombre}» no tiene texto.")
    texto, cambios = modelos.quitar_datos(texto[:MAX_ESCRITO])
    return {"nombre": pathlib.Path(nombre).stem, "texto": texto, "cambios": cambios}


class ModeloPropio(BaseModel):
    nombre: str
    grupo: str = ""
    materia: str = ""
    texto: str
    # que lo vean y lo usen también los abogados de su oficina
    compartido: bool = False


def _modelo_propio(m: ModeloPropio, u: dict) -> tuple:
    nombre = m.nombre.strip()[:120]
    if not nombre:
        raise HTTPException(400, "Póngale un nombre al modelo.")
    grupo = m.grupo if m.grupo in modelos.GRUPOS else ""
    materia = m.materia if m.materia in modelos.MATERIAS else ""
    return nombre, grupo, materia, _texto_escrito(TextoEscrito(texto=m.texto)), m.compartido and bool(u["oficina"])


@app.post("/api/modelos/propios")
def modelo_propio_crear(m: ModeloPropio, u=Depends(con_propios)):
    try:
        modelo_id = cuentas.guardar_modelo_propio(u["id"], None, *_modelo_propio(m, u))
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return modelos.propio(cuentas.leer_modelo_propio(u["id"], modelo_id))


@app.put("/api/modelos/propios/{modelo_id}")
def modelo_propio_cambiar(modelo_id: int, m: ModeloPropio, u=Depends(con_propios)):
    try:
        cuentas.guardar_modelo_propio(u["id"], modelo_id, *_modelo_propio(m, u))
    except ValueError as ex:
        raise HTTPException(404, str(ex))
    return modelos.propio(cuentas.leer_modelo_propio(u["id"], modelo_id))


@app.delete("/api/modelos/propios/{modelo_id}")
def modelo_propio_borrar(modelo_id: int, u=Depends(usuario_actual)):
    cuentas.borrar_modelo_propio(u["id"], modelo_id)
    return {"ok": True}


@app.post("/api/escrito/{formato}")
def escrito_descargar(formato: str, e: TextoEscrito, u=Depends(usuario_actual)):
    """El escrito en Word o PDF, ya con los datos que llenó el abogado (esos datos no pasan por la IA)."""
    if formato not in ("docx", "pdf"):
        raise HTTPException(404, "Ese formato no existe.")
    texto = _texto_escrito(e)
    try:
        contenido = pdf_escrito(texto) if formato == "pdf" else generar_escrito(texto)
    except Exception as ex:
        raise HTTPException(500, f"No se pudo armar el documento: {ex}")
    return _archivo(contenido, nombre_escrito(texto, formato))


@app.get("/api/escritos")
def escritos(u=Depends(usuario_actual)):
    """El historial de escritos del abogado (sala Redacción): cada escrito que Papiniano le redactó, con su texto.
    Los datos por llenar no están aquí: quedan en el navegador del abogado y solo se ponen al descargar."""
    return cuentas.escritos_guardados(u["id"])


@app.post("/api/escritos/{conv_id}/copiar")
def escrito_copiar(conv_id: int, u=Depends(usuario_actual)):
    """«Hacer otra como esta»: una conversación nueva con el mismo escrito, lista para pedirle cambios a Papiniano."""
    nuevo = cuentas.copiar_con_escrito(u["id"], conv_id)
    if not nuevo:
        raise HTTPException(404, "Ese escrito ya no está (la conversación se borró).")
    return {"id": nuevo}


@app.get("/api/pagina")
def pagina(url: str, n: int, u=Depends(usuario_actual)):
    """La página citada del PDF oficial, como imagen (ver jurisprudencia/visor.py)."""
    if not url.startswith(FUENTES_PERMITIDAS):
        raise HTTPException(400, "Esa fuente no se puede abrir aquí.")
    try:
        png, total = juris_visor.pagina_png(url, n)
    except Exception:
        raise HTTPException(502, "No se pudo abrir la página. Use «Abrir el PDF oficial».")
    return Response(png, media_type="image/png",
                    headers={"X-Total-Paginas": str(total), "Cache-Control": "private, max-age=86400"})


# ── BIBLIOTECA ───────────────────────────────────
@app.get("/api/documentos")
def documentos(u=Depends(usuario_actual)):
    if not juris_db.configurada():
        return {"configurada": False, "documentos": []}
    try:
        return {"configurada": True, "documentos": juris_proc.mis_documentos(u["id"])}
    except Exception:
        raise HTTPException(503, "No se pudieron leer sus documentos. Intente de nuevo en un momento.")


@app.post("/api/documentos")
async def subir_documento(request: Request, u=Depends(con_propios)):
    """El archivo llega tal cual en el cuerpo; el nombre, en el encabezado X-Nombre (codificado)."""
    if not juris_db.configurada():
        raise HTTPException(503, "Falta configurar el buscador.")
    nombre = unquote(request.headers.get("X-Nombre", "")).strip() or "documento"
    ext = pathlib.Path(nombre).suffix.lower()
    if ext not in (".pdf", ".docx"):
        raise HTTPException(400, f"«{nombre}»: solo se aceptan PDF o Word (.docx).")
    if int(request.headers.get("content-length") or 0) > MAX_MB_SUBIDA * 1024 * 1024:
        raise HTTPException(413, f"«{nombre}» pesa más de {MAX_MB_SUBIDA} MB.")
    contenido = await request.body()
    if len(contenido) > MAX_MB_SUBIDA * 1024 * 1024:
        raise HTTPException(413, f"«{nombre}» pesa más de {MAX_MB_SUBIDA} MB.")
    DIR_SUBIDAS.mkdir(exist_ok=True)
    ruta = DIR_SUBIDAS / f"u{u['id']}_{uuid.uuid4().hex[:10]}{ext}"
    ruta.write_bytes(contenido)

    def procesar():
        try:
            return juris_proc.subir_documento(str(ruta), u["id"], nombre)
        finally:
            ruta.unlink(missing_ok=True)

    from starlette.concurrency import run_in_threadpool
    try:
        r = await run_in_threadpool(procesar)
    except juris_proc.DocumentoSinTexto as ex:
        raise HTTPException(422, f"«{nombre}»: {ex} Por ahora solo se leen PDF digitales y Word.")
    except Exception:
        raise HTTPException(422, f"«{nombre}» no se pudo leer. Verifique que sea un PDF o Word válido.")
    return {"titulo": nombre, "numero": r.get("numero") or "", "paginas": r["paginas"]}


@app.delete("/api/documentos/{doc_id}")
def borrar_documento(doc_id: int, u=Depends(usuario_actual)):
    juris_proc.borrar_documento(doc_id, u["id"])
    return {"ok": True}


# ── REDACCIÓN (solo cuentas con plantillas) ──────
def con_plantillas(u=Depends(usuario_actual)) -> dict:
    if not u["plantillas"]:
        raise HTTPException(403, "Su cuenta no tiene las plantillas de solicitudes.")
    return u


def _archivo(contenido: bytes, nombre: str, **cabeceras) -> Response:
    tipo = ("application/pdf" if nombre.endswith(".pdf")
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return Response(contenido, media_type=tipo, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(nombre)}", "X-Nombre": quote(nombre),
        **cabeceras})


@app.get("/api/redaccion")
def redaccion_datos(u=Depends(con_plantillas)):
    """Las plantillas con sus valores iniciales (fechas de hoy) y las listas de tribunales y salas."""
    return {"plantillas": [{"clave": k, "nombre": p["nombre"], "sub": p["sub"], "valores": p["valores"](),
                            "requeridos": p["requeridos"]}
                           for k, p in redaccion.PLANTILLAS.items()],
            "listas": redaccion.LISTAS}


class Documento(BaseModel):
    datos: dict
    editando_id: int | None = None   # Reporte de Audiencia abierto desde el historial con «Editar»


@app.post("/api/redaccion/{clave}/{formato}")
def redaccion_generar(clave: str, formato: str, doc: Documento, u=Depends(con_plantillas)):
    if clave not in redaccion.PLANTILLAS or formato not in ("docx", "pdf"):
        raise HTTPException(404, "Esa plantilla no existe.")
    try:
        contenido, nombre = redaccion.generar(clave, doc.datos, formato)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    except Exception as ex:
        raise HTTPException(500, f"No se pudo armar el documento: {ex}")
    guardado = ""
    if redaccion.PLANTILLAS[clave].get("historial"):
        try:
            historial.guardar(historial.desde_reporte(doc.datos), datos=doc.datos, id_=doc.editando_id)
            guardado = "si"
        except Exception:
            guardado = "no"   # el documento sale igual; la pantalla avisa que no quedó en el historial
    return _archivo(contenido, nombre, **({"X-Historial": guardado} if guardado else {}))


@app.get("/api/historial")
def historial_lista(u=Depends(con_plantillas)):
    """Los reportes generados, en orden de creación (numero 1 es el primero)."""
    try:
        return [{**e, "numero": n} for n, e in enumerate(historial.listar(), start=1)]
    except Exception as ex:
        raise HTTPException(503, f"No se pudo leer el historial: {ex}")


@app.delete("/api/historial/{id_}")
def historial_borrar(id_: int, u=Depends(con_plantillas)):
    historial.borrar(id_)
    return {"ok": True}


@app.get("/api/historial/word")
def historial_word(u=Depends(con_plantillas)):
    """Todo el historial en Word, con el formato de EXPEDIENTES."""
    return _archivo(generar_expedientes(historial.listar()), f"EXPEDIENTES {datetime.now(ZONA_RD).year}.docx")


# ── USUARIOS (solo administradores) ──────────────
def solo_admin(u=Depends(usuario_actual)) -> dict:
    if not u["es_admin"]:
        raise HTTPException(403, "Solo los administradores pueden ver esto.")
    return u


@app.get("/api/errores")
def errores(u=Depends(solo_admin)):
    return cuentas.listar_errores()


@app.delete("/api/errores")
def borrar_errores(u=Depends(solo_admin)):
    cuentas.borrar_errores()
    _abiertos().clear()
    return {"ok": True}


class AvisoCliente(BaseModel):
    ruta: str
    metodo: str = "GET"
    estado: int = 0


@app.post("/api/errores/cliente")
def aviso_cliente(datos: AvisoCliente, u=Depends(usuario_actual)):
    """El navegador avisa que uno de sus pedidos no recibió respuesta válida (el servidor estaba despertando,
    el proxy de Render lo cortó, se cayó el internet del abogado): queda en el mismo panel de errores, marcado
    como aviso del navegador. Si el servidor está caído del todo este aviso también se pierde; de eso ve Render."""
    ruta = datos.ruta.strip().split("?")[0]
    if not ruta.startswith("/api/") or len(ruta) > 200:
        raise HTTPException(400, "Aviso inválido.")
    metodo = datos.metodo.strip().upper()[:10] or "GET"
    cuentas.registrar_error(
        metodo, ruta, "Sin respuesta" if datos.estado == 0 else f"HTTP {datos.estado}",
        "Aviso del navegador: el pedido no recibió una respuesta válida.",
        f"El navegador de {u['nombre'] or u['usuario']} no recibió respuesta válida de {metodo} {ruta} "
        f"(estado {datos.estado or 'sin conexión'}). Suele pasar mientras el servidor de Render despierta o "
        "su proxy corta el pedido; si se repite seguido, revisar Render.", u["id"])
    _abiertos().add((u["id"], ruta))
    return {"ok": True}


@app.get("/api/usuarios")
def usuarios(u=Depends(solo_admin)):
    return [{**x, "es_admin": bool(x["es_admin"]), "activo": bool(x["activo"]), "plantillas": bool(x["plantillas"]),
             "email": x["email"] or "", "plan": x["plan"] or "activo", "oficina": x["oficina"] or ""}
            for x in cuentas.listar_usuarios()]


class NuevoUsuario(BaseModel):
    usuario: str
    nombre: str = ""
    clave: str
    email: str = ""
    es_admin: bool = False
    plantillas: bool = False


@app.post("/api/usuarios")
def crear_usuario(datos: NuevoUsuario, u=Depends(solo_admin)):
    try:
        cuentas.crear_usuario(datos.usuario, datos.clave, datos.nombre, datos.es_admin, email=datos.email,
                              plantillas=datos.plantillas)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return {"ok": True}


class CambioUsuario(BaseModel):
    plan: str | None = None
    email: str | None = None
    activo: bool | None = None
    plantillas: bool | None = None
    # la oficina en la que queda (null: sin oficina); solo cuenta si viene en el pedido
    oficina_id: int | None = None


@app.patch("/api/usuarios/{uid}")
def cambiar_usuario(uid: int, c: CambioUsuario, u=Depends(solo_admin)):
    # su propia cuenta no se puede vencer ni desactivar (se quedaría afuera)
    if uid == u["id"] and (c.plan is not None or c.activo is not None):
        raise HTTPException(400, "No puede cambiar el plan ni desactivar su propia cuenta.")
    try:
        if c.plan is not None:
            cuentas.cambiar_plan(uid, c.plan)
        if c.email is not None:
            cuentas.asignar_email(uid, c.email.strip().lower())
        if c.activo is not None:
            cuentas.cambiar_activo(uid, c.activo)
        if c.plantillas is not None:
            cuentas.cambiar_plantillas(uid, c.plantillas)
        if "oficina_id" in c.model_fields_set:
            cuentas.poner_en_oficina(uid, c.oficina_id)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return {"ok": True}


@app.get("/api/oficinas")
def oficinas(u=Depends(solo_admin)):
    return cuentas.listar_oficinas()


class NuevaOficina(BaseModel):
    nombre: str
    dueno_id: int
    # los que paga: uno por abogado, el dueño incluido
    asientos: int = cuentas.ASIENTOS_MINIMOS


@app.post("/api/oficinas")
def oficina_crear(datos: NuevaOficina, u=Depends(solo_admin)):
    try:
        return {"id": cuentas.crear_oficina(datos.nombre, datos.dueno_id, datos.asientos)}
    except ValueError as ex:
        raise HTTPException(400, str(ex))


class CambioOficina(BaseModel):
    nombre: str | None = None
    plan: str | None = None
    asientos: int | None = None


@app.patch("/api/oficinas/{oid}")
def oficina_cambiar(oid: int, c: CambioOficina, u=Depends(solo_admin)):
    try:
        cuentas.cambiar_oficina(oid, c.nombre, c.plan, c.asientos)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return {"ok": True}


@app.delete("/api/oficinas/{oid}")
def oficina_borrar(oid: int, u=Depends(solo_admin)):
    cuentas.borrar_oficina(oid)
    return {"ok": True}


# ── MI OFICINA (plan Buffet) ───────────────────
def _mi_oficina(u: dict) -> dict:
    """Su oficina (None si no tiene) y las oficinas que lo agregaron y esperan que acepte."""
    return {"oficina": cuentas.mi_oficina(u["id"]), "invitaciones": cuentas.invitaciones_de(u)}


def _en_oficina(accion):
    """Hace el cambio; si no se puede, el motivo le llega al abogado como mensaje."""
    try:
        accion()
    except PermissionError as ex:
        raise HTTPException(403, str(ex))
    except ValueError as ex:
        raise HTTPException(400, str(ex))


@app.get("/api/oficina")
def oficina(u=Depends(usuario_actual)):
    return _mi_oficina(u)


class Correo(BaseModel):
    email: str


@app.post("/api/oficina/invitaciones")
def oficina_invitar(datos: Correo, u=Depends(usuario_actual)):
    _en_oficina(lambda: cuentas.invitar(u["id"], datos.email))
    return _mi_oficina(u)


@app.post("/api/oficina/invitaciones/cancelar")
def oficina_cancelar(datos: Correo, u=Depends(usuario_actual)):
    _en_oficina(lambda: cuentas.cancelar_invitacion(u["id"], datos.email))
    return _mi_oficina(u)


@app.delete("/api/oficina/abogados/{uid}")
def oficina_quitar(uid: int, u=Depends(usuario_actual)):
    _en_oficina(lambda: cuentas.quitar_abogado(u["id"], uid))
    return _mi_oficina(u)


@app.post("/api/oficina/unirme/{oid}")
def oficina_unirme(oid: int, u=Depends(usuario_actual)):
    _en_oficina(lambda: cuentas.aceptar_invitacion(u, oid))
    return {"ok": True}


@app.post("/api/oficina/rechazar/{oid}")
def oficina_rechazar(oid: int, u=Depends(usuario_actual)):
    cuentas.rechazar_invitacion(u, oid)
    return {"ok": True}


@app.post("/api/oficina/salir")
def oficina_salir(u=Depends(usuario_actual)):
    _en_oficina(lambda: cuentas.salir_de_oficina(u))
    return {"ok": True}


# ── EXPEDIENTES Y AGENDA ─────────────────────────
# Del plan Abogado y del Buffet (en una oficina, compartidos por todos sus abogados): el Aspirante no los trae.
SIN_EXPEDIENTES = "Expedientes y Agenda vienen con el plan Abogado. Para pasar al plan Abogado, escríbanos."


def con_expedientes(u=Depends(usuario_actual)) -> dict:
    if not cuentas.con_propios(u["plan"]):
        raise HTTPException(403, SIN_EXPEDIENTES)
    return u


class DatosExpediente(BaseModel):
    cliente: str
    asunto: str = ""
    numero: str = ""
    tribunal: str = ""
    contraparte: str = ""
    notas: str = ""
    estado: str = "activo"
    responsable_id: int | None = None


class DatosFecha(BaseModel):
    titulo: str
    tipo: str = "audiencia"
    fecha: str
    hora: str = ""
    lugar: str = ""
    notas: str = ""
    expediente_id: int | None = None
    responsable_id: int | None = None


class EnExpediente(BaseModel):
    expediente_id: int | None = None


class DocumentoDeBiblioteca(BaseModel):
    doc_id: int


def _caso(accion):
    """Hace el cambio; si no se puede, el motivo le llega al abogado como mensaje."""
    try:
        return accion()
    except LookupError as ex:
        raise HTTPException(404, str(ex))
    except ValueError as ex:
        raise HTTPException(400, str(ex))


def _expediente_completo(u: dict, exp_id: int) -> dict:
    """El expediente con sus documentos de la Biblioteca que todavía existen (se pudieron borrar allá)."""
    x = _caso(lambda: expedientes.leer(u, exp_id))
    if x["documentos"] and juris_db.configurada():
        try:
            existen = {d["id"] for d in juris_proc.mis_documentos(u["id"])}
            x["documentos"] = [d for d in x["documentos"] if d["id"] in existen]
        except Exception:
            pass   # si la otra base no responde, se muestran como estaban
    return x


@app.get("/api/expedientes")
def expedientes_lista(u=Depends(con_expedientes)):
    return expedientes.listar(u)


@app.post("/api/expedientes")
def expediente_crear(datos: DatosExpediente, u=Depends(con_expedientes)):
    exp_id = _caso(lambda: expedientes.guardar(u, None, datos.model_dump()))
    return _expediente_completo(u, exp_id)


@app.get("/api/expedientes/{exp_id}")
def expediente_ver(exp_id: int, u=Depends(con_expedientes)):
    return _expediente_completo(u, exp_id)


@app.put("/api/expedientes/{exp_id}")
def expediente_cambiar(exp_id: int, datos: DatosExpediente, u=Depends(con_expedientes)):
    _caso(lambda: expedientes.guardar(u, exp_id, datos.model_dump()))
    return _expediente_completo(u, exp_id)


@app.delete("/api/expedientes/{exp_id}")
def expediente_borrar(exp_id: int, u=Depends(con_expedientes)):
    _caso(lambda: expedientes.borrar(u, exp_id))
    return {"ok": True}


@app.post("/api/expedientes/{exp_id}/documentos")
def expediente_poner_documento(exp_id: int, datos: DocumentoDeBiblioteca, u=Depends(con_expedientes)):
    """Guarda en el expediente uno de sus documentos de la Biblioteca (solo los suyos)."""
    try:
        doc = next((d for d in juris_proc.mis_documentos(u["id"]) if d["id"] == datos.doc_id), None)
    except Exception:
        raise HTTPException(503, "No se pudieron leer sus documentos. Intente de nuevo en un momento.")
    if not doc:
        raise HTTPException(404, "Ese documento ya no está en su Biblioteca.")
    _caso(lambda: expedientes.poner_documento(u, exp_id, doc["id"], doc["titulo"] or "Documento"))
    return _expediente_completo(u, exp_id)


@app.delete("/api/expedientes/{exp_id}/documentos/{doc_id}")
def expediente_quitar_documento(exp_id: int, doc_id: int, u=Depends(con_expedientes)):
    _caso(lambda: expedientes.quitar_documento(u, exp_id, doc_id))
    return _expediente_completo(u, exp_id)


@app.put("/api/conversaciones/{conv_id}/expediente")
def conversacion_en_expediente(conv_id: int, datos: EnExpediente, u=Depends(con_expedientes)):
    """Guarda la conversación (con su escrito) en un expediente, o la saca (expediente_id null)."""
    _caso(lambda: expedientes.poner_conversacion(u, conv_id, datos.expediente_id))
    return {"expediente": expedientes.de_conversacion(u, conv_id)}


@app.get("/api/agenda")
def agenda(desde: str = "", hasta: str = "", u=Depends(con_expedientes)):
    """Las fechas entre dos días (AAAA-MM-DD, los dos incluidos); sin días, las de los próximos 7."""
    hoy = expedientes.hoy()
    return _caso(lambda: expedientes.agenda(u, desde or hoy.isoformat(), hasta or (hoy + timedelta(days=7)).isoformat()))


@app.post("/api/agenda")
def fecha_crear(datos: DatosFecha, u=Depends(con_expedientes)):
    return {"id": _caso(lambda: expedientes.guardar_fecha(u, None, datos.model_dump()))}


@app.put("/api/agenda/{fecha_id}")
def fecha_cambiar(fecha_id: int, datos: DatosFecha, u=Depends(con_expedientes)):
    return {"id": _caso(lambda: expedientes.guardar_fecha(u, fecha_id, datos.model_dump()))}


@app.delete("/api/agenda/{fecha_id}")
def fecha_borrar(fecha_id: int, u=Depends(con_expedientes)):
    _caso(lambda: expedientes.borrar_fecha(u, fecha_id))
    return {"ok": True}


# ── PANTALLAS ────────────────────────────────────
# Lo que Google y los asistentes de IA leen de cada página pública antes de que corra el JavaScript: el título, la
# descripción y, en la calculadora, un resumen propio (el de index.html habla de la portada). Las pantallas ponen el
# mismo título al abrirse (useTitulo).
PAGINAS_PUBLICAS = {
    "": ("Papiniano · Asistente jurídico con IA para abogados dominicanos",
         "Sentencias de la Suprema Corte y leyes dominicanas con la página exacta de cada cita, y sus escritos en Word. "
         "Pruébelo 5 días gratis.", None),
    "calculadora-prestaciones-laborales": (
        "Calculadora de prestaciones laborales RD · Papiniano",
        "Calcule gratis el preaviso, la cesantía, las vacaciones y la regalía pascual con las fórmulas del Código de "
        "Trabajo dominicano. Sin registrarse.",
        "<h1>Calculadora de prestaciones laborales de República Dominicana</h1>"
        "<p>Calcula gratis, sin registrarse, el preaviso (art. 76), el auxilio de cesantía (art. 80), las vacaciones no "
        "disfrutadas (arts. 177, 180 y 182) y la regalía pascual o salario de Navidad (arts. 219 y 220) de un trabajador al "
        "que le hicieron desahucio o lo despidieron sin causa justificada, con las fórmulas del Código de Trabajo. "
        "El salario diario es el salario mensual dividido entre 23.83.</p>"
        "<p>Preaviso: 7 días de 3 a 6 meses; 14 días de más de 6 meses a un año; 28 días con más de un año. Cesantía: "
        "6 días de 3 a 6 meses; 13 días de 6 meses a un año; 21 días por año de uno a cinco años; 23 días por año con "
        "cinco años o más.</p>"
        '<p>Hecha por <a href="https://papinianord.com/">Papiniano</a>, el asistente jurídico con IA para abogados '
        "dominicanos.</p>"),
    "terminos": ("Términos de servicio · Papiniano", "Las condiciones de uso de Papiniano.", None),
    "privacidad": ("Política de privacidad · Papiniano",
                   "Qué datos guarda Papiniano, para qué, y cómo pedir verlos o borrarlos (Ley 172-13).", None),
    "reembolso": ("Política de reembolso · Papiniano", "Cuándo y cómo se devuelve un pago de Papiniano.", None),
    "contacto": ("Contacto · Papiniano", "Escríbale a Papiniano: preguntas, el plan Buffet o algo que no funciona.", None),
    "entrar": ("Entrar · Papiniano", "Entre a Papiniano con su cuenta de Gmail o con su usuario y contraseña.", None),
}
# páginas públicas que Google no debe mostrar: la entrada no le sirve a quien busca
NO_INDEXAR = {"entrar"}
# las pantallas de la app (sin sesión piden entrar): existen, pero no son para Google. Son las mismas de RUTAS_APP en
# web/src/App.tsx; cualquier otra dirección responde 404. Si se agrega una pantalla, agregarla en los dos lados.
RUTAS_APP = re.compile(r"(papiniano|expedientes|redaccion)(/[^/]+)?|plan|modelos|redactar|biblioteca|usuarios|errores|oficina|agenda")
PAGINA_404 = ("Página no encontrada · Papiniano", "Esta dirección no existe en Papiniano.",
              '<h1>Página no encontrada</h1><p>Esta dirección no existe en Papiniano. '
              '<a href="https://papinianord.com/">Ir al inicio</a> · '
              '<a href="https://papinianord.com/calculadora-prestaciones-laborales">Calculadora de prestaciones</a> · '
              '<a href="https://papinianord.com/contacto">Contacto</a></p>')
NO_404 = object()   # la clave de la 404 en _INDICE
_INDICE = {}


def _origen() -> str:
    """La dirección pública del sitio, para las direcciones canónicas (la misma que usa la redirección desde Render)."""
    return (os.environ.get("APP_URL") or "https://papinianord.com").rstrip("/")


def _indice(ruta) -> str:
    """index.html con el título, la descripción y la dirección de esa página (se arma una vez por página).
    Con NO_404, la página 404: sin dirección canónica y con «noindex»."""
    if ruta not in _INDICE:
        html = (PANTALLAS / "index.html").read_text(encoding="utf-8")
        es_404 = ruta is NO_404
        titulo, descripcion, resumen = PAGINA_404 if es_404 else PAGINAS_PUBLICAS[ruta]
        t, d = escape(titulo, quote=True), escape(descripcion, quote=True)
        html = re.sub(r"<title>.*?</title>", f"<title>{t}</title>", html, count=1)
        html = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + d, html, count=1)
        html = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + t, html, count=1)
        html = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + d, html, count=1)
        extra = ""
        if not es_404:
            direccion = f"{_origen()}/{ruta}"
            html = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + direccion, html, count=1)
            extra += f'    <link rel="canonical" href="{direccion}" />\n'
        if es_404 or ruta in NO_INDEXAR:
            extra += '    <meta name="robots" content="noindex" />\n'
        html = html.replace("</head>", extra + "  </head>", 1)
        if resumen:
            html = re.sub(r"<noscript>.*?</noscript>", lambda m: f"<noscript>{resumen}</noscript>", html, count=1, flags=re.S)
        _INDICE[ruta] = html
    return _INDICE[ruta]


@app.get("/{ruta:path}")
def pantallas(ruta: str, request: Request):
    """Las pantallas ya armadas (npm run build). Cualquier dirección que no sea un archivo abre la app."""
    if ruta.startswith("api/"):
        return JSONResponse({"detail": "No existe."}, 404)
    # la dirección vieja de Render (…onrender.com) lleva al dominio propio, para que Google y los enlaces viejos
    # terminen en una sola dirección
    propia = os.environ.get("APP_URL", "").rstrip("/")
    if propia and ".onrender.com" not in propia and (request.url.hostname or "").endswith(".onrender.com"):
        return RedirectResponse(f"{propia}/{ruta}" + (f"?{request.url.query}" if request.url.query else ""), 301)
    archivo = (PANTALLAS / ruta).resolve()
    if ruta and archivo.is_file() and PANTALLAS.resolve() in archivo.parents:
        # los archivos de assets/ llevan su huella en el nombre (index-DwBA2pKM.js): no cambian nunca
        if ruta.startswith("assets/"):
            return FileResponse(archivo, headers={"Cache-Control": "public, max-age=31536000, immutable"})
        return FileResponse(archivo)
    if (PANTALLAS / "index.html").is_file():
        limpia = ruta.strip("/")
        if limpia in PAGINAS_PUBLICAS:
            cabeceras = {"Cache-Control": "no-cache"}
            if limpia in NO_INDEXAR:
                cabeceras["X-Robots-Tag"] = "noindex"
            return HTMLResponse(_indice(limpia), headers=cabeceras)
        if RUTAS_APP.fullmatch(limpia):
            return FileResponse(PANTALLAS / "index.html", headers={"Cache-Control": "no-cache", "X-Robots-Tag": "noindex"})
        # cualquier otra dirección: la página 404 de la app, con el código 404 de verdad para que Google la descarte
        return HTMLResponse(_indice(NO_404), status_code=404, headers={"Cache-Control": "no-cache", "X-Robots-Tag": "noindex"})
    return PlainTextResponse("Faltan las pantallas: en la carpeta web, corra npm install y npm run build.", 503)
