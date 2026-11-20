"""
Cobro con Polar (vende como comerciante de registro: cobra, factura y reembolsa).

Se activa con variables de Render; sin ellas la app funciona igual y la pantalla «Mi plan» dice que el pago llega pronto:
  POLAR_TOKEN           token de acceso de la organización (Settings → Developers → New Token)
  POLAR_WEBHOOK_SECRET  el secreto del aviso (Settings → Webhooks, apuntando a <dirección>/api/pagos/aviso)
  POLAR_SANDBOX         opcional: «1» para usar el sandbox de Polar en vez del real

Los productos NO se configuran aquí: se buscan en Polar por su nombre («Aspirante (mensual)», «Abogado (anual)»…).
El abogado se identifica en Polar con su número de cuenta (external_customer_id), así los avisos dicen de quién son.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time

import httpx

import cuentas

# nombre del producto en Polar → (plan, ciclo). Aspirante y Abogado cambian el plan de la cuenta; el Buffet abre una
# oficina de 10 abogados con quien paga como dueño.
PRODUCTOS = {
    "aspirante (mensual)": ("basico", "mes"),
    "aspirante (anual)": ("basico", "año"),
    "abogado (mensual)": ("activo", "mes"),
    "abogado (anual)": ("activo", "año"),
    "buffet (mensual)": ("buffet", "mes"),
    "buffet (anual)": ("buffet", "año"),
}
PLAN_PUBLICO = {"aspirante": "basico", "abogado": "activo", "buffet": "buffet"}


class ErrorPago(Exception):
    """Un fallo que se le puede decir al abogado."""


def _token() -> str:
    return os.environ.get("POLAR_TOKEN", "").strip()


def configurado() -> bool:
    return bool(_token())


def _base() -> str:
    return "https://sandbox-api.polar.sh/v1" if os.environ.get("POLAR_SANDBOX") == "1" else "https://api.polar.sh/v1"


def _pedir(metodo: str, ruta: str, **datos) -> dict:
    if not configurado():
        raise ErrorPago("El pago con tarjeta todavía no está activo. Escríbanos a soportepapiniano@gmail.com.")
    try:
        r = httpx.request(metodo, _base() + ruta, headers={"Authorization": f"Bearer {_token()}"}, timeout=20, **datos)
    except httpx.HTTPError:
        raise ErrorPago("No se pudo conectar con Polar. Intente en un momento.")
    if r.status_code >= 400:
        # solo el código y lo que Polar contesta (nunca el token): para saber si es el token (401), un permiso (403) o los datos (422)
        logging.getLogger("papiniano").warning("Polar %s %s → %s %s", metodo, ruta, r.status_code, r.text[:300])
        try:
            cuentas.registrar_error(metodo, "polar" + ruta, f"Polar {r.status_code}", r.text[:300], "")
        except Exception:
            pass
        raise ErrorPago(f"Polar no pudo completar la operación (código {r.status_code}). Escríbanos a soportepapiniano@gmail.com si sigue.")
    return r.json()


_cache = {"hasta": 0.0, "datos": {}}


def productos() -> dict:
    """{(plan, ciclo): id del producto en Polar}, de los productos activos; se guarda 10 minutos."""
    if time.time() < _cache["hasta"] and _cache["datos"]:
        return _cache["datos"]
    pagina, datos = 1, {}
    while pagina < 10:
        r = _pedir("GET", "/products/", params={"is_archived": "false", "limit": 100, "page": pagina})
        for p in r.get("items", []):
            clave = PRODUCTOS.get((p.get("name") or "").strip().lower())
            if clave:
                datos[clave] = p["id"]
        if pagina >= (r.get("pagination") or {}).get("max_page", 1):
            break
        pagina += 1
    _cache.update(hasta=time.time() + 600, datos=datos)
    return datos


def _plan_de_producto(producto: dict | None, producto_id: str | None) -> str | None:
    nombre = ((producto or {}).get("name") or "").strip().lower()
    if nombre in PRODUCTOS:
        return PRODUCTOS[nombre][0]
    for (plan, _), pid in productos().items():
        if pid and pid == (producto_id or (producto or {}).get("id")):
            return plan
    return None


def crear_pago(u: dict, plan: str, ciclo: str, volver: str) -> str:
    """La dirección de la pantalla de pago de Polar para este abogado, plan y ciclo."""
    if plan not in PLAN_PUBLICO or ciclo not in ("mes", "año"):
        raise ErrorPago("Ese plan no se paga aquí. Escríbanos a soportepapiniano@gmail.com.")
    oficina = u.get("oficina")
    if oficina and not (plan == "buffet" and oficina["es_dueno"]):
        raise ErrorPago("Su cuenta es de una oficina: el plan lo maneja el dueño de la oficina.")
    pid = productos().get((PLAN_PUBLICO[plan], ciclo))
    if not pid:
        raise ErrorPago("Ese plan todavía no está disponible. Escríbanos a soportepapiniano@gmail.com.")
    cuerpo = {"products": [pid], "success_url": volver, "external_customer_id": str(u["id"])}
    if u.get("email"):
        cuerpo["customer_email"] = u["email"]
    return _pedir("POST", "/checkouts/", json=cuerpo)["url"]


def crear_portal(u: dict) -> str:
    """La página donde el abogado ve sus recibos, cambia su tarjeta o cancela."""
    r = _pedir("POST", "/customer-sessions/", json={"external_customer_id": str(u["id"])})
    return r["customer_portal_url"]


# ── el aviso de Polar (Standard Webhooks) ────────
def firma_valida(cuerpo: bytes, cabeceras) -> bool:
    secreto = os.environ.get("POLAR_WEBHOOK_SECRET", "").strip()
    id_, marca, firmas = (cabeceras.get("webhook-id"), cabeceras.get("webhook-timestamp"), cabeceras.get("webhook-signature"))
    if not (secreto and id_ and marca and firmas):
        return False
    try:
        if abs(time.time() - int(marca)) > 300:
            return False
    except ValueError:
        return False
    claves = [secreto.encode("utf-8")]
    if secreto.startswith("whsec_"):
        try:
            claves.append(base64.b64decode(secreto[6:]))
        except Exception:
            pass
    firmado = f"{id_}.{marca}.".encode() + cuerpo
    for clave in claves:
        esperada = base64.b64encode(hmac.new(clave, firmado, hashlib.sha256).digest()).decode()
        for f in firmas.split():
            if hmac.compare_digest(f.split(",", 1)[-1], esperada):
                return True
    return False


def aplicar_evento(evento: dict) -> str:
    """Pone el plan de la cuenta según lo que Polar avisa de su suscripción. Devuelve qué hizo (para el registro)."""
    tipo = evento.get("type", "")
    if not tipo.startswith("subscription."):
        return "ignorado"
    datos = evento.get("data") or {}
    cliente = datos.get("customer") or {}
    uid = cliente.get("external_id") or (datos.get("metadata") or {}).get("usuario_id")
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return "sin cuenta"
    estado = datos.get("status")
    if estado in ("active", "trialing"):
        plan = _plan_de_producto(datos.get("product"), datos.get("product_id"))
        if not plan:
            return "producto desconocido"
    elif estado in ("canceled", "unpaid", "incomplete_expired"):
        plan = "vencido"   # «canceled» es que ya terminó el período pagado; mientras tanto el estado sigue «active»
    else:
        return f"estado {estado}"
    return cuentas.aplicar_suscripcion(uid, plan)


def procesar(cuerpo: bytes) -> str:
    return aplicar_evento(json.loads(cuerpo))
