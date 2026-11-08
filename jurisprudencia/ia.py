"""
IA para responder con las sentencias y los artículos de ley encontrados.
Usa proveedores compatibles con la API de OpenAI, en cadena: si uno llega a su
límite gratis (o falla), contesta el siguiente.

  1. Groq, modelo principal (IA_MODELO)        -> redacta
  2. Groq, modelo rápido (IA_MODELO_RAPIDO)    -> arma las búsquedas y reemplaza al 1
  3. Cloudflare Workers AI (CF_MODELO_TEXTO)   -> reemplazo si Groq se llena

En Groq gratis cada modelo tiene su propio límite (8.000 tokens por minuto,
200.000 por día). Cloudflare comparte sus 10.000 neuronas diarias con los vectores.
"""

import json, os, re

import httpx

IA_BASE_URL      = os.environ.get("IA_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
IA_MODELO        = os.environ.get("IA_MODELO", "openai/gpt-oss-120b")
IA_MODELO_RAPIDO = os.environ.get("IA_MODELO_RAPIDO", "openai/gpt-oss-20b")
IA_API_KEY       = os.environ.get("IA_API_KEY", "").strip()
CF_ACCOUNT_ID    = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_API_TOKEN     = os.environ.get("CF_API_TOKEN", "").strip()
CF_MODELO_TEXTO  = os.environ.get("CF_MODELO_TEXTO", "@cf/openai/gpt-oss-120b")

MAX_FUENTES = 6            # fragmentos que se le pasan a la IA
CARACTERES_FUENTES = 7000  # texto total de las fuentes (~2.000 tokens)

MAX_TOKENS_RESPUESTA = 1100   # deja lugar al análisis sin pasar de los 8.000 tokens por minuto de Groq
TURNOS_DE_MEMORIA = 4         # mensajes anteriores de la conversación que se le recuerdan a la IA

_SISTEMA = (
    "Eres un abogado asistente de investigación para colegas de República Dominicana. Conversas en "
    "español, tratando de usted, como un colega con experiencia: claro, práctico y honesto.\n\n"
    "Las fuentes salen de un buscador y no todas tienen que ver con la pregunta: usa solo las que la "
    "responden y las demás ignóralas sin mencionarlas ni resumirlas.\n\n"
    "Cómo responder:\n"
    "1. Empieza respondiendo directamente, en 1 a 3 oraciones, sin ponerle título.\n"
    "2. **Lo que dice la ley:** solo si entre las fuentes que sirven hay artículos de una ley o un "
    "reglamento: di qué dispone cada uno, nombrando el artículo y citándolo con su número entre "
    "corchetes, por ejemplo [1]. Si no hay ninguno, omite esta sección.\n"
    "3. **Lo que dice la jurisprudencia:** explica el criterio de las sentencias que sirven, citando cada "
    "afirmación con su número entre corchetes, por ejemplo [2]. Si hay sentencias que dicen cosas "
    "distintas, señálalo. Si ninguna sentencia sirve, omite esta sección.\n"
    "4. **Análisis:** da tu opinión profesional: cómo se aplica al caso, qué argumentos conviene usar, "
    "qué riesgos o puntos débiles hay y qué conviene revisar o reunir (documentos, plazos, pruebas). "
    "Aquí puedes razonar más allá de las fuentes, pero sin citarlas como si lo dijera una sentencia o una ley.\n"
    "5. Si ninguna fuente sirve, dilo en una o dos oraciones y sugiere cómo seguir (decirlo con otras "
    "palabras o subir sus propios documentos), sin las secciones 2, 3 y 4.\n\n"
    "Reglas: nunca inventes sentencias, números, fechas, artículos ni citas; [n] solo para lo que está en "
    "la fuente n. Si mencionas una ley o un artículo que no está en las fuentes, advierte que hay que "
    "verificarlo. No repitas la pregunta. Usa negritas y listas cortas, sin tablas. Eres una herramienta "
    "de apoyo: la decisión es del abogado."
)


class LimiteAlcanzado(Exception):
    """Todas las IAs llegaron a su límite gratis (por minuto o por día)."""


def _proveedores(para_busquedas: bool = False) -> list:
    """(url, clave, modelo) en el orden en que se prueban."""
    lista = []
    if IA_API_KEY:
        if not para_busquedas:
            lista.append((IA_BASE_URL, IA_API_KEY, IA_MODELO))
        if IA_MODELO_RAPIDO != IA_MODELO or para_busquedas:
            lista.append((IA_BASE_URL, IA_API_KEY, IA_MODELO_RAPIDO))
    if CF_ACCOUNT_ID and CF_API_TOKEN:
        lista.append((f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1",
                      CF_API_TOKEN, CF_MODELO_TEXTO))
    return lista


def disponible() -> bool:
    return bool(_proveedores())


def estado() -> str:
    """Qué claves ve el servidor (sin mostrarlas), para revisar la configuración."""
    return (f"Groq {'sí' if IA_API_KEY else 'no'}, "
            f"Cloudflare {'sí' if CF_ACCOUNT_ID and CF_API_TOKEN else 'no'}")


def _chat(mensajes: list, proveedor: tuple, max_tokens: int = 700, json_modo: bool = False) -> str:
    url, clave, modelo = proveedor
    cuerpo = {"model": modelo, "messages": mensajes, "temperature": 0.1, "max_tokens": max_tokens}
    if json_modo:
        cuerpo["response_format"] = {"type": "json_object"}
    if "gpt-oss" in modelo:
        cuerpo["reasoning_effort"] = "low"   # que no gaste los tokens pensando
        cuerpo["include_reasoning"] = False
    r = httpx.post(f"{url}/chat/completions", json=cuerpo, timeout=60,
                   headers={"Authorization": f"Bearer {clave}"})
    if r.status_code in (413, 429):
        raise LimiteAlcanzado(r.text[:200])
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


def _chat_en_cadena(mensajes: list, para_busquedas: bool = False, **kw) -> str:
    """Prueba cada proveedor en orden hasta que uno conteste."""
    ultimo = LimiteAlcanzado("No hay IA configurada.")
    for proveedor in _proveedores(para_busquedas):
        try:
            texto = _chat(mensajes, proveedor, **kw)
            if texto.strip():
                return texto
        except (LimiteAlcanzado, httpx.HTTPError) as ex:
            ultimo = ex
    raise ultimo if isinstance(ultimo, LimiteAlcanzado) else LimiteAlcanzado(str(ultimo))


_PRESENTACION = ("Busco en las sentencias de la Suprema Corte, en la Ley 108-05 de Registro Inmobiliario y sus "
                 "reglamentos, y en sus documentos. Puede preguntarme, por ejemplo, por «deslinde aprobado sin "
                 "citar a los colindantes», por un número de sentencia como SCJ-TS-25-1451 o por un artículo "
                 "como «art. 81 de la Ley 108-05».")


def no_es_consulta(texto: str) -> str:
    """Respuesta a un saludo o a algo que no es una consulta (sin buscar ni gastar IA)."""
    t = texto.lower()
    if "gracias" in t:
        inicio = "¡Con gusto! ¿En qué más le puedo ayudar?"
    elif re.search(r"\b(hola|buen[oa]s?|saludos|hey)\b", t):
        inicio = "¡Hola! ¿En qué le puedo ayudar?"
    elif re.search(r"\b(pued|podr|funcion|est[aá]s?\b)", t):
        inicio = "¡Claro! ¿Cuál es su consulta?"
    else:
        inicio = "¿En qué le puedo ayudar?"
    return f"{inicio} {_PRESENTACION}"


_SALUDOS = {"hola", "buenas", "buenos", "buen", "dia", "dias", "días", "tardes", "noches", "gracias", "ok", "oki",
            "listo", "prueba", "probando", "test", "saludos", "hey", "que", "qué", "tal", "como", "cómo", "estas",
            "estás", "bien", "si", "sí", "no",
            # preguntas sobre el asistente: «entonces puedes responderme», «ya funciona?»
            "entonces", "ahora", "ya", "puedes", "puede", "podrias", "podrías", "responder", "responderme",
            "contestar", "contestarme", "ayudar", "ayudarme", "ayuda", "funciona", "funcionas", "ahi", "ahí",
            "estas", "esta", "está", "me", "usted", "tu", "tú"}


def parece_consulta(texto: str) -> bool:
    """Descarta saludos y pruebas ("hola", "gracias") antes de gastar búsquedas e IA."""
    if re.search(r"\d", texto):
        return True   # puede ser un número de sentencia o expediente
    palabras = [p for p in re.findall(r"[a-záéíóúüñ]+", texto.lower()) if p not in _SALUDOS]
    return any(len(p) > 3 for p in palabras)


def _memoria(historial: list) -> list:
    """Últimos mensajes de la conversación, sin las citas [n] (cada respuesta numera sus fuentes)."""
    return [{"role": "user" if t["rol"] == "usuario" else "assistant",
             "content": re.sub(r"\s*\[\d+\]", "", t["texto"])[:900]}
            for t in (historial or [])[-TURNOS_DE_MEMORIA:]]


def preparar_busqueda(pregunta: str, historial: list = None) -> dict:
    """Decide qué hacer con el mensaje, teniendo en cuenta la conversación:
      {"tipo": "nueva", "consulta": "...", "busquedas": [...]}   hay que buscar sentencias
      {"tipo": "seguimiento", ...}   pide explicar o resumir lo ya respondido: se usan las mismas fuentes
      {"tipo": "no_juridica", ...}   saludo, agradecimiento o charla: no se busca"""
    plan = {"tipo": "nueva", "consulta": pregunta, "busquedas": [pregunta]}
    try:
        contexto = "\n".join(f"{'Abogado' if m['role'] == 'user' else 'Asistente'}: {m['content'][:300]}"
                             for m in _memoria(historial))
        salida = _chat_en_cadena([
            {"role": "system", "content":
                "Preparas las búsquedas de un asistente jurídico dominicano que busca en sentencias y en leyes. "
                "Recibes la conversación reciente y el último mensaje del abogado. Devuelve JSON: "
                "{\"tipo\": \"...\", \"consulta\": \"...\", \"busquedas\": [\"...\"]}.\n"
                "- tipo \"nueva\": pide información jurídica que hay que buscar (también una pregunta de "
                "seguimiento que cambia o amplía el tema). \"consulta\": el mensaje reescrito para que se "
                "entienda solo, sin pronombres, con el tema de la conversación. \"busquedas\": 2 a 4 búsquedas "
                "cortas (3 a 8 palabras) con sinónimos y términos jurídicos.\n"
                "- tipo \"seguimiento\": solo pide explicar, resumir, simplificar o aclarar lo ya respondido, "
                "sin tema nuevo. \"busquedas\": [].\n"
                "- tipo \"no_juridica\": un saludo, un agradecimiento, una pregunta sobre el asistente o sobre "
                "la conversación (por ejemplo «¿me puede responder?», «¿qué puede hacer?», «¿está ahí?», "
                "«ya funciona?»), una charla o algo sin sentido. \"busquedas\": [].\n"
                "Si el mensaje no nombra ningún tema jurídico y no se refiere a lo ya conversado, es "
                "\"no_juridica\". Un tema jurídico de una o dos palabras sí es una consulta nueva."},
            {"role": "user", "content": (f"Conversación:\n{contexto}\n\n" if contexto else "")
                                        + f"Último mensaje: {pregunta}"}],
            para_busquedas=True, max_tokens=500, json_modo=True)
        datos = json.loads(salida)
        tipo = datos.get("tipo") if datos.get("tipo") in ("nueva", "seguimiento", "no_juridica") else "nueva"
        busquedas = [b for b in datos.get("busquedas", []) if isinstance(b, str) and b.strip()][:4]
        consulta = (datos.get("consulta") or "").strip() or pregunta
        if tipo != "nueva" and re.search(r"\d", pregunta) and not historial:
            tipo = "nueva"   # puede ser un número de sentencia o expediente
        if tipo == "nueva":
            # sin conversación previa, el mensaje mismo también sirve como búsqueda
            busquedas = (busquedas or [consulta]) + ([] if historial else [pregunta])
        plan = {"tipo": tipo, "consulta": consulta, "busquedas": busquedas}
    except Exception:
        pass
    return plan


def generar_busquedas(pregunta: str) -> list:
    """Búsquedas para una pregunta suelta; [] si no es una consulta jurídica."""
    plan = preparar_busqueda(pregunta)
    return plan["busquedas"] if plan["tipo"] == "nueva" else []


def responder(pregunta: str, fuentes: list, referencia, historial: list = None) -> dict:
    """Redacta la respuesta con análisis y quita cualquier cita a una fuente que no exista."""
    fuentes = fuentes[:MAX_FUENTES]
    por_fuente = CARACTERES_FUENTES // max(len(fuentes), 1)
    bloque = "\n\n".join(f"[{n}] {referencia(f)}\n{f['texto'][:por_fuente]}" for n, f in enumerate(fuentes, 1))
    texto = _chat_en_cadena([
        {"role": "system", "content": _SISTEMA},
        *_memoria(historial),
        {"role": "user", "content": f"Fuentes:\n\n{bloque}\n\nPregunta: {pregunta}"}],
        max_tokens=MAX_TOKENS_RESPUESTA)
    # algunos modelos citan como 【1】 o 【1†fuente】: se pasan a [1]
    texto = re.sub(r"【\s*(\d+)[^】]*】", r"[\1]", texto)
    validas = set(range(1, len(fuentes) + 1))
    citadas = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto)} & validas)
    texto = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in validas else "", texto)
    return {"texto": texto.strip(), "citadas": citadas}
