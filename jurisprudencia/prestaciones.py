"""
Cálculo de prestaciones laborales con las reglas fijas del Código de Trabajo, para que los montos no
dependan de la IA (que divide entre 30, inventa escalas o suma la indemnización del art. 95 sin juicio).

Si la pregunta trae un salario y un tiempo trabajado y habla de despido, desahucio o prestaciones, se
calcula aquí y la IA solo lo explica (ver ia.responder, parámetro `calculo`).

Reglas (texto de los artículos en leyes/codigo-de-trabajo.pdf):
  salario diario   salario mensual / 23.83 (promedio de días laborables del mes, el que usa el
                   Ministerio de Trabajo)
  preaviso   76    3 a 6 meses: 7 días; más de 6 meses hasta 1 año: 14; más de 1 año: 28
  cesantía   80    3 a 6 meses: 6 días; 6 meses a 1 año: 13; 1 a 5 años: 21 por año;
                   5 años o más: 23 por año; la fracción de año mayor de 3 meses según los ordinales 1 y 2
  vacaciones 177, 179, 180, 182   menos de 1 año: escala del 180 (más de 5 meses: 6 días … más de 11: 12);
                   si no las disfrutó, se pagan (182). Con 1 año o más se calcula la proporción del año
                   en curso con la misma escala.
  Navidad    219, 220   la duodécima parte de lo ganado en el año calendario (proporcional)
  art. 95    solo si hay demanda y el tribunal declara injustificado el despido: hasta 6 meses de salario
             (desde la demanda hasta la sentencia). No se suma.
  art. 86    preaviso y cesantía se pagan en 10 días; si no, un día de salario por cada día de retraso.
"""

import re
from datetime import date

DIAS_MES = 23.83

_NUM = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
        "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
        "veinte": 20, "treinta": 30}
_N = r"(\d+(?:[.,]\d+)?|" + "|".join(_NUM) + r")"
_TEMA = re.compile(r"prestacion|liquidaci|despid|desahuci|cesant|preaviso|me botaron|me sacaron|me cancelaron"
                   r"|cancelaron|terminaron (?:el|mi) contrato", re.I)
_SALARIO = re.compile(
    r"(?:rd\s*\$?|\$|salario(?: mensual)?(?: de)?|gan(?:a|o|aba)|sueldo(?: de)?|cobr(?:a|o|aba))\s*(?:rd\s*\$?\s*)?"
    r"(\d{1,3}(?:[.,]\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d+)?)\s*(mil\b|k\b)?\s*(?:pesos)?\s*"
    r"(?:al |por |a la |cada )?(mes|mensual|quincena|quincenal|semana|semanal)?", re.I)
_SALARIO_PESOS = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,})\s*(?:pesos|rd)", re.I)
_ANIOS = re.compile(_N + r"\s*a[ñn]os?(?:\s*y\s*medio)?", re.I)
_MESES = re.compile(_N + r"\s*mes(?:es)?", re.I)
_DIAS = re.compile(_N + r"\s*d[ií]as?", re.I)


def _valor(t: str) -> float:
    t = t.lower()
    return float(_NUM[t]) if t in _NUM else float(t.replace(",", "."))


def _monto(texto: str):
    """Salario mensual que dice el texto (50,000 / 50 mil / RD$50000 / 25,000 quincenal)."""
    for m in _SALARIO.finditer(texto):
        cifra = m.group(1)
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+(?:\.\d{1,2})?", cifra):
            cifra = re.sub(r"[.,](?=\d{3}\b)", "", cifra)
        valor = float(cifra)
        if m.group(2):
            valor *= 1000
        if valor < 1000:   # "gana 8 meses…" o un número suelto: no es un salario
            continue
        periodo = (m.group(3) or "mes").lower()
        if periodo.startswith("quincen"):
            valor *= 2
        elif periodo.startswith("seman"):
            valor *= 4.33
        return valor
    m = _SALARIO_PESOS.search(texto)
    return float(re.sub(r"[.,]", "", m.group(1))) if m else None


def _tiempo_en_meses(texto: str):
    """Tiempo trabajado en meses (con fracción) que dice el texto: '2 años y 3 meses', '8 meses'."""
    sin_salario = re.sub(r"\d{1,3}(?:[.,]\d{3})+", " ", texto)
    meses = 0.0
    hallado = False
    # solo la primera mención de cada unidad: "tenía 8 meses… en esos 8 meses" no son 16
    m = _ANIOS.search(sin_salario)
    if m:
        meses += _valor(m.group(1)) * 12 + (6 if "medio" in m.group(0).lower() else 0)
        hallado = True
    m = _MESES.search(sin_salario)
    if m:
        meses += _valor(m.group(1))
        hallado = True
    m = _DIAS.search(sin_salario)
    if m and hallado:   # "8 meses y 15 días"; días sueltos suelen ser otra cosa (plazos)
        meses += _valor(m.group(1)) / 30
    return meses if hallado and meses > 0 else None


def _escala_vacaciones(meses: float) -> int:
    """Art. 180: más de 5 meses 6 días, más de 6 meses 7 … más de 11 meses 12."""
    for limite, dias in ((11, 12), (10, 11), (9, 10), (8, 9), (7, 8), (6, 7), (5, 6)):
        if meses > limite:
            return dias
    return 0


def _dinero(x: float) -> str:
    return f"RD$ {x:,.2f}"


def calcular(texto: str, hoy: date = None):
    """Si el texto pide prestaciones y trae salario y tiempo, devuelve el cálculo como texto (para la IA y
    para el abogado). Si falta un dato, None."""
    if not _TEMA.search(texto):
        return None
    salario, meses = _monto(texto), _tiempo_en_meses(texto)
    if not salario or not meses:
        return None
    hoy = hoy or date.today()
    diario = round(salario / DIAS_MES, 2)   # se redondea primero, como en la liquidación a mano
    anios, resto = int(meses // 12), meses - 12 * int(meses // 12)

    if meses < 3:
        preaviso = cesantia = 0
        nota_tiempo = "menos de 3 meses: no corresponde preaviso ni cesantía (arts. 76 y 80)"
    else:
        preaviso = 7 if meses <= 6 else 14 if meses <= 12 else 28
        if meses < 12:
            cesantia = 6 if meses <= 6 else 13
        else:
            por_anio = 23 if anios >= 5 else 21
            cesantia = anios * por_anio + (0 if resto <= 3 else 6 if resto <= 6 else 13)
        nota_tiempo = ""
    vacaciones = _escala_vacaciones(meses if meses < 12 else resto)
    meses_del_anio = min(meses, hoy.month - 1 + hoy.day / 30)
    navidad = salario * meses_del_anio / 12

    filas = [
        ("Preaviso", "art. 76", f"{preaviso} días", preaviso * diario),
        ("Auxilio de cesantía", "art. 80", f"{cesantia} días", cesantia * diario),
        ("Vacaciones no disfrutadas", "arts. 177, 180 y 182", f"{vacaciones} días", vacaciones * diario),
        ("Salario de Navidad proporcional", "arts. 219 y 220", f"{meses_del_anio:.1f}/12 del salario", navidad),
    ]
    total = sum(f[3] for f in filas)
    tiempo = (f"{anios} año{'s' if anios != 1 else ''} y " if anios else "") + f"{resto:.1f}".rstrip("0").rstrip(".") + " meses"
    lineas = [
        "CÁLCULO DE LA APP (fórmulas fijas del Código de Trabajo; úsalo tal cual, no lo rehagas):",
        f"Datos: salario mensual {_dinero(salario)}; tiempo trabajado {tiempo}; terminación por desahucio o "
        f"despido sin causa, contrato por tiempo indefinido.",
        "",
        f"Salario diario: {_dinero(salario)} / {DIAS_MES} = {_dinero(diario)}.",
        "",
        "| Concepto | Artículo | Días | Monto |",
        "|---|---|---|---|",
        *[f"| {c} | {a} | {d} | {_dinero(m)} |" for c, a, d, m in filas],
        f"| **Total** | | | **{_dinero(total)}** |",
        "",
        "Notas:",
        "- Preaviso y cesantía se pagan dentro de 10 días; si no, el empleador debe además un día de salario "
        f"({_dinero(diario)}) por cada día de retraso (art. 86).",
        "- Vacaciones: solo si no las disfrutó. Navidad: se supuso que trabajó en este año "
        f"{meses_del_anio:.1f} meses; si fueron otros, cambia. El salario de Navidad no puede pasar de cinco "
        "salarios mínimos (art. 219).",
        "- Si el salario variaba (comisiones, horas extra), el diario se saca del promedio del último año.",
        "- Art. 95: NO está sumado. Solo si el trabajador demanda y el tribunal declara injustificado el despido, "
        f"además se le pagan los salarios desde la demanda hasta la sentencia, hasta un máximo de 6 meses "
        f"({_dinero(6 * salario)}).",
    ]
    if meses >= 12:
        lineas.append(f"- Si no disfrutó las vacaciones del último año cumplido, se suman {18 if anios >= 5 else 14} "
                      f"días más ({_dinero((18 if anios >= 5 else 14) * diario)}) (arts. 177 y 182); la tabla solo "
                      "tiene la proporción del año en curso.")
    if nota_tiempo:
        lineas.append("- " + nota_tiempo)
    return "\n".join(lineas)


def para_mostrar(calculo: str) -> str:
    """El cálculo tal cual para el abogado, sin la instrucción que lleva para la IA."""
    return re.sub(r"^CÁLCULO DE LA APP.*\n", "**Cálculo de prestaciones (Código de Trabajo)**\n\n", calculo)
