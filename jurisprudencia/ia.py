"""
IA para responder con las sentencias encontradas.
Usa cualquier proveedor compatible con la API de OpenAI (por defecto Groq).
Para cambiar de proveedor basta con IA_BASE_URL, IA_MODELO e IA_API_KEY.
"""

import json, os, re

import httpx

IA_BASE_URL = os.environ.get("IA_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
IA_MODELO   = os.environ.get("IA_MODELO", "llama-3.3-70b-versatile")
IA_API_KEY  = os.environ.get("IA_API_KEY", "").strip()

_SISTEMA = (
    "Eres un asistente de investigación jurídica para abogados de República Dominicana. "
    "Respondes en español, claro y preciso. Usa ÚNICAMENTE las fuentes numeradas que te doy; "
    "no inventes sentencias, números, fechas ni criterios. Cita cada afirmación con el número "
    "de la fuente entre corchetes, por ejemplo [2]. Si las fuentes no alcanzan para responder, "
    "dilo claramente. No des asesoría definitiva: el abogado debe verificar en la fuente."
)


def disponible() -> bool:
    return bool(IA_API_KEY)


def _chat(mensajes: list, max_tokens: int = 900, json_modo: bool = False) -> str:
    cuerpo = {"model": IA_MODELO, "messages": mensajes, "temperature": 0.1, "max_tokens": max_tokens}
    if json_modo:
        cuerpo["response_format"] = {"type": "json_object"}
    r = httpx.post(f"{IA_BASE_URL}/chat/completions", json=cuerpo, timeout=60,
                   headers={"Authorization": f"Bearer {IA_API_KEY}"})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def generar_busquedas(pregunta: str) -> list:
    """Convierte la pregunta en 2–4 búsquedas con palabras clave y sinónimos jurídicos."""
    try:
        salida = _chat([
            {"role": "system", "content":
                "Convierte la pregunta de un abogado dominicano en búsquedas para un buscador de "
                "palabras clave de sentencias. Devuelve JSON: {\"busquedas\": [\"...\", \"...\"]} "
                "con 2 a 4 búsquedas cortas (3 a 8 palabras), con sinónimos y términos jurídicos."},
            {"role": "user", "content": pregunta}], max_tokens=200, json_modo=True)
        busquedas = [b for b in json.loads(salida).get("busquedas", []) if isinstance(b, str)]
        return (busquedas or [])[:4] + [pregunta]
    except Exception:
        return [pregunta]


def responder(pregunta: str, fuentes: list, referencia) -> dict:
    """Redacta la respuesta y quita cualquier cita a una fuente que no exista."""
    bloque = "\n\n".join(f"[{n}] {referencia(f)}\n{f['texto'][:2200]}" for n, f in enumerate(fuentes, 1))
    texto = _chat([
        {"role": "system", "content": _SISTEMA},
        {"role": "user", "content": f"Fuentes:\n\n{bloque}\n\nPregunta: {pregunta}"}])
    validas = set(range(1, len(fuentes) + 1))
    citadas = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto)} & validas)
    texto = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in validas else "", texto)
    return {"texto": texto.strip(), "citadas": citadas}
