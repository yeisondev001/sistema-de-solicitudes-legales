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

import json, os, pathlib, queue, secrets, threading, time, uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote, urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

import cuentas
import historial
import modelos
import redaccion
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


# ── SESIÓN ───────────────────────────────────────
def _poner_sesion(respuesta: Response, token: str):
    respuesta.set_cookie(COOKIE, token, max_age=cuentas.DURACION_SESION, httponly=True, samesite="lax",
                         secure=SEGURO, path="/")


def usuario_actual(request: Request) -> dict:
    try:
        u = cuentas.usuario_de_sesion(request.cookies.get(COOKIE, ""))
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
    perfil["escritos"] = cuentas.con_escritos(u["plan"])
    perfil["prueba"] = perfil["basico"] = None
    tope = cuentas.tope_diario(u["plan"])
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


def _entrar(respuesta: Response, usuario: str, clave: str) -> dict:
    try:
        r = cuentas.iniciar_sesion(usuario, clave)
    except Exception as ex:
        raise HTTPException(503, f"No se pudo conectar: {ex}")
    if not r:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    _poner_sesion(respuesta, r[1])
    return _perfil(r[0])


@app.post("/api/entrar")
def entrar(datos: Credenciales, respuesta: Response):
    return _entrar(respuesta, datos.usuario, datos.clave)


@app.post("/api/crear-admin")
def crear_admin(datos: NuevoAdmin, respuesta: Response):
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
    return _entrar(respuesta, datos.usuario, datos.clave)


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
def sesion(u=Depends(usuario_actual)):
    return _perfil(u)


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
# el plan Básico es para consultar: escritos, modelos y documentos propios son del plan Abogado
SIN_ESCRITOS = ("Los escritos, los modelos y sus propios documentos vienen con el plan Abogado. Con el plan "
                "Básico puede consultar sentencias y leyes. Para pasar al plan Abogado, escríbanos.")
SIN_ESCRITOS_CHAT = ("Con el plan Básico no puedo redactar escritos: eso viene con el plan Abogado. Sí le busco "
                     "sentencias y leyes sobre el tema; dígame qué necesita saber.")


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
    return {"id": conv_id, "mensajes": _con_referencia(mensajes), "escrito": cuentas.leer_escrito(u["id"], conv_id)}


@app.delete("/api/conversaciones/{conv_id}")
def borrar_conversacion(conv_id: int, u=Depends(usuario_actual)):
    cuentas.borrar_conversacion(u["id"], conv_id)
    return {"ok": True}


class Pregunta(BaseModel):
    texto: str
    conv_id: int | None = None
    # el modelo que eligió el abogado para el escrito; "ninguno": lo quiere sin modelo
    modelo: str | None = None


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
        r = juris_ia.escribir(q, actual, fuentes, juris_buscar.referencia, historial_chat)
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
        if not cuentas.con_escritos(u["plan"]):
            turno["texto"] = SIN_ESCRITOS_CHAT
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
            turno = (_usar_modelo(datos.modelo, bool(escrito), u) if cuentas.con_escritos(u["plan"])
                     else {"rol": "asistente", "texto": SIN_ESCRITOS_CHAT})
        # un saludo o una prueba ("hola") no se busca: siempre saldría "lo más parecido"
        elif not juris_ia.parece_consulta(q):
            turno = {"rol": "asistente", "texto": juris_ia.no_es_consulta(q)}
        else:
            # la prueba y el plan Básico tienen un máximo de preguntas por día
            try:
                cuentas.registrar_pregunta(u["id"], u["plan"])
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
        escrito_listo = None
        if guardar:
            try:
                conv_id = cuentas.guardar_conversacion(u["id"], conv_id, historial_chat + [pregunta, turno])
                if nuevo_escrito:
                    escrito_listo = cuentas.guardar_escrito(u["id"], conv_id, nuevo_escrito)
            except Exception:
                pass   # si no se puede guardar, la respuesta igual se muestra
        if nuevo_escrito and not escrito_listo:
            escrito_listo = {"texto": nuevo_escrito, "deshacer": False}
        yield linea({"turno": _con_referencia([turno])[0], "conv_id": conv_id,
                     **({"escrito": escrito_listo} if escrito_listo else {})})

    return StreamingResponse(eventos(), media_type="application/x-ndjson")


class TextoEscrito(BaseModel):
    texto: str


def con_escritos(u=Depends(usuario_actual)) -> dict:
    """Escritos, modelos y documentos propios: todos los planes menos el Básico."""
    if not cuentas.con_escritos(u["plan"]):
        raise HTTPException(403, SIN_ESCRITOS)
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
def escrito_guardar(conv_id: int, e: TextoEscrito, u=Depends(con_escritos)):
    """Lo que el abogado corrigió a mano en el escrito."""
    if not cuentas.abrir_conversacion(u["id"], conv_id):
        raise HTTPException(404, "Esa conversación ya no existe.")
    return cuentas.guardar_escrito(u["id"], conv_id, _texto_escrito(e))


@app.post("/api/conversaciones/{conv_id}/escrito/deshacer")
def escrito_deshacer(conv_id: int, u=Depends(con_escritos)):
    escrito = cuentas.deshacer_escrito(u["id"], conv_id)
    if not escrito:
        raise HTTPException(404, "Esa conversación no tiene escrito.")
    return escrito


@app.get("/api/modelos")
def modelos_lista(u=Depends(con_escritos)):
    """Los modelos de escritos, para elegir uno por grupo y materia, los que subió el abogado y los que
    comparten sus colegas de oficina."""
    try:
        suyos = _modelos_del_abogado(u)
    except Exception:
        suyos = []
    return {"modelos": modelos.lista(), "propios": [m for m in suyos if m["propio"]],
            "oficina": [m for m in suyos if m.get("oficina")], "grupos": modelos.GRUPOS, "materias": modelos.MATERIAS}


@app.get("/api/modelos/{clave}")
def modelo_ver(clave: str, u=Depends(con_escritos)):
    ficha, texto = _modelo(clave, u)
    if not texto:
        raise HTTPException(404, "Ese modelo no existe.")
    return {**ficha, "texto": texto}


MAX_MB_MODELO = 5


@app.post("/api/modelos/leer")
async def modelo_leer(request: Request, u=Depends(con_escritos)):
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
def modelo_propio_crear(m: ModeloPropio, u=Depends(con_escritos)):
    try:
        modelo_id = cuentas.guardar_modelo_propio(u["id"], None, *_modelo_propio(m, u))
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return modelos.propio(cuentas.leer_modelo_propio(u["id"], modelo_id))


@app.put("/api/modelos/propios/{modelo_id}")
def modelo_propio_cambiar(modelo_id: int, m: ModeloPropio, u=Depends(con_escritos)):
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
def escrito_descargar(formato: str, e: TextoEscrito, u=Depends(con_escritos)):
    """El escrito en Word o PDF, ya con los datos que llenó el abogado (esos datos no pasan por la IA)."""
    if formato not in ("docx", "pdf"):
        raise HTTPException(404, "Ese formato no existe.")
    texto = _texto_escrito(e)
    try:
        contenido = pdf_escrito(texto) if formato == "pdf" else generar_escrito(texto)
    except Exception as ex:
        raise HTTPException(500, f"No se pudo armar el documento: {ex}")
    return _archivo(contenido, nombre_escrito(texto, formato))


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
async def subir_documento(request: Request, u=Depends(con_escritos)):
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


# ── MI OFICINA (plan Despacho) ───────────────────
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


# ── PANTALLAS ────────────────────────────────────
@app.get("/{ruta:path}")
def pantallas(ruta: str):
    """Las pantallas ya armadas (npm run build). Cualquier dirección que no sea un archivo abre la app."""
    if ruta.startswith("api/"):
        return JSONResponse({"detail": "No existe."}, 404)
    archivo = (PANTALLAS / ruta).resolve()
    if ruta and archivo.is_file() and PANTALLAS.resolve() in archivo.parents:
        return FileResponse(archivo)
    if (PANTALLAS / "index.html").is_file():
        return FileResponse(PANTALLAS / "index.html", headers={"Cache-Control": "no-cache"})
    return PlainTextResponse("Faltan las pantallas: en la carpeta web, corra npm install y npm run build.", 503)
