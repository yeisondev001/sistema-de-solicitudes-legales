"""
Vectores de significado (embeddings) con Cloudflare Workers AI.
Variables: CF_ACCOUNT_ID y CF_API_TOKEN. Sin ellas la búsqueda es solo por palabras.

Cloudflare no guarda ni entrena con lo que se le envía. El plan gratis da
10.000 "neuronas" por día, compartidas con la IA de respuestas de Cloudflare.
"""

import os

import httpx

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_API_TOKEN  = os.environ.get("CF_API_TOKEN", "").strip()
MODELO        = os.environ.get("EMB_MODELO", "@cf/qwen/qwen3-embedding-0.6b")
DIMENSIONES   = 1024
LOTE          = 32       # máximo de textos por llamada que acepta Cloudflare
MAX_CARACTERES = 6000    # un fragmento de 400 palabras cabe de sobra

_INSTRUCCION = ("Dada la pregunta de un abogado dominicano, encuentra fragmentos de sentencias "
                "que la respondan")


class LimiteAlcanzado(Exception):
    """Se agotaron las neuronas gratis del día."""


class ErrorCloudflare(Exception):
    """Cloudflare rechazó la llamada (texto raro, falla pasajera…)."""


def configurado() -> bool:
    return bool(CF_ACCOUNT_ID and CF_API_TOKEN)


def _llamar(cuerpo: dict) -> tuple:
    """Devuelve (vectores, neuronas gastadas)."""
    r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{MODELO}",
                   json=cuerpo, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, timeout=120)
    if r.status_code == 429 or (r.status_code >= 400 and "neuron" in r.text.lower()):
        raise LimiteAlcanzado(r.text[:200])
    if r.status_code >= 400:
        raise ErrorCloudflare(f"{r.status_code}: {r.text[:300]}")
    res = r.json()["result"]
    vectores = res.get("data") or res.get("response") or []
    return vectores, float((res.get("usage") or {}).get("neurons", 0))


def de_documentos(textos: list) -> tuple:
    """Vectores de varios fragmentos; devuelve (vectores, neuronas gastadas).
    Si un lote falla se reintenta de uno en uno; el que siga fallando queda como None."""
    vectores, neuronas = [], 0.0
    for i in range(0, len(textos), LOTE):
        lote = [(t or " ")[:MAX_CARACTERES] for t in textos[i:i + LOTE]]
        try:
            v, n = _llamar({"documents": lote})
        except ErrorCloudflare:
            v, n = [], 0.0
            for t in lote:
                try:
                    uno, gasto = _llamar({"documents": [t]})
                    v.append(uno[0])
                    n += gasto
                except ErrorCloudflare:
                    v.append(None)
        vectores.extend(v)
        neuronas += n
    return vectores, neuronas


def de_pregunta(pregunta: str) -> list:
    """Vector de una pregunta (lleva la instrucción de búsqueda que pide el modelo)."""
    v, _ = _llamar({"queries": pregunta[:MAX_CARACTERES], "instruction": _INSTRUCCION})
    return v[0]


def como_texto(vector: list) -> str:
    """Formato que entiende pgvector: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
