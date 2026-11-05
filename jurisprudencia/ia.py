"""
IA para responder con las sentencias encontradas.
Usa cualquier proveedor compatible con la API de OpenAI (por defecto Groq).
Para cambiar de proveedor basta con IA_BASE_URL, IA_MODELO e IA_API_KEY.

En Groq gratis cada modelo tiene su propio límite (8.000 tokens por minuto,
200.000 por día), así que se reparten: el modelo rápido arma las búsquedas y
sirve de reemplazo; el principal solo redacta.
"""

import json, os, re

import httpx

IA_BASE_URL     = os.environ.get("IA_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
IA_MODELO       = os.environ.get("IA_MODELO", "openai/gpt-oss-120b")
IA_MODELO_RAPIDO = os.environ.get("IA_MODELO_RAPIDO", "openai/gpt-oss-20b")
IA_API_KEY      = os.environ.get("IA_API_KEY", "").strip()

MAX_FUENTES = 6           # fragmentos que se le pasan a la IA
CARACTERES_FUENTES = 7000  # texto total de las fuentes (~2.000 tokens)

_SISTEMA = (
    "Eres un asistente de investigación jurídica para abogados de República Dominicana. "
    "Respondes en español, claro y preciso. Usa ÚNICAMENTE las fuentes numeradas que te doy; "
    "no inventes sentencias, números, fechas ni criterios. Cita cada afirmación con el número "
    "de la fuente entre corchetes, por ejemplo [2]. Si las fuentes no alcanzan para responder, "
    "dilo claramente. No des asesoría definitiva: el abogado debe verificar en la fuente."
)


class LimiteAlcanzado(Exception):
    """Se agotó el límite gratis de la IA (por minuto o por día)."""


def disponible() -> bool:
    return bool(IA_API_KEY)


def _chat(mensajes: list, modelo: str, max_tokens: int = 700, json_modo: bool = False) -> str:
    cuerpo = {"model": modelo, "messages": mensajes, "temperature": 0.1, "max_tokens": max_tokens}
    if json_modo:
        cuerpo["response_format"] = {"type": "json_object"}
    if "gpt-oss" in modelo:
        cuerpo["reasoning_effort"] = "low"   # que no gaste los tokens pensando
        cuerpo["include_reasoning"] = False
    r = httpx.post(f"{IA_BASE_URL}/chat/completions", json=cuerpo, timeout=60,
                   headers={"Authorization": f"Bearer {IA_API_KEY}"})
    if r.status_code in (413, 429):
        raise LimiteAlcanzado(r.text[:200])
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _chat_con_reemplazo(mensajes: list, **kw) -> str:
    """Prueba el modelo principal y, si llegó al límite, el rápido."""
    try:
        return _chat(mensajes, IA_MODELO, **kw)
    except LimiteAlcanzado:
        if IA_MODELO_RAPIDO == IA_MODELO:
            raise
        return _chat(mensajes, IA_MODELO_RAPIDO, **kw)


def generar_busquedas(pregunta: str) -> list:
    """Convierte la pregunta en 2–4 búsquedas con palabras clave y sinónimos jurídicos."""
    try:
        salida = _chat([
            {"role": "system", "content":
                "Convierte la pregunta de un abogado dominicano en búsquedas para un buscador de "
                "palabras clave de sentencias. Devuelve JSON: {\"busquedas\": [\"...\", \"...\"]} "
                "con 2 a 4 búsquedas cortas (3 a 8 palabras), con sinónimos y términos jurídicos."},
            {"role": "user", "content": pregunta}], IA_MODELO_RAPIDO, max_tokens=200, json_modo=True)
        busquedas = [b for b in json.loads(salida).get("busquedas", []) if isinstance(b, str)]
        return (busquedas or [])[:4] + [pregunta]
    except Exception:
        return [pregunta]


def responder(pregunta: str, fuentes: list, referencia) -> dict:
    """Redacta la respuesta y quita cualquier cita a una fuente que no exista."""
    fuentes = fuentes[:MAX_FUENTES]
    por_fuente = CARACTERES_FUENTES // max(len(fuentes), 1)
    bloque = "\n\n".join(f"[{n}] {referencia(f)}\n{f['texto'][:por_fuente]}" for n, f in enumerate(fuentes, 1))
    texto = _chat_con_reemplazo([
        {"role": "system", "content": _SISTEMA},
        {"role": "user", "content": f"Fuentes:\n\n{bloque}\n\nPregunta: {pregunta}"}])
    # algunos modelos citan como 【1】 o 【1†fuente】: se pasan a [1]
    texto = re.sub(r"【\s*(\d+)[^】]*】", r"[\1]", texto)
    validas = set(range(1, len(fuentes) + 1))
    citadas = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto)} & validas)
    texto = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in validas else "", texto)
    return {"texto": texto.strip(), "citadas": citadas}
