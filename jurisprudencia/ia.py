"""
IA para responder con las sentencias encontradas.
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

_SISTEMA = (
    "Eres un asistente de investigación jurídica para abogados de República Dominicana. "
    "Respondes en español, claro y preciso. Usa ÚNICAMENTE las fuentes numeradas que te doy; "
    "no inventes sentencias, números, fechas ni criterios. Cita cada afirmación con el número "
    "de la fuente entre corchetes, por ejemplo [2]. Si las fuentes no alcanzan para responder, "
    "dilo claramente. No des asesoría definitiva: el abogado debe verificar en la fuente."
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


_PRESENTACION = ("Busco en las sentencias de la Suprema Corte y en sus documentos. Puede preguntarme, por "
                 "ejemplo, por «deslinde aprobado sin citar a los colindantes» o por un número de sentencia "
                 "como SCJ-TS-25-1451.")


def no_es_consulta(texto: str) -> str:
    """Respuesta a un saludo o a algo que no es una consulta (sin buscar ni gastar IA)."""
    t = texto.lower()
    if "gracias" in t:
        inicio = "¡Con gusto! ¿En qué más le puedo ayudar?"
    elif re.search(r"\b(hola|buen[oa]s?|saludos|hey)\b", t):
        inicio = "¡Hola! ¿En qué le puedo ayudar?"
    else:
        inicio = "¿En qué le puedo ayudar?"
    return f"{inicio} {_PRESENTACION}"
_SALUDOS = {"hola", "buenas", "buenos", "buen", "dia", "dias", "días", "tardes", "noches", "gracias", "ok", "oki",
            "listo", "prueba", "probando", "test", "saludos", "hey", "que", "qué", "tal", "como", "cómo", "estas",
            "estás", "bien", "si", "sí", "no"}


def parece_consulta(texto: str) -> bool:
    """Descarta saludos y pruebas ("hola", "gracias") antes de gastar búsquedas e IA."""
    if re.search(r"\d", texto):
        return True   # puede ser un número de sentencia o expediente
    palabras = [p for p in re.findall(r"[a-záéíóúüñ]+", texto.lower()) if p not in _SALUDOS]
    return any(len(p) > 3 for p in palabras)


def generar_busquedas(pregunta: str) -> list:
    """Convierte la pregunta en 2–4 búsquedas con palabras clave y sinónimos jurídicos.
    Devuelve [] si el texto no es una consulta jurídica (saludo, charla, texto sin sentido)."""
    try:
        salida = _chat_en_cadena([
            {"role": "system", "content":
                "Convierte la pregunta de un abogado dominicano en búsquedas para un buscador de "
                "palabras clave de sentencias. Devuelve JSON: {\"busquedas\": [\"...\", \"...\"]} "
                "con 2 a 4 búsquedas cortas (3 a 8 palabras), con sinónimos y términos jurídicos. "
                "Si el texto no es una consulta jurídica (un saludo, una charla, una prueba o algo sin "
                "sentido), devuelve {\"busquedas\": []}. Un tema jurídico de una o dos palabras sí es consulta."},
            {"role": "user", "content": pregunta}], para_busquedas=True, max_tokens=400, json_modo=True)
        busquedas = [b for b in json.loads(salida).get("busquedas", []) if isinstance(b, str) and b.strip()]
        if not busquedas and not re.search(r"\d", pregunta):
            return []
        return busquedas[:4] + [pregunta]
    except Exception:
        return [pregunta]


def responder(pregunta: str, fuentes: list, referencia) -> dict:
    """Redacta la respuesta y quita cualquier cita a una fuente que no exista."""
    fuentes = fuentes[:MAX_FUENTES]
    por_fuente = CARACTERES_FUENTES // max(len(fuentes), 1)
    bloque = "\n\n".join(f"[{n}] {referencia(f)}\n{f['texto'][:por_fuente]}" for n, f in enumerate(fuentes, 1))
    texto = _chat_en_cadena([
        {"role": "system", "content": _SISTEMA},
        {"role": "user", "content": f"Fuentes:\n\n{bloque}\n\nPregunta: {pregunta}"}])
    # algunos modelos citan como 【1】 o 【1†fuente】: se pasan a [1]
    texto = re.sub(r"【\s*(\d+)[^】]*】", r"[\1]", texto)
    validas = set(range(1, len(fuentes) + 1))
    citadas = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto)} & validas)
    texto = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in validas else "", texto)
    return {"texto": texto.strip(), "citadas": citadas}
