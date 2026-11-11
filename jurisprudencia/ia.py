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
    "Eres Papiniano, un abogado asistente de investigación para colegas de República Dominicana. Conversas en "
    "español, tratando de usted, como un colega con experiencia: claro, práctico y honesto.\n\n"
    "Las fuentes salen de un buscador y no todas tienen que ver con la pregunta: usa las que sirven y las "
    "demás ignóralas sin mencionarlas ni resumirlas. Una fuente sirve aunque no trate el caso exacto si "
    "fija la regla general o resuelve un caso parecido que se aplica igual (por ejemplo, un vidrio roto es "
    "un daño a la propiedad: sirven las sentencias sobre reparación de daños y perjuicios y responsabilidad "
    "civil, aunque traten de choques); en ese caso explica cómo se traslada al caso del abogado.\n\n"
    "Cómo responder:\n"
    "1. Empieza respondiendo directamente, en 1 a 3 oraciones, sin ponerle título.\n"
    "2. **Lo que dice la ley:** solo si entre las fuentes que sirven hay artículos de una ley o un "
    "reglamento: di qué dispone cada uno, nombrando el artículo y citándolo con su número entre "
    "corchetes, por ejemplo [1]. Si entre las fuentes hay comentarios de un libro (empiezan con "
    "«Comentario:»), puedes sumar aquí cómo lo explican sus autores, con tus palabras y citándolo [n]; "
    "no copies párrafos del libro. Si no hay ninguno, omite esta sección.\n"
    "3. **Lo que dice la jurisprudencia:** explica el criterio de las sentencias que sirven, citando cada "
    "afirmación con su número entre corchetes, por ejemplo [2]. Si hay sentencias que dicen cosas "
    "distintas, señálalo. Si ninguna sentencia sirve, omite esta sección.\n"
    "4. **Análisis:** da tu opinión profesional: cómo se aplica al caso, qué argumentos conviene usar, "
    "qué riesgos o puntos débiles hay y qué conviene revisar o reunir (documentos, plazos, pruebas). "
    "Aquí puedes razonar más allá de las fuentes, pero sin citarlas como si lo dijera una sentencia o una ley.\n"
    "5. Solo si ninguna fuente trata ni la regla general ni un caso parecido, dilo en una o dos oraciones y sugiere cómo seguir (decirlo con otras "
    "palabras o subir sus propios documentos), sin las secciones 2, 3 y 4.\n\n"
    "Reglas: nunca inventes sentencias, números, fechas, artículos ni citas; [n] solo para lo que está en "
    "la fuente n. Si mencionas una ley o un artículo que no está en las fuentes, advierte que hay que "
    "verificarlo. Cálculos (prestaciones, plazos, montos): usa solo los días, escalas y fórmulas que dice "
    "el artículo de las fuentes según el tiempo y los datos del caso, muestra la operación paso a paso y cita "
    "el artículo [n]; si el artículo no está en las fuentes no pongas cifras de memoria: di qué artículo hay "
    "que revisar. No sumes conceptos que dependen de otra cosa (por ejemplo, una indemnización que solo da "
    "el tribunal) sin advertirlo. Si viene un «CÁLCULO DE PRESTACIONES», es el cálculo correcto hecho con las "
    "fórmulas del Código de Trabajo: muestra su tabla tal cual, explica cada concepto con su artículo y sus "
    "notas (también la de los días de vacaciones si viene), y no lo rehagas, no cambies montos ni le sumes "
    "nada; llámalo «el cálculo», sin decir de dónde salió. No repitas la pregunta. Usa negritas, listas "
    "cortas y, para cálculos o comparaciones, tablas de pocas columnas; nunca títulos con # ni fórmulas en "
    "LaTeX (nada de \\frac, \\times ni corchetes [ ] alrededor de una operación): escribe las operaciones "
    "con × y /, por ejemplo «14 días × RD$ 2,098.20 = RD$ 29,374.80». Eres una herramienta "
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


_PRESENTACION = ("Soy Papiniano, su asistente: busco en las sentencias de la Suprema Corte, en la Ley 108-05 de Registro Inmobiliario y sus "
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


def _normas_disponibles() -> str:
    """Las leyes y códigos cargados, para que la IA que prepara la búsqueda pida artículos que existen."""
    try:
        from .leyes import NORMAS, OBRAS
        nombres = [n["corto"] for n in NORMAS] + [o["corto"] + " (nuevo, Ley 74-25)" for o in OBRAS
                                                  if o["corto"] == "Código Penal"]
        return ", ".join(dict.fromkeys(nombres))
    except Exception:
        return "Código Civil, Código de Trabajo, Código Penal, Ley 108-05"


_NORMAS_DISPONIBLES = _normas_disponibles()


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
                "cortas (3 a 8 palabras) con sinónimos y términos jurídicos. Además, si sabes qué artículos "
                "regulan el tema, agrega hasta 3 búsquedas más, cada una con un solo artículo, escritas así: "
                "«art. 76 del Código de Trabajo». Solo de estas normas: " + _NORMAS_DISPONIBLES + ". Si no "
                "estás seguro del número, no lo agregues.\n"
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
        busquedas = [b for b in datos.get("busquedas", []) if isinstance(b, str) and b.strip()][:7]
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


# ── Cifras que no salen de las fuentes ─────────────
# La IA a veces pone plazos de memoria ("30 días de preaviso") que no dicen las fuentes. Se revisa cada
# "N días / meses / años…" de la respuesta: el número tiene que estar en las fuentes, en la pregunta o en la
# conversación, escrito con cifras o con letras (las leyes dicen "catorce días").
_UNIDADES = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
             "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
             "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
             "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
             "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30,
             "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
             "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300,
             "trescientas": 300, "cuatrocientos": 400, "quinientos": 500, "seiscientos": 600}
_PALABRA_NUM = r"(?:%s)" % "|".join(sorted(_UNIDADES, key=len, reverse=True))
_NUMERO_LETRAS = re.compile(r"\b%s(?:\s+(?:y\s+)?%s)*\b" % (_PALABRA_NUM, _PALABRA_NUM))
_CIFRA = re.compile(r"\b(\d{1,4}|%s(?:\s+(?:y\s+)?%s)*)\s*(?:\(\s*\d{1,4}\s*\)\s*)?"
                    r"(d[ií]as?|mes(?:es)?|a[ñn]os?|semanas?|horas?)\b" % (_PALABRA_NUM, _PALABRA_NUM), re.I)


def _sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _valor(numero: str) -> int:
    numero = _sin_tildes(numero)
    if numero.isdigit():
        return int(numero)
    return sum(_UNIDADES.get(p, 0) for p in numero.split() if p != "y")


def _numeros(texto: str) -> set:
    """Todos los números de un texto, escritos con cifras ("14", "1,500") o con letras ("catorce")."""
    texto = _sin_tildes(texto)
    nums = {int(n.replace(",", "").replace(".", "")) for n in re.findall(r"\d{1,3}(?:[.,]\d{3})+|\d+", texto)}
    return nums | {_valor(m.group(0)) for m in _NUMERO_LETRAS.finditer(texto)}


def cifras_sin_respaldo(respuesta: str, textos: list) -> list:
    """Las cifras con plazo ("30 días", "tres meses") de la respuesta que no salen de ningún texto dado."""
    validos = set().union(*(_numeros(t) for t in textos)) if textos else set()
    salida = []
    import unicodedata
    respuesta = unicodedata.normalize("NFC", respuesta)   # así quitar tildes no cambia las posiciones
    for m in _CIFRA.finditer(_sin_tildes(respuesta)):
        if _valor(m.group(1)) > 1 and _valor(m.group(1)) not in validos:
            salida.append(respuesta[m.start():m.end()].strip())
    return list(dict.fromkeys(salida))


def sin_latex(texto: str) -> str:
    """La app no dibuja fórmulas: '[ \\frac{14}{30}\\times 50,000 = 23,333.33\\ \\text{RD} ]' -> '14/30 × 50,000 = 23,333.33 RD'."""
    texto = re.sub(r"\\d?frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", texto)
    texto = re.sub(r"\\(?:text|mathrm|textbf|mathbf)\{([^{}]*)\}", r"\1", texto)
    texto = texto.replace("\\times", " × ").replace("\\cdot", " × ").replace("\\div", "/").replace("\\%", "%")
    texto = re.sub(r"\\[ ,;!]", " ", texto)
    texto = re.sub(r"\\[\[\]()]", "", texto)   # \[ \] \( \)
    # "[ 14/30 × 50,000 = … ]" en su propia línea: se quitan los corchetes (las citas [3] no se tocan)
    texto = re.sub(r"(?m)^(\s*)\[\s+(.*?[=×/].*?)\s+\]\s*$", r"\1\2", texto)
    return re.sub(r"(?<=\S)[ \t]{2,}", " ", texto)   # sin tocar la sangría de las listas


def responder(pregunta: str, fuentes: list, referencia, historial: list = None, calculo: str = None) -> dict:
    """Redacta la respuesta con análisis y quita cualquier cita a una fuente que no exista.
    Si pone plazos que no salen de las fuentes, se le pide una vez que los corrija; si insiste, se avisa."""
    fuentes = fuentes[:MAX_FUENTES]
    por_fuente = CARACTERES_FUENTES // max(len(fuentes), 1)
    bloque = "\n\n".join(f"[{n}] {referencia(f)}\n{f['texto'][:por_fuente]}" for n, f in enumerate(fuentes, 1))
    mensajes = [{"role": "system", "content": _SISTEMA},
                *_memoria(historial),
                {"role": "user", "content": f"Fuentes:\n\n{bloque}\n\n" + (f"{calculo}\n\n" if calculo else "")
                                            + f"Pregunta: {pregunta}"}]
    texto = _chat_en_cadena(mensajes, max_tokens=MAX_TOKENS_RESPUESTA)
    respaldo = [bloque, pregunta, calculo or ""] + [m["content"] for m in _memoria(historial)]
    dudosas = cifras_sin_respaldo(texto, respaldo)
    if dudosas:
        try:
            corregido = _chat_en_cadena(mensajes + [
                {"role": "assistant", "content": texto},
                {"role": "user", "content":
                    "Revisión: estas cifras de tu respuesta no aparecen en ninguna de las fuentes: "
                    + ", ".join(f"«{d}»" for d in dudosas) + ". Reescribe la respuesta completa usando solo "
                    "los plazos y cantidades que dicen las fuentes, con la operación paso a paso. Si el dato "
                    "que hace falta no está en las fuentes, no lo pongas: di qué artículo hay que verificar."}],
                max_tokens=MAX_TOKENS_RESPUESTA)
            if len(cifras_sin_respaldo(corregido, respaldo)) < len(dudosas):
                texto = corregido
        except Exception:
            pass   # sin cuota para corregir: queda la primera respuesta con el aviso
        dudosas = cifras_sin_respaldo(texto, respaldo)
        if dudosas:
            texto += ("\n\n> ⚠️ **Verifique estas cifras:** " + ", ".join(dudosas)
                      + ". No aparecen en las fuentes encontradas; pueden ser un error.")
    # algunos modelos citan como 【1】 o 【1†fuente】: se pasan a [1]
    texto = re.sub(r"【\s*(\d+)[^】]*】", r"[\1]", texto)
    texto = sin_latex(texto)
    validas = set(range(1, len(fuentes) + 1))
    citadas = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto)} & validas)
    texto = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in validas else "", texto)
    return {"texto": texto.strip(), "citadas": citadas}
