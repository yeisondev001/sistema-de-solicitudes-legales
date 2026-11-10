"""
Temas de colores de la app (Mi cuenta → Apariencia)
===================================================
Por fuera (la entrada) siempre se usa la marca, «Vino y madera». Por dentro cada
usuario elige uno de estos temas cerrados: no hay selector libre de colores, para
que el texto siempre se lea bien (contraste de 4,5 a 1 o más en todos).

Los nombres de los colores son los que usa main.py:
  INK, INK_SOFT     texto principal y secundario
  ACCENT            acento: pestaña activa, bordes en foco, íconos
  ACCENT_TEXT       acento como texto sobre el papel
  PAPER, PAPER_EDGE fondo de tarjetas y campos, y su borde suave
  RULE              líneas y bordes de los campos
  SURFACE           fondo de la página
  PANEL_INK         barra de arriba y globos del usuario en el chat
  ON_PANEL          texto sobre PANEL_INK
  NAV_TEXT, NAV_SUB pestañas inactivas sobre la barra
  NAV_LINEA         raya bajo la pestaña activa
  BAR_BTN(_TEXT)    botones de la barra (Jurisprudencia, Historial)
  BOTON, ON_BOTON   botón principal y su texto
  HINT              texto de ayuda en los campos
  PDF_COLOR         botón PDF y borrar
  AVISO_BG/_TEXT    avisos (plazos, cosas por revisar)
"""

# orden en que colores() los devuelve, para repartirlos en variables
NOMBRES = ("INK", "INK_SOFT", "ACCENT", "ACCENT_TEXT", "PAPER", "PAPER_EDGE", "RULE", "SURFACE",
           "PANEL_INK", "ON_PANEL", "NAV_TEXT", "NAV_SUB", "BAR_BTN", "BAR_BTN_TEXT", "BOTON", "ON_BOTON",
           "NAV_LINEA", "HINT", "PDF_COLOR", "AVISO_BG", "AVISO_TEXT")

MARCA = "madera"

TEMAS = {
    "madera": {
        "nombre": "Vino y madera", "descripcion": "El de la marca: el escritorio y los libros", "oscuro": False,
        "INK": "#241C17", "INK_SOFT": "#4A3F37", "ACCENT": "#7A1F2B", "ACCENT_TEXT": "#7A1F2B",
        "PAPER": "#FFFFFF", "PAPER_EDGE": "#E5DCCB", "RULE": "#DCD1BE", "SURFACE": "#F8F4EC",
        "PANEL_INK": "#3E2C20", "ON_PANEL": "#FBF6EC", "NAV_TEXT": "#EADFCF", "NAV_SUB": "#D9C4AA",
        "BAR_BTN": "#F1E8DA", "BAR_BTN_TEXT": "#7A1F2B", "BOTON": "#7A1F2B", "ON_BOTON": "#FFFFFF",
        "NAV_LINEA": "#E2C29B", "HINT": "#6A5D52", "PDF_COLOR": "#6B1A1A", "AVISO_BG": "#FBF1D6", "AVISO_TEXT": "#5E4610",
    },
    "papel": {
        "nombre": "Papel y tinta", "descripcion": "Lo más limpio y fácil de leer, sin adornos", "oscuro": False,
        "INK": "#1A1A1A", "INK_SOFT": "#4A4640", "ACCENT": "#7A1F2B", "ACCENT_TEXT": "#7A1F2B",
        "PAPER": "#FFFFFF", "PAPER_EDGE": "#E4DFD5", "RULE": "#D6D0C4", "SURFACE": "#FDFBF7",
        "PANEL_INK": "#F2EDE4", "ON_PANEL": "#1A1A1A", "NAV_TEXT": "#3A3733", "NAV_SUB": "#5B5650",
        "BAR_BTN": "#FFFFFF", "BAR_BTN_TEXT": "#7A1F2B", "BOTON": "#1A1A1A", "ON_BOTON": "#FDFBF7",
        "NAV_LINEA": "#7A1F2B", "HINT": "#5B5650", "PDF_COLOR": "#6B1A1A", "AVISO_BG": "#FBF1D6", "AVISO_TEXT": "#5E4610",
    },
    "cuero": {
        "nombre": "Cuero vino y azul", "descripcion": "Más formal: tapa de libro y azul oscuro", "oscuro": False,
        "INK": "#1A1D21", "INK_SOFT": "#44484E", "ACCENT": "#1F3A5F", "ACCENT_TEXT": "#1F3A5F",
        "PAPER": "#FFFFFF", "PAPER_EDGE": "#E6E3DC", "RULE": "#D6D2C8", "SURFACE": "#FAF8F3",
        "PANEL_INK": "#5E1A24", "ON_PANEL": "#FFF8F4", "NAV_TEXT": "#F3E7E1", "NAV_SUB": "#E2C9CC",
        "BAR_BTN": "#F3E7E1", "BAR_BTN_TEXT": "#1F3A5F", "BOTON": "#1F3A5F", "ON_BOTON": "#FFFFFF",
        "NAV_LINEA": "#F3E7E1", "HINT": "#55595F", "PDF_COLOR": "#6B1A1A", "AVISO_BG": "#FBF1D6", "AVISO_TEXT": "#5E4610",
    },
    "noche": {
        "nombre": "Biblioteca de noche", "descripcion": "Oscuro, para trabajar de noche", "oscuro": True,
        "INK": "#EFE6D8", "INK_SOFT": "#C9BCA9", "ACCENT": "#D8B27A", "ACCENT_TEXT": "#D8B27A",
        "PAPER": "#26201B", "PAPER_EDGE": "#3A302A", "RULE": "#4A3E35", "SURFACE": "#1C1714",
        "PANEL_INK": "#15110F", "ON_PANEL": "#EFE6D8", "NAV_TEXT": "#CFC3B2", "NAV_SUB": "#A89A87",
        "BAR_BTN": "#8C2A36", "BAR_BTN_TEXT": "#FFFFFF", "BOTON": "#8C2A36", "ON_BOTON": "#FFFFFF",
        "NAV_LINEA": "#D8B27A", "HINT": "#A89A87", "PDF_COLOR": "#E59A9A", "AVISO_BG": "#3A2F17", "AVISO_TEXT": "#E9CF8C",
    },
}


def tema(clave=None) -> dict:
    """El tema con esa clave; si no existe (o no eligió ninguno), la marca."""
    return TEMAS.get(clave or MARCA, TEMAS[MARCA])


def colores(t=None) -> tuple:
    """Los colores del tema en el orden de NOMBRES. Acepta la clave o el tema ya buscado."""
    t = t if isinstance(t, dict) else tema(t)
    return tuple(t[n] for n in NOMBRES)


def elegir(t, nombres: str) -> tuple:
    """Solo los colores pedidos, p. ej. elegir(t, "INK RULE"). t: clave, tema o None (la marca)."""
    t = t if isinstance(t, dict) else tema(t)
    return tuple(t[n] for n in nombres.split())
