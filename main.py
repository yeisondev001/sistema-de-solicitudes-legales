"""
Automatización de Solicitudes Legales
======================================
UI principal — generación de documentos en generators/
"""

import os, base64, copy, functools, platform, pathlib, re, secrets, uuid, time, threading
from datetime import date, datetime, timedelta, timezone

import flet as ft

import cuentas
import historial
import temas
from jurisprudencia import basedatos as juris_db, buscador as juris_buscar, ia as juris_ia, procesar as juris_proc
from jurisprudencia import visor as juris_visor, prestaciones as juris_prestaciones
from generators import (
    generar_informe_tecnico,
    generar_copia_certificada,
    generar_reporte_audiencia,
    generar_solicitud_cobros,
    generar_solicitud_inspeccion,
    generar_informe_audiencia_provincial,
    generar_conclusiones_saneamiento,
    generar_expedientes,
    nombre_archivo,
    pdf_informe_tecnico,
    pdf_copia_certificada,
    pdf_reporte_audiencia,
    pdf_solicitud_cobros,
    pdf_solicitud_inspeccion,
    pdf_informe_audiencia_provincial,
    pdf_conclusiones_saneamiento,
)

# ── PALETA ───────────────────────────────────────
# La de la marca («Vino y madera»), que se ve en la entrada. Por dentro app_principal usa
# el tema que eligió cada usuario (temas.py); qué es cada color está explicado allí.
(INK, INK_SOFT, ACCENT, ACCENT_TEXT, PAPER, PAPER_EDGE, RULE, SURFACE, PANEL_INK, ON_PANEL, NAV_TEXT, NAV_SUB,
 BAR_BTN, BAR_BTN_TEXT, BOTON, ON_BOTON, NAV_LINEA, HINT, PDF_COLOR, AVISO_BG, AVISO_TEXT) = temas.colores()

FONT_DISPLAY = "Literata"                 # títulos: serif de libro, hecha para leer en pantalla
FONT_BODY    = "Atkinson Hyperlegible"    # texto: letras que no se confunden (I l 1, O 0)
FUENTES = {
    FONT_DISPLAY: "https://cdn.jsdelivr.net/fontsource/fonts/literata@5.3.0/latin-500-normal.ttf",
    FONT_BODY:    "https://cdn.jsdelivr.net/fontsource/fonts/atkinson-hyperlegible@5.3.0/latin-400-normal.ttf",
}
ANCHO_MAX    = 1200       # ancho máximo del contenido en pantallas grandes
NOMBRE_APP   = "Papiniano"  # nombre del producto (igual que su asistente)
ZONA_RD      = timezone(timedelta(hours=-4))   # República Dominicana no cambia la hora en verano
DIAS_SEMANA  = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES_ANIO   = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                "octubre", "noviembre", "diciembre")

KT_NUM    = ft.KeyboardType.NUMBER
RE_FECHA  = re.compile(r"[^0-9/]")
RE_CEDULA = re.compile(r"[^0-9\-]")

# Las listas de tribunales, salas y asuntos están en redaccion.py (también las usa servidor.py)
from redaccion import (
    TRIBUNALES_INMOBILIARIA, TRIBUNALES_CIVIL, SALAS_INMOBILIARIA, ASUNTOS_INMOBILIARIA,
    TIPOS_AUDIENCIA_PROVINCIAL, RECLAMANTES_SANEAMIENTO,
)


# ── DESCARGA ─────────────────────────────────────
def _descargar(page, contenido: bytes, nombre: str, mime: str, snack_fn, t=None):
    INK, INK_SOFT, PAPER, BOTON, ON_BOTON = temas.elegir(t, "INK INK_SOFT PAPER BOTON ON_BOTON")
    if platform.system() == "Windows":
        descargas = pathlib.Path.home() / "Downloads"
        descargas.mkdir(exist_ok=True)
        ruta = descargas / nombre
        ruta.write_bytes(contenido)
        os.startfile(str(ruta))
        snack_fn(f"✓ Guardado en Descargas: {nombre}")
    else:
        dl_dir = pathlib.Path("assets") / "dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        # Limpieza: subcarpetas o archivos viejos (>1h)
        try:
            now = time.time()
            for f in dl_dir.iterdir():
                try:
                    if (now - f.stat().st_mtime) > 3600:
                        if f.is_dir():
                            for sub in f.iterdir():
                                sub.unlink(missing_ok=True)
                            f.rmdir()
                        else:
                            f.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            pass
        uid     = uuid.uuid4().hex[:8]
        safe    = re.sub(r"[^\w \-.()ñÑáéíóúÁÉÍÓÚ]", "_", nombre).strip() or "documento"
        sub_dir = dl_dir / uid
        sub_dir.mkdir(parents=True, exist_ok=True)
        (sub_dir / safe).write_bytes(contenido)
        fname = f"{uid}/{safe}"

        def _cerrar(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=PAPER,
            title=ft.Row(controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color="#2E7D32", size=20),
                ft.Text("  Documento listo", font_family=FONT_DISPLAY, color=INK, size=18),
            ]),
            content=ft.Column(controls=[
                ft.Text(nombre, font_family=FONT_BODY, color=INK_SOFT, size=13),
                ft.Container(height=10),
                ft.Text(
                    "Toca DESCARGAR para guardar el archivo.\n"
                    "iPhone → app Archivos → Descargas",
                    font_family=FONT_BODY, color=INK_SOFT, size=12, italic=True,
                ),
            ], tight=True, spacing=0),
            actions=[
                ft.TextButton("Cerrar", on_click=_cerrar,
                              style=ft.ButtonStyle(color=INK_SOFT)),
                ft.ElevatedButton(
                    "⬇  Descargar",
                    url=f"/dl/{fname}",
                    url_target="_blank",
                    style=ft.ButtonStyle(
                        bgcolor=BOTON, color=ON_BOTON,
                        shape=ft.RoundedRectangleBorder(radius=2),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        page.open(dlg)


def _guardar_y_abrir(page, contenido: bytes, nombre: str, snack_fn, t=None):
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    _descargar(page, contenido, nombre, mime, snack_fn, t)


def _guardar_pdf(page, contenido: bytes, nombre: str, snack_fn, t=None):
    _descargar(page, contenido, nombre, "application/pdf", snack_fn, t)


# ── HELPERS UI ───────────────────────────────────
def fila_campos(*controles):
    """Campos lado a lado en pantallas anchas; uno debajo del otro en el celular."""
    for c in controles:
        c.col = {"xs": 12, "md": 12 // len(controles)}
        c.expand = False
    return ft.ResponsiveRow(controls=list(controles), spacing=24, run_spacing=14)


def campo(label, form, key, on_change, hint=None, multiline=False, required=False, expand=True,
          keyboard_type=None, char_filter=None, date_format=False, t=None):
    INK, INK_SOFT, ACCENT, ACCENT_TEXT, RULE, HINT = temas.elegir(t, "INK INK_SOFT ACCENT ACCENT_TEXT RULE HINT")

    def _on_change(e, k=key):
        val = e.control.value
        if char_filter:
            clean = char_filter.sub("", val)
            if clean != val:
                e.control.value = clean
                e.control.update()
                val = clean
        form[k] = val
        on_change()

    tf = ft.TextField(
        value=form.get(key, ""),
        hint_text=hint,
        multiline=multiline,
        min_lines=2 if multiline else 1,
        max_lines=4 if multiline else 1,
        border=ft.InputBorder.UNDERLINE,
        border_color=RULE,
        focused_border_color=ACCENT,
        focused_border_width=2,
        cursor_color=ACCENT,
        text_style=ft.TextStyle(font_family=FONT_BODY, size=15, color=INK, italic=True),
        hint_style=ft.TextStyle(font_family=FONT_BODY, italic=True, color=HINT),
        content_padding=ft.padding.symmetric(vertical=8, horizontal=2),
        keyboard_type=keyboard_type,
        on_change=_on_change,
    )
    req_star = ft.Text(" *", color=ACCENT_TEXT, size=12) if required else ft.Text("")
    return ft.Column(
        controls=[
            ft.Row(controls=[
                ft.Text(label.upper(), size=12, weight=ft.FontWeight.W_600,
                        color=INK_SOFT, font_family=FONT_BODY),
                req_star,
            ], spacing=0),
            tf,
        ],
        spacing=4, expand=expand,
    )


def combobox_campo(label, form, key, options, update_fn, required=False, expand=True, hint=None,
                   filter_on_type=True, t=None):
    """Campo con lista desplegable. Si filter_on_type=False, la lista siempre muestra todas las opciones."""
    INK, INK_SOFT, ACCENT, ACCENT_TEXT, PAPER, PAPER_EDGE, RULE, HINT = temas.elegir(
        t, "INK INK_SOFT ACCENT ACCENT_TEXT PAPER PAPER_EDGE RULE HINT")

    opts_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO)
    opts_container = ft.Container(
        content=opts_col,
        bgcolor=PAPER,
        border=ft.border.all(1, RULE),
        border_radius=ft.border_radius.only(bottom_left=4, bottom_right=4),
        shadow=ft.BoxShadow(blur_radius=8, spread_radius=0, color="#25000000"),
        visible=False,
        padding=0,
        margin=ft.margin.only(top=1),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    tf = ft.TextField(
        value=form.get(key, ""),
        hint_text=hint or "Escriba para buscar o ingrese un valor personalizado…",
        border=ft.InputBorder.UNDERLINE,
        border_color=RULE,
        focused_border_color=ACCENT,
        focused_border_width=2,
        cursor_color=ACCENT,
        text_style=ft.TextStyle(font_family=FONT_BODY, size=15, color=INK, italic=True),
        hint_style=ft.TextStyle(font_family=FONT_BODY, italic=True, color=HINT),
        content_padding=ft.padding.symmetric(vertical=8, horizontal=2),
        suffix=ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=INK_SOFT, size=20),
    )

    _selecting = [False]

    def _rebuild_opts(query=""):
        if filter_on_type:
            q = query.lower().strip()
            filtered = [o for o in options if not q or q in o.lower()]
        else:
            filtered = list(options)
        opts_col.controls.clear()
        for opt in filtered:
            def make_item(o=opt):
                def _mouse_down(e):
                    _selecting[0] = True

                def _on_select(e):
                    tf.value = o
                    form[key] = o
                    opts_container.visible = False
                    _selecting[0] = False
                    update_fn()

                return ft.Container(
                    content=ft.Text(o, font_family=FONT_BODY, size=13, color=INK,
                                    no_wrap=False),
                    padding=ft.padding.symmetric(vertical=9, horizontal=12),
                    on_click=_on_select,
                    ink=True,
                    border=ft.border.only(bottom=ft.BorderSide(0.5, PAPER_EDGE)),
                    bgcolor=PAPER,
                )
            opts_col.controls.append(make_item())
        opts_container.visible = bool(filtered)

    def on_tf_change(e):
        form[key] = e.control.value
        _rebuild_opts(e.control.value)
        update_fn()

    def on_focus(e):
        _rebuild_opts(tf.value or "")
        update_fn()

    def on_blur(e):
        def _hide():
            time.sleep(0.3)
            if not _selecting[0]:
                opts_container.visible = False
                update_fn()
        threading.Thread(target=_hide, daemon=True).start()

    tf.on_change = on_tf_change
    tf.on_focus  = on_focus
    tf.on_blur   = on_blur

    req_star = ft.Text(" *", color=ACCENT_TEXT, size=12) if required else ft.Text("")

    return ft.Column(
        controls=[
            ft.Row(controls=[
                ft.Text(label.upper(), size=12, weight=ft.FontWeight.W_600,
                        color=INK_SOFT, font_family=FONT_BODY),
                req_star,
            ], spacing=0),
            tf,
            opts_container,
        ],
        spacing=4, expand=expand,
    )


def materia_selector(page, form, key, on_materia_change, t=None):
    """Selector de dos opciones con lista en los colores de la plantilla."""
    INK, INK_SOFT, PAPER, PAPER_EDGE, RULE, HINT = temas.elegir(t, "INK INK_SOFT PAPER PAPER_EDGE RULE HINT")
    opciones = ["MATERIA INMOBILIARIA", "MATERIA CIVIL"]

    valor_text = ft.Text(
        form.get(key) or "Seleccione una materia…",
        font_family=FONT_BODY, size=15,
        color=INK if form.get(key) else HINT,
        italic=not bool(form.get(key)),
    )

    opts_col = ft.Column(spacing=0)
    opts_container = ft.Container(
        content=opts_col, bgcolor=PAPER,
        border=ft.border.all(1, RULE),
        border_radius=ft.border_radius.only(bottom_left=4, bottom_right=4),
        shadow=ft.BoxShadow(blur_radius=8, spread_radius=0, color="#25000000"),
        visible=False,
        margin=ft.margin.only(top=1),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    def _build_opts():
        opts_col.controls.clear()
        for opt in opciones:
            def make_item(o=opt):
                def _sel(e):
                    form[key] = o
                    valor_text.value = o
                    valor_text.color = INK
                    valor_text.italic = False
                    opts_container.visible = False
                    on_materia_change()
                return ft.Container(
                    content=ft.Text(o, font_family=FONT_BODY, size=14, color=INK),
                    padding=ft.padding.symmetric(vertical=10, horizontal=12),
                    on_click=_sel, ink=True, bgcolor=PAPER,
                    border=ft.border.only(bottom=ft.BorderSide(0.5, PAPER_EDGE)),
                )
            opts_col.controls.append(make_item())
    _build_opts()

    def _toggle(e):
        opts_container.visible = not opts_container.visible
        page.update()

    cabecera = ft.Container(
        content=ft.Row(controls=[
            valor_text,
            ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=INK_SOFT, size=22),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.only(top=8, bottom=8, left=2, right=2),
        border=ft.border.only(bottom=ft.BorderSide(1, RULE)),
        on_click=_toggle, ink=True,
    )

    return ft.Column(controls=[
        ft.Text("MATERIA", size=12, weight=ft.FontWeight.W_600,
                color=INK_SOFT, font_family=FONT_BODY),
        cabecera,
        opts_container,
    ], spacing=4)


def tarjeta(romano, titulo, subtitulo, contenido, t=None):
    INK, INK_SOFT, ACCENT, ACCENT_TEXT, PAPER, PAPER_EDGE, RULE = temas.elegir(
        t, "INK INK_SOFT ACCENT ACCENT_TEXT PAPER PAPER_EDGE RULE")
    return ft.Container(
        content=ft.Column(controls=[
            ft.Row(controls=[
                ft.Container(
                    content=ft.Text(romano, size=18, italic=True,
                                    color=ACCENT_TEXT, font_family=FONT_DISPLAY),
                    width=38, height=38,
                    border=ft.border.all(1, ACCENT),
                    alignment=ft.alignment.center,
                ),
                ft.Column(controls=[
                    ft.Text(titulo, size=20, weight=ft.FontWeight.W_500,
                            color=INK, font_family=FONT_DISPLAY),
                    ft.Text(subtitulo, size=12, italic=True,
                            color=INK_SOFT, font_family=FONT_BODY),
                ], spacing=2, tight=True),
            ], spacing=14),
            ft.Container(height=1, bgcolor=RULE,
                         margin=ft.margin.symmetric(vertical=12), opacity=0.6),
            contenido,
        ], spacing=0),
        bgcolor=PAPER, border=ft.border.all(1, PAPER_EDGE), padding=ft.padding.all(22),
    )


def boton_generar(on_click, texto="GENERAR DOCUMENTO WORD", t=None):
    BOTON, ON_BOTON = temas.elegir(t, "BOTON ON_BOTON")
    return ft.Container(
        content=ft.Row(controls=[
            ft.Icon(ft.Icons.DOWNLOAD, color=ON_BOTON, size=18),
            ft.Text(texto, size=14,
                    weight=ft.FontWeight.W_500, color=ON_BOTON, font_family=FONT_DISPLAY),
        ], spacing=14, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=BOTON,
        padding=ft.padding.symmetric(vertical=16, horizontal=34),
        on_click=on_click, ink=True, border_radius=2,
    )


def boton_pdf(on_click, t=None):
    PAPER, PDF_COLOR = temas.elegir(t, "PAPER PDF_COLOR")
    return ft.Container(
        content=ft.Row(controls=[
            ft.Icon(ft.Icons.PICTURE_AS_PDF, color=PAPER, size=18),
            ft.Text("GENERAR DOCUMENTO PDF", size=14,
                    weight=ft.FontWeight.W_500, color=PAPER, font_family=FONT_DISPLAY),
        ], spacing=14, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=PDF_COLOR,
        padding=ft.padding.symmetric(vertical=16, horizontal=34),
        on_click=on_click, ink=True, border_radius=2,
    )


def nota_descarga(t=None):
    INK_SOFT, = temas.elegir(t, "INK_SOFT")
    return ft.Container(
        content=ft.Text(
            "El archivo .docx se guardará en Descargas con el formato oficial.",
            size=12, italic=True, color=INK_SOFT, font_family=FONT_BODY,
            text_align=ft.TextAlign.CENTER,
        ),
        alignment=ft.alignment.center,
    )


# ══════════════════════════════════════════════════
#  APP PRINCIPAL
# ══════════════════════════════════════════════════
def aplicar_tema(page: ft.Page, t=None):
    """Fondo, modo claro u oscuro y colores de los controles propios de Flet (menús, casillas, diálogos)."""
    t = t if isinstance(t, dict) else temas.tema(t)
    page.bgcolor = t["SURFACE"]
    page.theme_mode = ft.ThemeMode.DARK if t["oscuro"] else ft.ThemeMode.LIGHT
    page.theme = page.dark_theme = ft.Theme(
        font_family=FONT_BODY, color_scheme_seed=t["ACCENT"],
        color_scheme=ft.ColorScheme(primary=t["ACCENT"], on_primary=t["PAPER"],
                                    surface=t["PAPER"], on_surface=t["INK"]),
    )


def app_principal(page: ft.Page, usuario: dict, salir, seccion=None):
    hoy = date.today()
    # Los colores son los del tema que eligió en Mi cuenta → Apariencia: estas variables tapan a
    # las de la marca, y las ayudas de afuera (campo, tarjeta, …) reciben el tema con t=.
    tema = temas.tema(usuario.get("tema"))
    (INK, INK_SOFT, ACCENT, ACCENT_TEXT, PAPER, PAPER_EDGE, RULE, SURFACE, PANEL_INK, ON_PANEL, NAV_TEXT, NAV_SUB,
     BAR_BTN, BAR_BTN_TEXT, BOTON, ON_BOTON, NAV_LINEA, HINT, PDF_COLOR, AVISO_BG, AVISO_TEXT) = temas.colores(tema)
    (_guardar_y_abrir, _guardar_pdf, campo, combobox_campo, materia_selector, tarjeta, boton_generar, boton_pdf,
     nota_descarga) = (functools.partial(globals()[n], t=tema) for n in (
        "_guardar_y_abrir", "_guardar_pdf", "campo", "combobox_campo", "materia_selector", "tarjeta",
        "boton_generar", "boton_pdf", "nota_descarga"))
    aplicar_tema(page, tema)
    # el menú de las salas queda fijo y cada sección se desliza por dentro (ver form_area)
    page.scroll = None

    # las plantillas de solicitudes (sala Redacción) son solo para las cuentas que las tienen activadas
    con_plantillas = usuario.get("plantillas", False)
    # la sección abierta: "escritorio", "jurisprudencia" (el Asistente), "biblioteca",
    # "historial" o una plantilla
    plantilla = {"actual": seccion or "escritorio"}

    # ── VALORES POR DEFECTO DE FORMULARIOS ───────
    form_informe = {
        "fecha_carta":        f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}",
        "destinatario":       "Arq. Gilberto Grullón.",
        "cargo_destinatario": "Director técnico.",
        "atencion_nombre":    "Agrim. Julio Yens Seijas,",
        "atencion_cargo":     "Encargado del Depto. de Catastro",
        "asunto":             "Solicitud de Investigación Parcelaria.",
        "anexos":             ["Acto No. ", "Certificado de Inscripción Catastral No. "],
        "inscripcion_no":     "",
        "propietario":        "",
        "fecha_audiencia":    "",
        "salon":              "3",
        "piso":               "Segundo Piso",
        "lugar":              "Ciudad Judicial",
        "expediente":         "",
        "cliente":            "",
        "firmante_nombre":    "YOLANDA DE LA CRUZ VARGAS.",
        "firmante_cargo":     "Directora Legal.",
        "iniciales":          "JDCV/rr",
    }

    form_archivo = {
        "fecha_carta":          f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}",
        "destinatario":         "Sr. Leibi Rafael Méndez Beltre.",
        "cargo_destinatario":   "Encargado interino de la División de Archivos de Expedientes Legales.",
        "asunto":               "Solicitud de Copia Certificada de Expediente.",
        "nombre_cliente":       "",
        "cedula":               "",
        "descripcion_inmueble": "",
        "materia":              "",
        "tipo_proceso":         "deslinde",
        "tribunal":             "",
        "sala":                 "",
        "firmante_nombre":      "YOLANDA DE LA CRUZ VARGAS.",
        "firmante_cargo":       "Directora Legal.",
        "iniciales":            "YDCV/rr",
    }

    form_reporte = {
        "materia":         "",
        "tribunal":        "",
        "sala":            "",
        "expediente":      "",
        "demandantes":     "",
        "demandados":      [""],
        "asunto":          "Solicitud de Deslinde.",
        "parcela":         "",
        "agrimensor":      "",
        "caja_no":         "",
        "rol":             "",
        "fecha_audiencia": f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}",
        "fallo":           "",
        "fecha_proxima":   "",
        "abogados":        "",
    }

    form_cobros = {
        "fecha_carta":        f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}",
        "destinatario":       "Licda. Denisse Amadés",
        "cargo_destinatario": "Encargada dpto. de cobros.",
        "asunto":             "SI EXISTE CUENTA O PAGO.",
        "nombre_cliente":     "",
        "materia":            "",
        "tipo_proceso":       "Saneamiento",
        "parcela":            "Designación Posesional No.",
        "municipio":          "",
        "provincia":          "",
        "expediente":         "",
        "cedula":             "",
        "tribunal":           "",
        "sala":               "",
        "sentencia":          "",
        "fecha_sentencia":    "",
        "tribunal_original":  "",
        "firmante_nombre":    "LICDA. YOLANDA DE LA CRUZ VARGAS.",
        "firmante_cargo":     "Directora Legal.",
        "iniciales":          "YDLCV/rr",
    }

    form_inspeccion = {
        "fecha_carta":        f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}",
        "destinatario":       "",
        "cargo_destinatario": "Director Técnico",
        "atencion_nombre":    "",
        "atencion_cargo":     "Encargada dpto. de Inspección.",
        "asunto":             "Solicitud de Inspección",
        "cuerpo_1":           "Muy cortésmente, por medio de la presente, solicitamos que nos informe ",
        "cuerpo_2":           "",
        "firmante_nombre":    "YOLANDA DE LA CRUZ VARGAS.",
        "firmante_cargo":     "Directora Legal.",
        "iniciales":          "YDLCV/rr",
        "cc":                 "",
    }

    form_audiencia_provincial = {
        "fecha_informe": f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}",
        "provincia": "",
        "municipio": "",
        "fecha_desde": f"{hoy.day:02d}/{hoy.month:02d}/{hoy.year}",
        "fecha_hasta": "",
        "tribunal": "",
        "tipo_proceso": "Deslinde",
        "inmueble": "",
        "demandante": "",
        "expediente": "",
        "resultado": "",
    }

    form_conclusiones_saneamiento = {
        "expediente": "",
        "reclamante": RECLAMANTES_SANEAMIENTO[0],
        "inmueble": "",
    }

    form_area = ft.Column(spacing=20, scroll=ft.ScrollMode.AUTO, expand=True)

    def snack(msg, ok=True):
        page.open(ft.SnackBar(
            content=ft.Text(msg, color="#FFFFFF", font_family=FONT_BODY),
            bgcolor="#2E7D32" if ok else "#B71C1C",
        ))

    # ── PLANTILLA 1: INFORME TÉCNICO ─────────────
    def build_informe():
        form = form_informe
        def rf(): page.update()

        anexos_col = ft.Column(spacing=8)

        def build_anexos():
            anexos_col.controls.clear()
            for idx, val in enumerate(form["anexos"]):
                def make_row(i=idx, v=val):
                    tf = ft.TextField(
                        value=v, hint_text="Ej: Acto No. 02/2026.",
                        border=ft.InputBorder.UNDERLINE, border_color=RULE,
                        focused_border_color=ACCENT, focused_border_width=2,
                        cursor_color=ACCENT,
                        text_style=ft.TextStyle(font_family=FONT_BODY, size=15, color=INK, italic=True),
                        hint_style=ft.TextStyle(font_family=FONT_BODY, italic=True, color=HINT),
                        content_padding=ft.padding.symmetric(vertical=8, horizontal=2),
                        expand=True,
                        on_change=lambda e, i_=i: form["anexos"].__setitem__(i_, e.control.value),
                    )
                    def on_remove(e, i_=i):
                        if len(form["anexos"]) > 1:
                            form["anexos"].pop(i_); build_anexos(); page.update()
                    return ft.Row(controls=[
                        ft.Text(f"{i+1}-", size=13, color=INK_SOFT, font_family=FONT_BODY, width=28),
                        tf,
                        ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_color=ACCENT,
                                      icon_size=18, tooltip="Eliminar anexo", on_click=on_remove),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                anexos_col.controls.append(make_row())

            def on_agregar(e):
                form["anexos"].append(""); build_anexos(); page.update()
            anexos_col.controls.append(ft.TextButton(
                content=ft.Row(controls=[
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=ACCENT, size=16),
                    ft.Text("Agregar anexo", color=ACCENT_TEXT, size=13, font_family=FONT_BODY),
                ], spacing=6), on_click=on_agregar,
            ))

        build_anexos()

        def _validar_informe():
            reqs = [("inscripcion_no","No. Inscripción Catastral"),("propietario","Propietario"),
                    ("fecha_audiencia","Fecha de audiencia"),("expediente","No. Expediente"),("cliente","Cliente")]
            faltantes = [n for k, n in reqs if not form.get(k,"").strip()]
            if not any(a.strip() for a in form.get("anexos",[])):
                faltantes.append("al menos un Anexo")
            return faltantes

        def on_generar(e):
            faltantes = _validar_informe()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = generar_informe_tecnico(form)
                _guardar_y_abrir(page, contenido, nombre_archivo("Informe Tecnico", form.get("cliente","Solicitud")), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        def on_pdf_informe(e):
            faltantes = _validar_informe()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = pdf_informe_tecnico(form)
                _guardar_pdf(page, contenido, nombre_archivo("Informe Tecnico", form.get("cliente","Solicitud")).replace(".docx",".pdf"), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            tarjeta("I",   "Encabezado", "Destinatario y asunto", ft.Column(controls=[
                fila_campos(campo("Fecha de la carta", form,"fecha_carta",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Asunto",form,"asunto",rf,required=True)),
                ft.Container(height=14),
                fila_campos(campo("Destinatario",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)),
                ft.Container(height=14),
                fila_campos(campo("Nombre (Atención)",form,"atencion_nombre",rf),
                                 campo("Cargo (Atención)",form,"atencion_cargo",rf)),
            ])),
            tarjeta("II",  "Inmueble", "Inscripción catastral, anexos y propietario", ft.Column(controls=[
                ft.Row(controls=[ft.Text("ANEXOS",size=12,weight=ft.FontWeight.W_600,color=INK_SOFT,font_family=FONT_BODY),
                                 ft.Text(" *", color=ACCENT_TEXT, size=12)], spacing=0),
                anexos_col, ft.Container(height=14),
                campo("No. Inscripción Catastral (cuerpo)",form,"inscripcion_no",rf,required=True),
                ft.Container(height=14),
                campo("Nombre del propietario / propietarios",form,"propietario",rf,multiline=True,required=True),
            ])),
            tarjeta("III", "Audiencia", "Fecha, lugar y expediente", ft.Column(controls=[
                fila_campos(
                    campo("Fecha de audiencia",form,"fecha_audiencia",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                    fila_campos(campo("Salón",form,"salon",rf), campo("Piso",form,"piso",rf))),
                ft.Container(height=14),
                fila_campos(campo("Lugar",form,"lugar",rf),
                                 campo("No. Expediente",form,"expediente",rf,required=True)),
                ft.Container(height=14),
                campo("Nombre del cliente",form,"cliente",rf,multiline=True,required=True),
            ])),
            tarjeta("IV",  "Firma", "Quien suscribe la solicitud", ft.Column(controls=[
                fila_campos(campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)),
                ft.Container(height=14),
                campo("Iniciales",form,"iniciales",rf,expand=False),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(on_generar), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(on_pdf_informe), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── PLANTILLA 2: COPIA CERTIFICADA ───────────
    def build_archivo():
        form = form_archivo
        def rf(): page.update()

        # Wrappers reactivos a la Materia (Asunto, Tribunal y Sala)
        asunto_wrap   = ft.Column(spacing=0, expand=True)
        tribunal_wrap = ft.Column(spacing=0, expand=True)
        sala_wrap     = ft.Column(spacing=0, expand=True)

        def rebuild_materia_fields():
            mat = form.get("materia", "")
            asunto_wrap.controls.clear()
            tribunal_wrap.controls.clear()
            sala_wrap.controls.clear()

            if mat == "MATERIA INMOBILIARIA":
                asunto_wrap.controls.append(
                    combobox_campo("Asunto", form, "asunto",
                                   ASUNTOS_INMOBILIARIA, rf, required=True, expand=True,
                                   filter_on_type=False)
                )
                tribunal_wrap.controls.append(
                    combobox_campo("Tribunal", form, "tribunal",
                                   TRIBUNALES_INMOBILIARIA, rf, required=True, expand=True)
                )
                sala_wrap.controls.append(
                    combobox_campo("Sala", form, "sala",
                                   SALAS_INMOBILIARIA, rf, expand=True)
                )
            elif mat == "MATERIA CIVIL":
                asunto_wrap.controls.append(
                    campo("Asunto", form, "asunto", rf, required=True, expand=True)
                )
                tribunal_wrap.controls.append(
                    combobox_campo("Tribunal", form, "tribunal",
                                   TRIBUNALES_CIVIL, rf, required=True, expand=True)
                )
                sala_wrap.controls.append(
                    campo("Sala", form, "sala", rf, expand=True)
                )
            else:
                asunto_wrap.controls.append(
                    campo("Asunto", form, "asunto", rf, required=True, expand=True)
                )
                tribunal_wrap.controls.append(
                    campo("Tribunal / Sala", form, "tribunal", rf,
                          multiline=True, required=True, expand=True)
                )

        rebuild_materia_fields()

        materia_dd = materia_selector(page, form, "materia", lambda: (rebuild_materia_fields(), rf()))

        def _validar_archivo():
            reqs = [("nombre_cliente","Nombre del cliente"),("cedula","Cédula"),
                    ("descripcion_inmueble","Descripción del inmueble"),
                    ("tipo_proceso","Tipo de proceso"),("tribunal","Tribunal")]
            return [n for k, n in reqs if not form.get(k,"").strip()]

        def on_generar(e):
            faltantes = _validar_archivo()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = generar_copia_certificada(form)
                _guardar_y_abrir(page, contenido, nombre_archivo("Solicitud de Archivo", form.get("nombre_cliente","Solicitud")), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        def on_pdf_archivo(e):
            faltantes = _validar_archivo()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = pdf_copia_certificada(form)
                _guardar_pdf(page, contenido, nombre_archivo("Solicitud de Archivo", form.get("nombre_cliente","Solicitud")).replace(".docx",".pdf"), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            tarjeta("I",   "Encabezado", "Destinatario y asunto", ft.Column(controls=[
                ft.Row(controls=[campo("Fecha de la carta",form,"fecha_carta",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 asunto_wrap], spacing=24, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(height=14),
                fila_campos(campo("Destinatario (A)",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)),
            ])),
            tarjeta("II",  "Expediente", "Cliente, inmueble y tribunal", ft.Column(controls=[
                fila_campos(campo("Nombre del cliente",form,"nombre_cliente",rf,required=True,multiline=True),
                                 campo("Cédula de identidad",form,"cedula",rf,hint="000-0000000-0",required=True,keyboard_type=KT_NUM,char_filter=RE_CEDULA)),
                ft.Container(height=14),
                campo("Descripción del inmueble",form,"descripcion_inmueble",rf,
                      hint="Parcela No. X, del Distrito Catastral No. X…",multiline=True,required=True),
                ft.Container(height=14),
                campo("Tipo de proceso",form,"tipo_proceso",rf,hint="deslinde / desalojo…",required=True),
                ft.Container(height=14),
                materia_dd,
                ft.Container(height=14),
                tribunal_wrap,
                ft.Container(height=14),
                sala_wrap,
            ])),
            tarjeta("III", "Firma", "Quien suscribe la solicitud", ft.Column(controls=[
                fila_campos(campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)),
                ft.Container(height=14),
                campo("Iniciales",form,"iniciales",rf,expand=False),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(on_generar), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(on_pdf_archivo), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── PLANTILLA 3: REPORTE DE AUDIENCIA ────────
    def build_reporte():
        form = form_reporte
        def rf(): page.update()

        dem_col = ft.Column(spacing=8)

        def build_demandados():
            dem_col.controls.clear()
            for idx, val in enumerate(form["demandados"]):
                def make_row(i=idx, v=val):
                    tf = ft.TextField(
                        value=v, hint_text="Nombre del demandado",
                        border=ft.InputBorder.UNDERLINE, border_color=RULE,
                        focused_border_color=ACCENT, focused_border_width=2, cursor_color=ACCENT,
                        text_style=ft.TextStyle(font_family=FONT_BODY, size=15, color=INK, italic=True),
                        hint_style=ft.TextStyle(font_family=FONT_BODY, italic=True, color=HINT),
                        content_padding=ft.padding.symmetric(vertical=8, horizontal=2), expand=True,
                        on_change=lambda e, i_=i: form["demandados"].__setitem__(i_, e.control.value),
                    )
                    def on_remove(e, i_=i):
                        if len(form["demandados"]) > 1:
                            form["demandados"].pop(i_); build_demandados(); page.update()
                    return ft.Row(controls=[
                        tf,
                        ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_color=ACCENT,
                                      icon_size=18, tooltip="Eliminar", on_click=on_remove),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                dem_col.controls.append(make_row())

            def on_agregar(e):
                form["demandados"].append(""); build_demandados(); page.update()
            dem_col.controls.append(ft.TextButton(
                content=ft.Row(controls=[
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=ACCENT, size=16),
                    ft.Text("Agregar demandado", color=ACCENT_TEXT, size=13, font_family=FONT_BODY),
                ], spacing=6), on_click=on_agregar,
            ))

        build_demandados()

        # Wrappers reactivos a Materia
        asunto_wrap   = ft.Column(spacing=0, expand=True)
        tribunal_wrap = ft.Column(spacing=0, expand=True)
        sala_wrap     = ft.Column(spacing=0, expand=True)

        def rebuild_materia_fields():
            mat = form.get("materia", "")
            asunto_wrap.controls.clear()
            tribunal_wrap.controls.clear()
            sala_wrap.controls.clear()

            if mat == "MATERIA INMOBILIARIA":
                asunto_wrap.controls.append(
                    combobox_campo("Asunto", form, "asunto",
                                   ASUNTOS_INMOBILIARIA, rf, required=True, expand=True,
                                   filter_on_type=False)
                )
                tribunal_wrap.controls.append(
                    combobox_campo("Tribunal", form, "tribunal",
                                   TRIBUNALES_INMOBILIARIA, rf, required=True, expand=True)
                )
                sala_wrap.controls.append(
                    combobox_campo("Sala", form, "sala",
                                   SALAS_INMOBILIARIA, rf, expand=True)
                )
            elif mat == "MATERIA CIVIL":
                asunto_wrap.controls.append(
                    campo("Asunto", form, "asunto", rf, required=True, expand=True)
                )
                tribunal_wrap.controls.append(
                    combobox_campo("Tribunal", form, "tribunal",
                                   TRIBUNALES_CIVIL, rf, required=True, expand=True)
                )
                sala_wrap.controls.append(
                    campo("Sala", form, "sala", rf, expand=True)
                )
            else:
                asunto_wrap.controls.append(
                    campo("Asunto", form, "asunto", rf, required=True, expand=True)
                )
                tribunal_wrap.controls.append(
                    campo("Tribunal", form, "tribunal", rf, multiline=True, required=True, expand=True)
                )

        rebuild_materia_fields()

        materia_dd = materia_selector(page, form, "materia", lambda: (rebuild_materia_fields(), rf()))

        def _validar_reporte():
            reqs = [("tribunal","Tribunal"),("expediente","No. Expediente"),("demandantes","Demandante(s)"),
                    ("parcela","Parcela"),("fecha_audiencia","Fecha de audiencia"),("fallo","Fallo"),
                    ("fecha_proxima","Fecha próxima audiencia"),("abogados","Abogado(s)")]
            faltantes = [n for k, n in reqs if not form.get(k,"").strip()]
            if not any(x.strip() for x in form.get("demandados",[])):
                faltantes.append("Demandado(s)")
            return faltantes

        def on_generar(e):
            faltantes = _validar_reporte()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = generar_reporte_audiencia(form)
                demte = form.get("demandantes","").strip()
                exp   = form.get("expediente","").strip()
                ident = "-".join([x for x in (demte, exp) if x]) or "Reporte"
                _guardar_y_abrir(page, contenido, nombre_archivo("Reporte de Audiencia", ident), snack)
                registrar_en_historial(form)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        def on_pdf_reporte(e):
            faltantes = _validar_reporte()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = pdf_reporte_audiencia(form)
                demte = form.get("demandantes","").strip()
                exp   = form.get("expediente","").strip()
                ident = "-".join([x for x in (demte, exp) if x]) or "Reporte"
                _guardar_pdf(page, contenido, nombre_archivo("Reporte de Audiencia", ident).replace(".docx",".pdf"), snack)
                registrar_en_historial(form)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            *aviso_reporte(form),
            tarjeta("I",   "Expediente", "Tribunal, partes y parcela", ft.Column(controls=[
                campo("No. Expediente", form, "expediente", rf, required=True),
                ft.Container(height=14),
                materia_dd,
                ft.Container(height=14),
                asunto_wrap,
                ft.Container(height=14),
                tribunal_wrap,
                ft.Container(height=14),
                sala_wrap,
                ft.Container(height=14),
                campo("Parcela / Designación", form, "parcela", rf, required=True),
                ft.Container(height=14),
                campo("Agrimensor", form, "agrimensor", rf),
            ])),
            tarjeta("II",  "Partes", "Demandante y demandado(s)", ft.Column(controls=[
                campo("Demandante(s)",form,"demandantes",rf,multiline=True,required=True),
                ft.Container(height=14),
                ft.Row(controls=[ft.Text("DEMANDADO(S)",size=12,weight=ft.FontWeight.W_600,
                                         color=INK_SOFT,font_family=FONT_BODY),
                                 ft.Text(" *", color=ACCENT_TEXT, size=12)], spacing=0),
                dem_col,
            ])),
            tarjeta("III", "Audiencia", "Fecha, fallo y próxima audiencia", ft.Column(controls=[
                fila_campos(campo("Fecha de la audiencia",form,"fecha_audiencia",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Caja No.",form,"caja_no",rf),
                                 campo("Rol",form,"rol",rf)),
                ft.Container(height=14),
                campo("Fallo",form,"fallo",rf,multiline=True,required=True,hint="Ej: Aplazada a los fines de que…"),
                ft.Container(height=14),
                fila_campos(campo("Fecha próxima audiencia",form,"fecha_proxima",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Abogado(s) que compareció",form,"abogados",rf,multiline=True,required=True)),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(on_generar), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(on_pdf_reporte), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── PLANTILLA 4: SOLICITUD DE COBROS ─────────
    def build_cobros():
        form = form_cobros
        def rf(): page.update()

        # Wrappers reactivos a Materia (Asunto, Tribunal y Sala)
        asunto_wrap   = ft.Column(spacing=0, expand=True)
        tribunal_wrap = ft.Column(spacing=0, expand=True)
        sala_wrap     = ft.Column(spacing=0, expand=True)

        def rebuild_materia_fields():
            mat = form.get("materia", "")
            asunto_wrap.controls.clear()
            tribunal_wrap.controls.clear()
            sala_wrap.controls.clear()

            if mat == "MATERIA INMOBILIARIA":
                asunto_wrap.controls.append(
                    combobox_campo("Asunto", form, "asunto",
                                   ASUNTOS_INMOBILIARIA, rf, required=True, expand=True,
                                   filter_on_type=False)
                )
                tribunal_wrap.controls.append(
                    combobox_campo("Tribunal", form, "tribunal",
                                   TRIBUNALES_INMOBILIARIA, rf, required=True, expand=True)
                )
                sala_wrap.controls.append(
                    combobox_campo("Sala", form, "sala",
                                   SALAS_INMOBILIARIA, rf, expand=True)
                )
            elif mat == "MATERIA CIVIL":
                asunto_wrap.controls.append(
                    campo("Asunto", form, "asunto", rf, required=True, expand=True)
                )
                tribunal_wrap.controls.append(
                    combobox_campo("Tribunal", form, "tribunal",
                                   TRIBUNALES_CIVIL, rf, required=True, expand=True)
                )
                sala_wrap.controls.append(
                    campo("Sala", form, "sala", rf, expand=True)
                )
            else:
                asunto_wrap.controls.append(
                    campo("Asunto", form, "asunto", rf, required=True, expand=True)
                )
                tribunal_wrap.controls.append(
                    campo("Tribunal", form, "tribunal", rf,
                          multiline=True, required=True, expand=True)
                )

        rebuild_materia_fields()

        materia_dd = materia_selector(page, form, "materia", lambda: (rebuild_materia_fields(), rf()))

        def _validar_cobros():
            reqs = [("nombre_cliente","Nombre del cliente"),("tipo_proceso","Tipo de proceso"),
                    ("parcela","Parcela"),("municipio","Municipio"),("provincia","Provincia"),
                    ("expediente","No. Expediente"),("cedula","Cédula"),("tribunal","Tribunal"),
                    ("sentencia","No. Sentencia"),("fecha_sentencia","Fecha sentencia"),
                    ("tribunal_original","Tribunal que dictó la sentencia")]
            return [n for k, n in reqs if not form.get(k,"").strip()]

        def on_generar(e):
            faltantes = _validar_cobros()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = generar_solicitud_cobros(form)
                _guardar_y_abrir(page, contenido, nombre_archivo("Solicitud de Cobros", form.get("nombre_cliente","Solicitud")), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        def on_pdf_cobros(e):
            faltantes = _validar_cobros()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = pdf_solicitud_cobros(form)
                _guardar_pdf(page, contenido, nombre_archivo("Solicitud de Cobros", form.get("nombre_cliente","Solicitud")).replace(".docx",".pdf"), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            tarjeta("I",   "Encabezado", "Destinatario y asunto", ft.Column(controls=[
                ft.Row(controls=[campo("Fecha de la carta",form,"fecha_carta",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 asunto_wrap], spacing=24, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(height=14),
                fila_campos(campo("Destinatario (A LA)",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)),
            ])),
            tarjeta("II",  "Cliente", "Datos del cliente e inmueble", ft.Column(controls=[
                campo("Nombre del cliente",form,"nombre_cliente",rf,required=True,multiline=True,
                      hint="Nombre completo tal como aparece en el expediente"),
                ft.Container(height=14),
                materia_dd,
                ft.Container(height=14),
                campo("Tipo de proceso",form,"tipo_proceso",rf,hint="Saneamiento / Deslinde…",required=True),
                ft.Container(height=14),
                campo("Parcela / Designación",form,"parcela",rf,hint="Designación Posesional No. …",required=True),
                ft.Container(height=14),
                fila_campos(campo("Municipio",form,"municipio",rf,required=True),
                                 campo("Provincia",form,"provincia",rf,required=True)),
                ft.Container(height=14),
                fila_campos(campo("No. Expediente",form,"expediente",rf,required=True),
                                 campo("Cédula",form,"cedula",rf,hint="000-0000000-0",required=True,keyboard_type=KT_NUM,char_filter=RE_CEDULA)),
            ])),
            tarjeta("III", "Proceso Legal", "Tribunal, sentencia y tribunal original", ft.Column(controls=[
                tribunal_wrap,
                ft.Container(height=14),
                sala_wrap,
                ft.Container(height=14),
                fila_campos(campo("No. Sentencia",form,"sentencia",rf,required=True),
                                 campo("Fecha sentencia",form,"fecha_sentencia",rf,hint="01 Julio del 2022",required=True)),
                ft.Container(height=14),
                campo("Tribunal que dictó la sentencia",form,"tribunal_original",rf,multiline=True,required=True),
            ])),
            tarjeta("IV",  "Firma", "Quien suscribe la solicitud", ft.Column(controls=[
                fila_campos(campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)),
                ft.Container(height=14),
                campo("Iniciales",form,"iniciales",rf,expand=False),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(on_generar), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(on_pdf_cobros), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── PLANTILLA 5: SOLICITUD DE INSPECCIÓN ─────
    def build_inspeccion():
        form = form_inspeccion
        def rf(): page.update()

        def _validar_inspeccion():
            reqs = [("destinatario","Destinatario"),("asunto","Asunto"),("cuerpo_1","Párrafo principal")]
            return [n for k, n in reqs if not form.get(k,"").strip()]

        def on_generar(e):
            faltantes = _validar_inspeccion()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = generar_solicitud_inspeccion(form)
                _guardar_y_abrir(page, contenido, nombre_archivo("Solicitud de Inspeccion", form.get("destinatario","Solicitud")), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        def on_pdf_inspeccion(e):
            faltantes = _validar_inspeccion()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = pdf_solicitud_inspeccion(form)
                _guardar_pdf(page, contenido, nombre_archivo("Solicitud de Inspeccion", form.get("destinatario","Solicitud")).replace(".docx",".pdf"), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            tarjeta("I",   "Encabezado", "Destinatario, atención y asunto", ft.Column(controls=[
                fila_campos(campo("Fecha de la carta",form,"fecha_carta",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Asunto",form,"asunto",rf,required=True)),
                ft.Container(height=14),
                fila_campos(campo("Destinatario (A)",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)),
                ft.Container(height=14),
                fila_campos(campo("Atención (nombre)",form,"atencion_nombre",rf),
                                 campo("Atención (cargo)",form,"atencion_cargo",rf)),
            ])),
            tarjeta("II",  "Contenido", "Cuerpo de la solicitud", ft.Column(controls=[
                campo("Párrafo 1 — Cuerpo principal",form,"cuerpo_1",rf,multiline=True,required=True,
                      hint="Muy cortésmente, por medio de la presente, solicitamos que…"),
                ft.Container(height=14),
                campo("Párrafo 2 — Adicional (opcional)",form,"cuerpo_2",rf,multiline=True,
                      hint="Es oportuno mencionar que…"),
            ])),
            tarjeta("III", "Firma", "Quien suscribe y copia", ft.Column(controls=[
                fila_campos(campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)),
                ft.Container(height=14),
                fila_campos(campo("Iniciales",form,"iniciales",rf,expand=False),
                                 campo("Cc.",form,"cc",rf,hint="Dirección General.",expand=True)),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(on_generar), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(on_pdf_inspeccion), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── PLANTILLA 6: INFORME DE AUDIENCIA PROVINCIAL ──
    def build_audiencia_provincial():
        form = form_audiencia_provincial
        def rf(): page.update()

        def validar():
            reqs = [
                ("provincia", "Provincia"), ("fecha_desde", "Fecha de traslado"),
                ("tribunal", "Tribunal"), ("tipo_proceso", "Tipo de proceso"),
                ("inmueble", "Inmueble"), ("demandante", "Demandante"),
                ("resultado", "Resultado de la audiencia"),
            ]
            return [nombre for clave, nombre in reqs if not form.get(clave, "").strip()]

        def generar_documento(es_pdf=False):
            faltantes = validar()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = (pdf_informe_audiencia_provincial if es_pdf else generar_informe_audiencia_provincial)(form)
                ident = "-".join(x for x in [form.get("provincia", "").strip(), form.get("expediente", "").strip()] if x) or "Audiencia provincial"
                nombre = nombre_archivo("Informe de Audiencia Provincial", ident)
                if es_pdf:
                    _guardar_pdf(page, contenido, nombre.replace(".docx", ".pdf"), snack)
                else:
                    _guardar_y_abrir(page, contenido, nombre, snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            tarjeta("I", "Traslado", "Provincia y duración de la comisión", ft.Column(controls=[
                fila_campos(
                    campo("Fecha del informe", form, "fecha_informe", rf, hint="DD/MM/AAAA", required=True, keyboard_type=KT_NUM),
                    campo("Provincia", form, "provincia", rf, required=True),
                    campo("Municipio (opcional)", form, "municipio", rf)),
                ft.Container(height=14),
                fila_campos(
                    campo("Fecha de traslado", form, "fecha_desde", rf, hint="DD/MM/AAAA", required=True, keyboard_type=KT_NUM),
                    campo("Fecha de retorno (solo si fueron dos días)", form, "fecha_hasta", rf, hint="DD/MM/AAAA", keyboard_type=KT_NUM)),
            ])),
            tarjeta("II", "Audiencia", "Datos que aparecen en la referencia y el cuerpo", ft.Column(controls=[
                campo("Tribunal", form, "tribunal", rf, required=True, multiline=True),
                ft.Container(height=14),
                combobox_campo("Tipo de proceso", form, "tipo_proceso", TIPOS_AUDIENCIA_PROVINCIAL, rf, required=True, filter_on_type=False),
                ft.Container(height=14),
                campo("Inmueble", form, "inmueble", rf, required=True, multiline=True,
                      hint="Parcela, D. C., resultantes, municipio y provincia…"),
                ft.Container(height=14),
                fila_campos(
                    campo("Demandante / requirente", form, "demandante", rf, required=True, multiline=True),
                    campo("No. Expediente (opcional)", form, "expediente", rf)),
            ])),
            tarjeta("III", "Resultado", "Lo ocurrido en la audiencia", ft.Column(controls=[
                campo("Resultado de la audiencia", form, "resultado", rf, required=True, multiline=True,
                      hint="Ej.: se aplazó para el 7 de diciembre a los fines de…"),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(lambda e: generar_documento()), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(lambda e: generar_documento(True)), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── PLANTILLA 7: CONCLUSIONES DE SANEAMIENTO ──
    def build_conclusiones_saneamiento():
        form = form_conclusiones_saneamiento
        def rf(): page.update()

        def validar():
            reqs = [("expediente", "No. de expediente"), ("reclamante", "Reclamante"), ("inmueble", "Inmueble")]
            return [nombre for clave, nombre in reqs if not form.get(clave, "").strip()]

        def generar_documento(es_pdf=False):
            faltantes = validar()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = (pdf_conclusiones_saneamiento if es_pdf else generar_conclusiones_saneamiento)(form)
                nombre = nombre_archivo("Conclusiones de Saneamiento", form["expediente"])
                if es_pdf:
                    _guardar_pdf(page, contenido, nombre.replace(".docx", ".pdf"), snack)
                else:
                    _guardar_y_abrir(page, contenido, nombre, snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            tarjeta("I", "Datos variables", "Los únicos datos editables del modelo de conclusiones", ft.Column(controls=[
                campo("No. de expediente", form, "expediente", rf, required=True),
                ft.Container(height=14),
                combobox_campo("Reclamante", form, "reclamante", RECLAMANTES_SANEAMIENTO, rf,
                               required=True, filter_on_type=False),
                ft.Container(height=14),
                campo("Inmueble", form, "inmueble", rf, required=True, multiline=True,
                      hint="SANEAMIENTO PARCELA NO. …"),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(lambda e: generar_documento()), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(lambda e: generar_documento(True)), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── HISTORIAL DE EXPEDIENTES ─────────────────
    reporte_vacio = copy.deepcopy(form_reporte)
    hist_estado   = {"filtro": ""}

    def registrar_en_historial(form):
        datos = {k: v for k, v in form.items() if not k.startswith("_")}
        try:
            historial.guardar(historial.desde_reporte(form), datos=datos, id_=form.get("_editando_id"))
        except Exception as ex:
            snack(f"El documento se generó, pero no se guardó en el historial: {ex}", ok=False)
        actualizar_contador()

    def cargar_en_reporte(entrada, numero, editar):
        """Llena el Reporte de Audiencia con un expediente del historial."""
        datos = entrada.get("datos") or {}
        form_reporte.clear()
        form_reporte.update(copy.deepcopy(reporte_vacio))
        form_reporte.update(copy.deepcopy(datos))
        if not datos:   # guardado antes de existir "datos": lo que se pueda recuperar
            form_reporte.update({
                "tribunal": entrada["tribunal"], "expediente": entrada["expediente"],
                "demandantes": entrada["recurrente"],
                "demandados": [x.strip() for x in entrada["recurrido"].split(",") if x.strip()] or [""],
                "asunto": entrada["objeto"], "parcela": entrada["parcela"],
                "agrimensor": entrada["agrimensor"], "fallo": entrada["fallo"],
                "fecha_audiencia": entrada["fecha_audiencia"], "fecha_proxima": entrada["fecha_proxima"],
            })
        if editar:
            form_reporte["_editando_id"] = entrada["id"]
        form_reporte["_origen_no"] = numero
        ir_a("reporte")

    def aviso_reporte(form):
        """Barra sobre el Reporte de Audiencia cuando viene del historial."""
        no = form.get("_origen_no")
        if not no:
            return []

        def nuevo_en_blanco(e):
            form_reporte.clear(); form_reporte.update(copy.deepcopy(reporte_vacio))
            rebuild_form(); page.update()

        if form.get("_editando_id"):
            texto = (f"Editando el No.{no:02d} del historial. Al generar el documento "
                     "se actualiza ese mismo expediente.")
        else:
            texto = (f"Copia del No.{no:02d} del historial. Cambie lo necesario; al generar "
                     "se guarda como un expediente nuevo.")
        return [ft.Container(
            content=ft.ResponsiveRow(controls=[
                ft.Row(controls=[
                    ft.Icon(ft.Icons.EDIT_NOTE if form.get("_editando_id") else ft.Icons.CONTENT_COPY,
                            color=ACCENT_TEXT, size=20),
                    ft.Text(texto, size=13, color=INK, font_family=FONT_BODY, expand=True),
                ], col={"xs": 12, "md": 9}),
                ft.Container(
                    content=ft.TextButton("Empezar uno en blanco", on_click=nuevo_en_blanco,
                                          style=ft.ButtonStyle(color=INK_SOFT)),
                    col={"xs": 12, "md": 3}, alignment=ft.alignment.center_right,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=AVISO_BG, border=ft.border.all(1, RULE), border_radius=4,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
        )]

    def etiqueta_proxima(txt):
        """'Hoy' / 'Mañana' / 'En N días' si la próxima audiencia es esta semana."""
        try:
            dias = (datetime.strptime(txt.strip(), "%d/%m/%Y").date() - date.today()).days
        except ValueError:
            return None
        if dias == 0:
            return "Hoy"
        if dias == 1:
            return "Mañana"
        if 1 < dias <= 7:
            return f"En {dias} días"
        return None

    def build_historial():
        try:
            entradas = historial.listar()
        except Exception as ex:
            return [tarjeta("!", "Sin conexión", "No se pudo leer el historial",
                            ft.Text(str(ex), size=13, color=PDF_COLOR, font_family=FONT_BODY))]

        if not entradas:
            return [tarjeta("I", "Empiece su historial", "Se llena solo al generar reportes",
                ft.Column(controls=[
                    ft.Text("Cada Reporte de Audiencia que genere en Word o PDF aparecerá aquí, "
                            "listo para buscarlo, editarlo o descargarlo con el formato de EXPEDIENTES.",
                            size=14, color=INK_SOFT, font_family=FONT_BODY),
                    ft.Container(height=12),
                    boton_generar(lambda e: ir_a("reporte"), "CREAR REPORTE DE AUDIENCIA"),
                ]))]

        ancho     = page.width or 1280
        compacto  = ancho < 760
        hist_estado["compacto"] = compacto
        numeradas = list(enumerate(entradas, start=1))

        def on_descargar(e):
            try:
                _guardar_y_abrir(page, generar_expedientes(entradas), f"EXPEDIENTES {hoy.year}.docx", snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        def confirmar_borrado(entrada, numero):
            def on_borrar(e):
                page.close(dlg)
                try:
                    historial.borrar(entrada["id"])
                    snack(f"No.{numero:02d} borrado del historial.")
                except Exception as ex:
                    snack(f"No se pudo borrar: {ex}", ok=False)
                actualizar_contador(); rebuild_form(); page.update()

            dlg = ft.AlertDialog(
                modal=True, bgcolor=PAPER,
                title=ft.Text("¿Borrar del historial?", font_family=FONT_DISPLAY, color=INK, size=22),
                content=ft.Text(
                    f"No.{numero:02d} · Exp. {entrada['expediente']}\n{entrada['recurrente']}\n\n"
                    "Esta acción no se puede deshacer.",
                    font_family=FONT_BODY, color=INK_SOFT, size=14,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg),
                                  style=ft.ButtonStyle(color=INK_SOFT)),
                    ft.ElevatedButton("Borrar", on_click=on_borrar, style=ft.ButtonStyle(
                        bgcolor=PDF_COLOR, color=PAPER, shape=ft.RoundedRectangleBorder(radius=2))),
                ],
                actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            page.open(dlg)

        def celda(texto, ancho_=None, expand=False, **kw):
            return ft.Text(texto or "—", size=13, color=INK, font_family=FONT_BODY, width=ancho_,
                           expand=expand, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, **kw)

        def dato(etiqueta, valor):
            return ft.ResponsiveRow(controls=[
                ft.Text(etiqueta.upper(), size=12, weight=ft.FontWeight.W_600, color=INK_SOFT,
                        font_family=FONT_BODY, col={"xs": 12, "sm": 4, "md": 3}),
                ft.Text(valor or "—", size=14, color=INK, font_family=FONT_BODY, selectable=True,
                        col={"xs": 12, "sm": 8, "md": 9}),
            ], spacing=8, run_spacing=0)

        def boton_accion(texto, icono, on_click, color=INK):
            return ft.OutlinedButton(
                content=ft.Row(controls=[ft.Icon(icono, size=16, color=color),
                                         ft.Text(texto, size=13, color=color, font_family=FONT_BODY)],
                               spacing=6, tight=True),
                on_click=on_click,
                style=ft.ButtonStyle(side=ft.BorderSide(1, RULE), shape=ft.RoundedRectangleBorder(radius=4),
                                     padding=ft.padding.symmetric(horizontal=14, vertical=12)),
            )

        def fila_expediente(numero, ent):
            d = ent.get("datos") or {}
            detalle = ft.Container(visible=False, padding=ft.padding.only(left=8, right=8, top=4, bottom=16),
                content=ft.Column(controls=[
                    dato("Tribunal", ent["tribunal"]),
                    dato("Fecha audiencia", ent["fecha_audiencia"]),
                    dato("No. Exp.", ent["expediente"]),
                    dato("Recurrente", ent["recurrente"]),
                    dato("Recurrido", ent["recurrido"]),
                    dato("Agrimensor", ent["agrimensor"]),
                    dato("Objeto", ent["objeto"]),
                    dato("Parcela", ent["parcela"]),
                    dato("Fallo", ent["fallo"]),
                    dato("Próxima audiencia", ent["fecha_proxima"]),
                    *([dato("Abogado(s)", d["abogados"])] if d.get("abogados") else []),
                    *([dato("Caja / Rol", f"{d.get('caja_no') or '—'} / {d.get('rol') or '—'}")]
                      if d.get("caja_no") or d.get("rol") else []),
                    ft.Container(height=6),
                    ft.Row(controls=[
                        boton_accion("Editar", ft.Icons.EDIT_OUTLINED,
                                     lambda e: cargar_en_reporte(ent, numero, editar=True)),
                        boton_accion("Usar como base", ft.Icons.CONTENT_COPY,
                                     lambda e: cargar_en_reporte(ent, numero, editar=False)),
                        boton_accion("Borrar", ft.Icons.DELETE_OUTLINE,
                                     lambda e: confirmar_borrado(ent, numero), color=PDF_COLOR),
                    ], wrap=True, spacing=8, run_spacing=8),
                ], spacing=8))

            prox = etiqueta_proxima(ent["fecha_proxima"])
            prox_ctrl = (ft.Container(content=ft.Text(prox, size=12, weight=ft.FontWeight.W_600,
                                                      color=AVISO_TEXT, font_family=FONT_BODY),
                                      bgcolor=AVISO_BG, border_radius=10,
                                      padding=ft.padding.symmetric(horizontal=8, vertical=2), width=110)
                         if prox else celda(ent["fecha_proxima"], 110))
            flecha = ft.Icon(ft.Icons.EXPAND_MORE, color=INK_SOFT, size=20)

            def alternar(e):
                detalle.visible = not detalle.visible
                flecha.name = ft.Icons.EXPAND_LESS if detalle.visible else ft.Icons.EXPAND_MORE
                page.update()

            numero_txt = ft.Text(f"{numero:02d}", size=18, color=ACCENT_TEXT, font_family=FONT_DISPLAY, width=36)
            if compacto:
                resumen = [numero_txt,
                           ft.Column(controls=[celda(ent["expediente"]), celda(ent["recurrente"], color=INK_SOFT)],
                                     spacing=0, expand=True),
                           prox_ctrl, flecha]
            else:
                resumen = [numero_txt, celda(ent["fecha_audiencia"], 100), celda(ent["expediente"], 150),
                           celda(ent["recurrente"], expand=True), prox_ctrl, flecha]
            return ft.Container(
                content=ft.Column(controls=[
                    ft.Container(content=ft.Row(controls=resumen, spacing=12,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                 padding=ft.padding.symmetric(horizontal=8, vertical=12),
                                 on_click=alternar, ink=True, tooltip="Ver completo"),
                    detalle,
                ], spacing=0),
                border=ft.border.only(bottom=ft.BorderSide(1, PAPER_EDGE)),
            )

        def coincide(ent, q):
            return any(q in (ent[c] or "").lower()
                       for c in ("expediente", "recurrente", "recurrido", "tribunal", "parcela", "objeto"))

        lista = ft.Column(spacing=0)

        def pintar_lista():
            q = hist_estado["filtro"].strip().lower()
            filas = [fila_expediente(n, ent) for n, ent in reversed(numeradas) if not q or coincide(ent, q)]
            lista.controls = filas or [ft.Container(
                content=ft.Text(f'Ningún expediente coincide con "{hist_estado["filtro"]}".',
                                size=14, color=INK_SOFT, font_family=FONT_BODY),
                padding=ft.padding.all(16))]

        def on_buscar(e):
            hist_estado["filtro"] = e.control.value
            pintar_lista(); page.update()

        pintar_lista()
        encabezado = [] if compacto else [ft.Container(
            content=ft.Row(controls=[
                ft.Text("NO.", width=36), ft.Text("AUDIENCIA", width=100), ft.Text("EXP.", width=150),
                ft.Text("RECURRENTE", expand=True), ft.Text("PRÓXIMA", width=110), ft.Container(width=20),
            ], spacing=12),
            padding=ft.padding.symmetric(horizontal=8, vertical=8),
            border=ft.border.only(bottom=ft.BorderSide(1, RULE)),
        )]
        for t in (encabezado[0].content.controls if encabezado else []):
            if isinstance(t, ft.Text):
                t.size, t.weight, t.color, t.font_family = 12, ft.FontWeight.W_600, INK_SOFT, FONT_BODY

        total = len(entradas)
        return [
            ft.ResponsiveRow(controls=[
                ft.TextField(
                    value=hist_estado["filtro"], on_change=on_buscar,
                    hint_text="Buscar por expediente, recurrente, tribunal o parcela",
                    prefix_icon=ft.Icons.SEARCH, border_color=RULE, focused_border_color=ACCENT,
                    cursor_color=ACCENT, bgcolor=PAPER, border_radius=4,
                    text_style=ft.TextStyle(font_family=FONT_BODY, size=14, color=INK),
                    hint_style=ft.TextStyle(font_family=FONT_BODY, size=14, color=HINT),
                    content_padding=ft.padding.symmetric(vertical=10, horizontal=12),
                    col={"xs": 12, "md": 8},
                ),
                ft.Container(content=boton_generar(on_descargar, "DESCARGAR TODO EN WORD"),
                             col={"xs": 12, "md": 4}),
            ], spacing=12, run_spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(f"{total} expediente{'s' if total != 1 else ''} · el más reciente primero · "
                    "toque una fila para verla completa",
                    size=12, color=INK_SOFT, font_family=FONT_BODY),
            ft.Container(content=ft.Column(controls=[*encabezado, lista], spacing=0),
                         bgcolor=PAPER, border=ft.border.all(1, PAPER_EDGE), border_radius=4),
        ]

    # ── JURISPRUDENCIA ───────────────────────────
    MAX_MB_SUBIDA = 20
    # conv_id: la conversación abierta, guardada en la base (cuentas.guardar_conversacion)
    juris_estado  = {"chat": [], "pendiente": None, "subidas": {}, "conv_id": None}

    def _sin_html(texto):
        return re.sub(r"</?b>", "", texto or "")

    def ver_pagina(f):
        """Abre dentro de la app la página del PDF que cita la fuente (sentencia, ley o comentario),
        tal como es, con botones para pasar de página (ver jurisprudencia/visor.py)."""
        estado = {"pagina": f["pagina"], "total": None}
        imagen = ft.Image(src_base64="", visible=False, fit=ft.ImageFit.FIT_WIDTH)
        cargando = ft.Column(controls=[ft.ProgressRing(color=ACCENT), ft.Text(
            "Abriendo la página…", size=13, color=INK_SOFT, font_family=FONT_BODY)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        numero = ft.Text("", size=13, color=INK_SOFT, font_family=FONT_BODY)
        anterior = ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Página anterior", on_click=lambda e: ir(-1))
        siguiente = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Página siguiente", on_click=lambda e: ir(1))

        def dibujar():
            try:
                png, estado["total"] = juris_visor.pagina_png(f["fuente_url"], estado["pagina"])
                imagen.src_base64, imagen.visible, cargando.visible = base64.b64encode(png).decode(), True, False
            except Exception:
                cargando.controls = [ft.Text("No se pudo abrir la página. Use «Abrir el PDF oficial».",
                                             size=13, color=INK_SOFT, font_family=FONT_BODY)]
            numero.value = f"Página {estado['pagina']}" + (f" de {estado['total']}" if estado["total"] else "")
            anterior.disabled = estado["pagina"] <= 1
            siguiente.disabled = bool(estado["total"]) and estado["pagina"] >= estado["total"]
            page.update()

        def ir(paso):
            estado["pagina"] += paso
            imagen.visible, cargando.visible = False, True
            page.update()
            page.run_thread(dibujar)

        dlg = ft.AlertDialog(
            bgcolor=PAPER, inset_padding=ft.padding.all(16),
            title=ft.Text(juris_buscar.referencia(f), font_family=FONT_DISPLAY, color=INK, size=16),
            content=ft.Container(width=820, height=int((page.height or 820) * 0.72), content=ft.Column(
                controls=[cargando, imagen], scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER)),
            actions=[
                ft.Row(controls=[anterior, numero, siguiente], spacing=0, tight=True),
                ft.TextButton("Abrir el PDF oficial", icon=ft.Icons.OPEN_IN_NEW,
                              url=f"{f['fuente_url']}#page={estado['pagina']}", url_target="_blank",
                              style=ft.ButtonStyle(color=INK_SOFT)),
                ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg), style=ft.ButtonStyle(color=INK)),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        page.open(dlg)
        page.run_thread(dibujar)

    def leer_fuente(f):
        """Muestra el texto encontrado de un documento subido por el usuario (no tiene PDF público)."""
        dlg = ft.AlertDialog(
            bgcolor=PAPER,
            title=ft.Text(juris_buscar.referencia(f), font_family=FONT_DISPLAY, color=INK, size=18),
            content=ft.Container(width=760, height=min(520, int((page.height or 820) * 0.6)), content=ft.Column(
                controls=[ft.Text(f["texto"], size=15, color=INK, font_family=FONT_BODY, selectable=True),
                          ft.Text("Es la parte del documento que encontró el buscador; el documento completo "
                                  "está en el PDF oficial.", size=12, italic=True, color=INK_SOFT,
                                  font_family=FONT_BODY)],
                scroll=ft.ScrollMode.AUTO, spacing=12)),
            actions=[
                *([ft.TextButton("Abrir el PDF oficial", icon=ft.Icons.OPEN_IN_NEW,
                                 url=f"{f['fuente_url']}#page={f['pagina']}", url_target="_blank",
                                 style=ft.ButtonStyle(color=INK_SOFT))] if f["fuente_url"] else []),
                ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg), style=ft.ButtonStyle(color=INK)),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        page.open(dlg)

    def tarjeta_fuente(n, f, citada):
        return ft.Container(
            content=ft.Column(controls=[
                ft.Row(controls=[
                    ft.Text(f"[{n}]", size=14, weight=ft.FontWeight.W_600,
                            color=ACCENT_TEXT if citada else INK_SOFT, font_family=FONT_BODY),
                    ft.Text(juris_buscar.referencia(f), size=13, weight=ft.FontWeight.W_600,
                            color=INK, font_family=FONT_BODY, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Text(f"«…{_sin_html(f['extracto'])}…»", size=13, italic=True, color=INK_SOFT,
                        font_family=FONT_BODY, selectable=True),
                ft.Row(controls=[
                    *([ft.TextButton("Ver la página aquí", icon=ft.Icons.ARTICLE_OUTLINED,
                                     on_click=lambda e: ver_pagina(f), style=ft.ButtonStyle(color=INK))]
                      if f["fuente_url"] else
                      [ft.TextButton("Leer aquí", icon=ft.Icons.ARTICLE_OUTLINED, on_click=lambda e: leer_fuente(f),
                                     style=ft.ButtonStyle(color=INK))]),
                    *([ft.TextButton({"ley": "Abrir el texto oficial", "doctrina": "Abrir el libro"}.get(
                                         f["origen"], "Abrir en el Boletín Judicial"),
                                     icon=ft.Icons.OPEN_IN_NEW,
                                     url=f"{f['fuente_url']}#page={f['pagina']}", url_target="_blank",
                                     style=ft.ButtonStyle(color=INK_SOFT))] if f["fuente_url"] else []),
                ], wrap=True, spacing=4),
            ], spacing=4),
            bgcolor=PAPER, border=ft.border.all(1, PAPER_EDGE), border_radius=4,
            padding=ft.padding.all(12),
        )

    def procesar_subida(nombre_original, nombre_servidor):
        ruta = pathlib.Path(DIR_SUBIDAS) / nombre_servidor
        try:
            r = juris_proc.subir_documento(str(ruta), usuario["id"], nombre_original)
            detalle = f" — {r['numero']}" if r["numero"] else ""
            snack(f"«{nombre_original}» agregado al buscador{detalle} ({r['paginas']} pág.).")
        except juris_proc.DocumentoSinTexto as ex:
            snack(f"«{nombre_original}»: {ex} Por ahora solo se leen PDF digitales y Word.", ok=False)
        except Exception:
            snack(f"«{nombre_original}» no se pudo leer. Verifique que sea un PDF o Word válido.", ok=False)
        finally:
            ruta.unlink(missing_ok=True)
        if plantilla["actual"] in ("biblioteca", "escritorio"):   # las dos muestran sus documentos
            rebuild_form()
        page.update()

    def al_elegir_archivos(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        lista = []
        for f in e.files:
            if f.size and f.size > MAX_MB_SUBIDA * 1024 * 1024:
                snack(f"«{f.name}» pesa más de {MAX_MB_SUBIDA} MB.", ok=False); continue
            ext = pathlib.Path(f.name).suffix.lower()
            if ext not in (".pdf", ".docx"):
                snack(f"«{f.name}»: solo se aceptan PDF o Word (.docx).", ok=False); continue
            destino = f"u{usuario['id']}_{uuid.uuid4().hex[:10]}{ext}"
            juris_estado["subidas"][f.name] = destino
            lista.append(ft.FilePickerUploadFile(f.name, upload_url=page.get_upload_url(destino, 600)))
        if lista:
            snack(f"Subiendo {len(lista)} archivo{'s' if len(lista) != 1 else ''}…")
            selector.upload(lista)

    def al_subir(e: ft.FilePickerUploadEvent):
        if e.error:
            snack(f"«{e.file_name}» no se pudo subir: {e.error}", ok=False); return
        if e.progress is not None and e.progress >= 1:
            destino = juris_estado["subidas"].pop(e.file_name, None)
            if destino:
                page.run_thread(procesar_subida, e.file_name, destino)

    selector = ft.FilePicker(on_result=al_elegir_archivos, on_upload=al_subir)
    page.overlay.append(selector)

    def hoja_markdown():
        """Estilos de las respuestas en Markdown (el Asistente). Todos con color propio:
        los que quedan sin definir salen con el color del tema de Flet y no siempre se leen, como las
        tablas y los títulos que a veces pone la IA."""
        def _estilo(size=15, color=INK, **kw):
            return ft.TextStyle(font_family=FONT_BODY, size=size, color=color, **kw)
        return ft.MarkdownStyleSheet(
            p_text_style=_estilo(),
            list_bullet_text_style=_estilo(),
            strong_text_style=_estilo(weight=ft.FontWeight.W_600),
            em_text_style=_estilo(italic=True),
            del_text_style=_estilo(decoration=ft.TextDecoration.LINE_THROUGH),
            a_text_style=_estilo(color=ACCENT_TEXT, decoration=ft.TextDecoration.UNDERLINE),
            code_text_style=_estilo(size=14),
            blockquote_text_style=_estilo(color=INK_SOFT, italic=True),
            h1_text_style=_estilo(size=19, weight=ft.FontWeight.W_700),
            h2_text_style=_estilo(size=17, weight=ft.FontWeight.W_700),
            h3_text_style=_estilo(size=16, weight=ft.FontWeight.W_600),
            h4_text_style=_estilo(weight=ft.FontWeight.W_600),
            h5_text_style=_estilo(weight=ft.FontWeight.W_600),
            h6_text_style=_estilo(weight=ft.FontWeight.W_600),
            table_head_text_style=_estilo(size=14, weight=ft.FontWeight.W_600),
            table_body_text_style=_estilo(size=14),
            table_cells_padding=ft.padding.symmetric(horizontal=12, vertical=8))

    def build_jurisprudencia():
        juris_estado["enviar"] = None
        if not juris_db.configurada():
            return [tarjeta("!", "Falta configurar el buscador", "Base de jurisprudencia",
                            ft.Text("Agregue la variable JURIS_DATABASE_URL (Neon) para activar esta sección.",
                                    size=14, color=INK_SOFT, font_family=FONT_BODY))]

        # La consulta es una conversación: cada mensaje del abogado y cada respuesta del asistente
        # (con las sentencias que usó) quedan en juris_estado["chat"] y se guardan en la base, así el
        # abogado las vuelve a abrir desde la lista de conversaciones (como en ChatGPT).
        chat = juris_estado["chat"]
        texto_md = hoja_markdown()
        # STRETCH: cada mensaje ocupa el ancho, así los del abogado se pueden alinear a la derecha
        mensajes_col = ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, auto_scroll=True,
                                 horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                 height=max(360, int((page.height or 820) - 380)))
        entrada = ft.TextField(
            multiline=True, min_lines=1, max_lines=6, shift_enter=True, expand=True,
            hint_text="Escriba su consulta…", on_submit=lambda e: enviar(entrada.value),
            border_color=RULE, focused_border_color=ACCENT, cursor_color=ACCENT, bgcolor=PAPER, border_radius=22,
            content_padding=ft.padding.symmetric(horizontal=18, vertical=12),
            text_style=ft.TextStyle(font_family=FONT_BODY, size=15, color=INK),
            hint_style=ft.TextStyle(font_family=FONT_BODY, size=14, color=HINT),
        )
        boton_enviar = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color=ON_BOTON, bgcolor=BOTON, icon_size=20,
                                     tooltip="Enviar (Enter)", on_click=lambda e: enviar(entrada.value))
        boton_nueva = ft.TextButton("Nueva conversación", icon=ft.Icons.ADD_COMMENT_OUTLINED,
                                    on_click=lambda e: nueva_conversacion(), style=ft.ButtonStyle(color=INK_SOFT))
        EJEMPLOS = ["¿Qué pasa si se aprobó un deslinde sin citar a los colindantes?",
                    "¿Cuándo caduca el recurso de casación?",
                    "Me despidieron sin pagarme las prestaciones, ¿qué dice la Suprema?"]

        def burbuja_usuario(texto):
            return ft.Column(controls=[ft.Container(
                content=ft.Text(texto, size=15, color=ON_PANEL, font_family=FONT_BODY, selectable=True),
                bgcolor=PANEL_INK, padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border_radius=ft.border_radius.only(top_left=16, top_right=16, bottom_left=16, bottom_right=4),
                margin=ft.margin.only(left=48))], horizontal_alignment=ft.CrossAxisAlignment.END)

        def burbuja_asistente(turno):
            partes = [ft.Markdown(turno["texto"], selectable=True, md_style_sheet=texto_md,
                                  extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)]
            citadas = set(turno.get("citadas", []))
            # si respondió la IA se muestran solo las sentencias que citó; si no, todas las encontradas
            lista = [(n, f) for n, f in enumerate(turno.get("fuentes") or [], start=1)
                     if n in citadas or not turno.get("ia")]
            if lista:
                # "fuentes" porque además de sentencias pueden ser artículos de ley o comentarios
                titulo = (("Ver la fuente citada" if len(lista) == 1 else f"Ver las {len(lista)} fuentes citadas")
                          if citadas else f"Ver las {len(lista)} fuentes encontradas")
                partes.append(ft.ExpansionTile(
                    title=ft.Text(titulo, size=13, weight=ft.FontWeight.W_600, color=INK_SOFT, font_family=FONT_BODY),
                    leading=ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=18, color=ACCENT),
                    controls=[ft.Column(controls=[tarjeta_fuente(n, f, n in citadas) for n, f in lista], spacing=8)],
                    tile_padding=ft.padding.all(0), icon_color=INK_SOFT, collapsed_icon_color=INK_SOFT,
                    shape=ft.RoundedRectangleBorder(radius=4), collapsed_shape=ft.RoundedRectangleBorder(radius=4)))
            def copiar(e):
                # el texto se copia sin las marcas de Markdown (** y >), para pegarlo en un escrito o un correo
                limpio = re.sub(r"\*\*|__|^>\s?", "", turno["texto"], flags=re.M)
                page.set_clipboard(limpio)
                snack("Respuesta copiada.")

            # la respuesta tiene varios bloques y no se puede seleccionar toda de una vez: botón para copiarla
            copiar_btn = [ft.TextButton("Copiar", icon=ft.Icons.CONTENT_COPY, on_click=copiar,
                                        tooltip="Copiar la respuesta completa",
                                        style=ft.ButtonStyle(color=INK_SOFT, padding=ft.padding.symmetric(horizontal=8)))
                          ] if "fuentes" in turno or turno.get("ia") else []
            return ft.Column(controls=[
                ft.Row(controls=[ft.Icon(ft.Icons.GAVEL, size=16, color=ACCENT),
                                 ft.Text("Asistente", size=12, weight=ft.FontWeight.W_600, color=INK_SOFT,
                                         font_family=FONT_BODY, expand=True), *copiar_btn], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(content=ft.Column(controls=partes, spacing=8), bgcolor=PAPER,
                             border=ft.border.all(1, PAPER_EDGE),
                             border_radius=ft.border_radius.only(top_left=4, top_right=16, bottom_left=16, bottom_right=16),
                             padding=ft.padding.symmetric(horizontal=18, vertical=14), margin=ft.margin.only(right=24)),
            ], spacing=4)

        def bienvenida():
            return [
                burbuja_asistente({"texto": "Hola. Soy su asistente de jurisprudencia: busco en las sentencias de la "
                                            "Suprema Corte (Boletín Judicial), en la Ley 108-05 de Registro Inmobiliario "
                                            "y sus reglamentos, y en sus documentos, y le doy mi análisis "
                                            "con las citas para que las verifique.\n\nPuede empezar con una de estas:"}),
                ft.Row(controls=[ft.OutlinedButton(
                    ejemplo, on_click=lambda e, t=ejemplo: enviar(t),
                    style=ft.ButtonStyle(color=INK, side=ft.BorderSide(1, RULE), shape=ft.RoundedRectangleBorder(radius=16),
                                         padding=ft.padding.symmetric(horizontal=14, vertical=10)))
                    for ejemplo in EJEMPLOS], wrap=True, spacing=8, run_spacing=8),
            ]

        def pintar():
            mensajes_col.controls = bienvenida() if not chat else [
                burbuja_usuario(t["texto"]) if t["rol"] == "usuario" else burbuja_asistente(t) for t in chat]
            if juris_estado["pendiente"]:
                mensajes_col.controls.append(ft.Row(controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=ACCENT),
                    ft.Text(juris_estado["pendiente"], size=13, italic=True, color=INK_SOFT, font_family=FONT_BODY),
                ], spacing=10))
            boton_enviar.disabled = bool(juris_estado["pendiente"])
            boton_nueva.disabled = not chat or bool(juris_estado["pendiente"])

        lista_conv = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)
        # con el menú de las salas al lado, la lista cabe desde 1100; si no, se abre con un botón
        lateral = (page.width or 1280) >= 1100

        def conversaciones():
            try:
                return cuentas.listar_conversaciones(usuario["id"])
            except Exception:
                return []

        def fila_conversacion(c, al_abrir=None):
            abierta = c["id"] == juris_estado["conv_id"]

            def abrir(e):
                if al_abrir:
                    al_abrir()
                abrir_conversacion(c["id"])

            return ft.Container(
                content=ft.Row(controls=[
                    ft.Text(c["titulo"], size=13, color=INK, font_family=FONT_BODY, expand=True,
                            weight=ft.FontWeight.W_600 if abierta else None,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=INK_SOFT,
                                  tooltip="Borrar conversación", on_click=lambda e: confirmar_borrar_conv(c)),
                ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=PAPER_EDGE if abierta else None, border_radius=8,
                padding=ft.padding.only(left=10, top=2, bottom=2), on_click=abrir, ink=True)

        def pintar_conversaciones():
            filas = conversaciones()
            lista_conv.controls = [fila_conversacion(c) for c in filas] or [ft.Text(
                "Aquí aparecerán sus conversaciones.", size=12, italic=True, color=INK_SOFT, font_family=FONT_BODY)]

        def guardar_chat():
            """Guarda la conversación abierta en segundo plano y refresca la lista."""
            mensajes = list(chat)

            def tarea():
                try:
                    juris_estado["conv_id"] = cuentas.guardar_conversacion(
                        usuario["id"], juris_estado["conv_id"], mensajes)
                except Exception:
                    return   # si no se puede guardar, el chat sigue funcionando igual
                if lateral:
                    pintar_conversaciones(); page.update()
            page.run_thread(tarea)

        def abrir_conversacion(conv_id):
            if juris_estado["pendiente"]:
                return
            try:
                mensajes = cuentas.abrir_conversacion(usuario["id"], conv_id)
            except Exception as ex:
                snack(f"No se pudo abrir la conversación: {ex}", ok=False); return
            chat[:] = mensajes
            juris_estado["conv_id"] = conv_id
            if lateral:
                pintar_conversaciones()
            pintar(); page.update()

        def confirmar_borrar_conv(c):
            def on_borrar(e):
                page.close(dlg)
                try:
                    cuentas.borrar_conversacion(usuario["id"], c["id"])
                except Exception as ex:
                    snack(f"No se pudo borrar: {ex}", ok=False); return
                if juris_estado["conv_id"] == c["id"]:
                    chat.clear(); juris_estado["conv_id"] = None
                if lateral:
                    pintar_conversaciones()
                pintar(); page.update()
                snack("Conversación borrada.")

            dlg = ft.AlertDialog(
                modal=True, bgcolor=PAPER,
                title=ft.Text("¿Borrar la conversación?", font_family=FONT_DISPLAY, color=INK, size=22),
                content=ft.Text(f"«{c['titulo']}»\n\nEsta acción no se puede deshacer.",
                                font_family=FONT_BODY, color=INK_SOFT, size=14),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg), style=ft.ButtonStyle(color=INK_SOFT)),
                    ft.ElevatedButton("Borrar", on_click=on_borrar, style=ft.ButtonStyle(
                        bgcolor=PDF_COLOR, color=PAPER, shape=ft.RoundedRectangleBorder(radius=2))),
                ],
                actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            page.open(dlg)

        def ver_conversaciones():
            """En el celular: la lista en una ventana."""
            def cerrar():
                page.close(dlg)
            filas = conversaciones()
            dlg = ft.AlertDialog(
                bgcolor=PAPER,
                title=ft.Text("Conversaciones", font_family=FONT_DISPLAY, color=INK, size=22),
                content=ft.Container(width=420, height=420, content=ft.Column(
                    controls=[fila_conversacion(c, cerrar) for c in filas] or [ft.Text(
                        "Todavía no tiene conversaciones guardadas.", size=13, color=INK_SOFT, font_family=FONT_BODY)],
                    spacing=2, scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: cerrar(), style=ft.ButtonStyle(color=INK))])
            page.open(dlg)

        def nueva_conversacion():
            chat.clear()
            juris_estado["conv_id"] = None
            if lateral:
                pintar_conversaciones()
            pintar(); page.update()

        def enviar(texto):
            q = (texto or "").strip()
            if len(q) < 2 or juris_estado["pendiente"]:
                return
            entrada.value = ""
            historial = list(chat)
            chat.append({"rol": "usuario", "texto": q})
            # un saludo o una prueba ("hola") no se busca: siempre saldría "lo más parecido"
            if not juris_ia.parece_consulta(q):
                chat.append({"rol": "asistente", "texto": juris_ia.no_es_consulta(q)})
                pintar(); page.update(); guardar_chat(); return
            # las cuentas de prueba tienen un máximo de preguntas por día
            try:
                cuentas.registrar_pregunta(usuario["id"], usuario.get("plan", "activo"))
            except ValueError as ex:
                chat.append({"rol": "asistente", "texto": str(ex)})
                pintar(); page.update(); return
            except Exception:
                pass   # si no se puede contar, no se le niega la pregunta
            juris_estado["pendiente"] = "Pensando…"
            pintar(); page.update()

            def avance(texto):
                juris_estado["pendiente"] = texto
                pintar(); page.update()

            def tarea():
                turno = {"rol": "asistente", "texto": "", "fuentes": [], "citadas": []}
                try:
                    plan = (juris_ia.preparar_busqueda(q, historial) if juris_ia.disponible()
                            else {"tipo": "nueva", "consulta": q, "busquedas": [q]})
                    anteriores = next((t["fuentes"] for t in reversed(historial) if t.get("fuentes")), [])
                    if plan["tipo"] == "no_juridica":
                        turno["texto"] = juris_ia.no_es_consulta(q)
                    else:
                        if plan["tipo"] == "seguimiento" and anteriores:
                            fuentes = anteriores   # "explíquelo más simple": las mismas sentencias
                        else:
                            avance("Buscando en las sentencias…")
                            fuentes = juris_buscar.buscar(plan["busquedas"] or [plan["consulta"]], usuario["id"],
                                                          limite=juris_ia.MAX_FUENTES, pregunta=plan["consulta"])
                        turno["fuentes"] = fuentes
                        # prestaciones con salario y tiempo: los montos los calcula la app, la IA los explica
                        calculo = juris_prestaciones.calcular(q) or juris_prestaciones.calcular(plan["consulta"])
                        if not fuentes:
                            turno["texto"] = ("No encontré sentencias sobre eso. Pruebe a decirlo con otras palabras, "
                                              "o suba sus propios documentos en «Mis documentos».")
                        elif juris_ia.disponible():
                            avance("Analizando las sentencias…")
                            try:
                                r = juris_ia.responder(q, fuentes, juris_buscar.referencia, historial, calculo)
                                turno.update(texto=r["texto"], citadas=r["citadas"], ia=True)
                            except juris_ia.LimiteAlcanzado:
                                turno["texto"] = ("_Se alcanzó el límite gratis de la IA por ahora; intente en un minuto. "
                                                  "Mientras tanto, abajo están las sentencias encontradas._")
                                if calculo:
                                    turno["texto"] = juris_prestaciones.para_mostrar(calculo) + "\n\n" + turno["texto"]
                        else:
                            turno["texto"] = (f"_La IA no está disponible en el servidor (claves: {juris_ia.estado()}). "
                                              "Abajo están las sentencias encontradas._")
                except Exception as ex:
                    turno["texto"] = f"No pude completar la consulta: {ex}"
                chat.append(turno)
                juris_estado["pendiente"] = None
                pintar(); page.update()
                guardar_chat()
            page.run_thread(tarea)

        juris_estado["enviar"] = enviar   # el Escritorio manda por aquí la pregunta que escribieron allá
        pintar()
        arriba = [boton_nueva] if lateral else [ft.TextButton(
            "Conversaciones", icon=ft.Icons.HISTORY, on_click=lambda e: ver_conversaciones(),
            style=ft.ButtonStyle(color=INK_SOFT)), boton_nueva]
        chat_col = ft.Column(controls=[
            ft.Row(controls=arriba, alignment=ft.MainAxisAlignment.END if lateral
                   else ft.MainAxisAlignment.SPACE_BETWEEN),
            mensajes_col,
            ft.Row(controls=[entrada, boton_enviar], vertical_alignment=ft.CrossAxisAlignment.END, spacing=8),
            ft.Text("Herramienta de apoyo: verifique cada cita en la fuente antes de usarla. "
                    "No escriba datos personales de clientes en la consulta.",
                    size=12, italic=True, color=INK_SOFT, font_family=FONT_BODY),
        ], spacing=12, expand=True)
        consulta = chat_col
        if lateral:
            pintar_conversaciones()
            consulta = ft.Row(controls=[
                ft.Container(width=240, height=mensajes_col.height + 120, content=ft.Column(controls=[
                    ft.Text("Conversaciones", size=13, weight=ft.FontWeight.W_600, color=INK_SOFT,
                            font_family=FONT_BODY),
                    lista_conv], spacing=8),
                    padding=ft.padding.only(right=12), border=ft.border.only(right=ft.BorderSide(1, PAPER_EDGE))),
                chat_col], vertical_alignment=ft.CrossAxisAlignment.START, spacing=16)
        return [tarjeta("I", "Consulta", "Converse con su asistente; cada respuesta cita sus fuentes", consulta)]

    # ── BIBLIOTECA ───────────────────────────────
    def subir_documentos():
        selector.pick_files(allow_multiple=True, allowed_extensions=["pdf", "docx"])

    def mis_documentos():
        if not juris_db.configurada():
            return None
        try:
            return juris_proc.mis_documentos(usuario["id"])
        except Exception:
            return None

    def lista_documentos():
        docs = mis_documentos()
        if docs is None:
            return [ft.Text("No se pudieron leer sus documentos. Intente de nuevo en un momento.",
                            size=13, color=PDF_COLOR, font_family=FONT_BODY)]
        if not docs:
            return [ft.Text("Todavía no ha subido documentos. Puede subir sentencias, resoluciones o escritos "
                            "en PDF digital o Word; solo usted los verá.",
                            size=13, color=INK_SOFT, font_family=FONT_BODY)]

        def borrar(d):
            juris_proc.borrar_documento(d["id"], usuario["id"])
            snack(f"«{d['titulo']}» quitado del buscador.")
            rebuild_form(); page.update()

        return [ft.Container(
            content=ft.Row(controls=[
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=INK_SOFT, size=18),
                ft.Column(controls=[
                    ft.Text(d["titulo"], size=14, color=INK, font_family=FONT_BODY,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(" · ".join(x for x in (d["numero"], d["sala"], d["materia"]) if x) or "Sin ficha",
                            size=12, color=INK_SOFT, font_family=FONT_BODY,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0, expand=True),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=PDF_COLOR, tooltip="Quitar del buscador",
                              on_click=lambda e, d=d: borrar(d)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border=ft.border.only(bottom=ft.BorderSide(1, PAPER_EDGE)),
            padding=ft.padding.symmetric(vertical=6, horizontal=4),
        ) for d in docs]

    def build_biblioteca():
        estantes = [
            (ft.Icons.GAVEL, "Sentencias de la Suprema Corte de Justicia",
             "Del Boletín Judicial; las nuevas se agregan solas cada mes."),
            (ft.Icons.MENU_BOOK_OUTLINED, "Leyes y reglamentos",
             "La Ley 108-05 de Registro Inmobiliario y sus reglamentos, artículo por artículo."),
            (ft.Icons.FOLDER_SHARED_OUTLINED, "Sus documentos",
             "Lo que usted sube entra al mismo buscador; nadie más lo ve."),
        ]
        return [
            tarjeta("I", "Qué hay en su biblioteca", "Su asistente busca aquí cuando le pregunta", ft.Column(controls=[
                *[ft.Row(controls=[
                    ft.Icon(icono, color=ACCENT_TEXT, size=22),
                    ft.Column(controls=[
                        ft.Text(titulo, size=15, weight=ft.FontWeight.W_600, color=INK, font_family=FONT_BODY),
                        ft.Text(detalle, size=13, color=INK_SOFT, font_family=FONT_BODY),
                    ], spacing=2, expand=True),
                ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START) for icono, titulo, detalle in estantes],
                ft.TextButton("Preguntarle al asistente", icon=ft.Icons.ARROW_FORWARD,
                              on_click=lambda e: ir_a("jurisprudencia"), style=ft.ButtonStyle(color=ACCENT_TEXT)),
            ], spacing=14)),
            tarjeta("II", "Mis documentos", "Solo usted los ve; entran al mismo buscador", ft.Column(controls=[
                ft.OutlinedButton("Subir PDF o Word", icon=ft.Icons.UPLOAD_FILE, on_click=lambda e: subir_documentos(),
                                  style=ft.ButtonStyle(color=INK, icon_color=INK, side=ft.BorderSide(1, INK_SOFT),
                                                       shape=ft.RoundedRectangleBorder(radius=4),
                                                       padding=ft.padding.symmetric(horizontal=16, vertical=14))),
                ft.Column(controls=lista_documentos(), spacing=0),
            ], spacing=12)),
        ]

    # ── USUARIOS (solo administradores) ──────────
    def abrir_usuarios():
        lista = ft.Column(spacing=0, tight=True)

        def fila(u):
            vence = (f"  ·  prueba hasta {time.strftime('%d/%m/%Y', time.localtime(u['prueba_hasta']))}"
                     if u.get("plan") == "prueba" and u.get("prueba_hasta") else "")

            def plan_cambiado(e, uid=u["id"]):
                try:
                    cuentas.cambiar_plan(uid, e.control.value)
                except ValueError as ex:
                    snack(str(ex), ok=False); return
                pintar(); page.update()

            def correo_cambiado(e, uid=u["id"], antes=u.get("email") or ""):
                nuevo = (e.control.value or "").strip().lower()
                if nuevo == antes:
                    return
                try:
                    cuentas.asignar_email(uid, nuevo)
                except ValueError as ex:
                    snack(str(ex), ok=False); return
                snack("Correo guardado: con él puede entrar con Google a esta misma cuenta." if nuevo else "Correo quitado.")
                pintar(); page.update()

            def plantillas_cambiadas(e, uid=u["id"]):
                cuentas.cambiar_plantillas(uid, e.control.value)
                snack("Listo: se aplica cuando esa persona vuelva a entrar.")

            texto = ft.TextStyle(font_family=FONT_BODY, size=13, color=INK)
            return ft.Container(
                padding=ft.padding.symmetric(vertical=10), border=ft.border.only(bottom=ft.BorderSide(1, RULE)),
                content=ft.Column(controls=[
                    ft.Text(spans=[
                        ft.TextSpan(u["nombre"] or u["usuario"], ft.TextStyle(weight=ft.FontWeight.W_600)),
                        ft.TextSpan(f"  ·  {u['usuario']}{'  ·  admin' if u['es_admin'] else ''}{vence}",
                                    ft.TextStyle(color=INK_SOFT)),
                    ], size=13, color=INK, font_family=FONT_BODY),
                    ft.Row(controls=[
                        ft.Dropdown(value=u.get("plan") or "activo",
                                    options=[ft.dropdown.Option(p) for p in cuentas.PLANES],
                                    width=120, dense=True, tooltip="Plan", on_change=plan_cambiado,
                                    text_style=texto, bgcolor=PAPER, border_color=RULE, focused_border_color=ACCENT,
                                    disabled=u["id"] == usuario["id"]),
                        ft.TextField(value=u.get("email") or "", hint_text="correo de Google", dense=True, expand=True,
                                     text_style=texto, border_color=RULE, focused_border_color=ACCENT,
                                     cursor_color=ACCENT, on_submit=correo_cambiado, on_blur=correo_cambiado),
                        ft.Switch(value=bool(u["activo"]), active_color=ACCENT, disabled=u["id"] == usuario["id"],
                                  tooltip="Activo",
                                  on_change=lambda e, uid=u["id"]: cuentas.cambiar_activo(uid, e.control.value)),
                    ], spacing=8),
                    ft.Checkbox(label="Ve las plantillas de solicitudes", value=bool(u.get("plantillas")),
                                active_color=ACCENT, label_style=texto, on_change=plantillas_cambiadas),
                ], spacing=6))

        def pintar():
            lista.controls = [fila(u) for u in cuentas.listar_usuarios()]

        def campo_dialogo(etiqueta, clave=False):
            return ft.TextField(label=etiqueta, password=clave, can_reveal_password=clave, dense=True,
                                border_color=RULE, focused_border_color=ACCENT, cursor_color=ACCENT)

        tf_usuario, tf_nombre, tf_clave = campo_dialogo("Usuario"), campo_dialogo("Nombre"), campo_dialogo("Contraseña", True)
        tf_correo = campo_dialogo("Correo de Google (opcional)")
        estilo_casilla = ft.TextStyle(font_family=FONT_BODY, size=14, color=INK)
        cb_admin = ft.Checkbox(label="Administrador", value=False, active_color=ACCENT, label_style=estilo_casilla)
        cb_plantillas = ft.Checkbox(label="Ve las plantillas de solicitudes", value=False, active_color=ACCENT,
                                    label_style=estilo_casilla)

        def crear(e):
            try:
                cuentas.crear_usuario(tf_usuario.value or "", tf_clave.value or "", tf_nombre.value or "", cb_admin.value,
                                      email=tf_correo.value or "", plantillas=cb_plantillas.value)
            except ValueError as ex:
                snack(str(ex), ok=False); return
            snack(f"Usuario «{tf_usuario.value.strip().lower()}» creado.")
            tf_usuario.value = tf_nombre.value = tf_clave.value = tf_correo.value = ""
            cb_admin.value = cb_plantillas.value = False
            pintar(); page.update()

        pintar()
        dlg = ft.AlertDialog(
            modal=True, bgcolor=PAPER,
            title=ft.Text("Usuarios", font_family=FONT_DISPLAY, color=INK, size=24),
            content=ft.Column(controls=[
                lista, ft.Divider(color=RULE),
                ft.Text("NUEVO USUARIO", size=12, weight=ft.FontWeight.W_600, color=INK_SOFT, font_family=FONT_BODY),
                tf_usuario, tf_nombre, tf_clave, tf_correo, cb_admin, cb_plantillas,
            ], tight=True, scroll=ft.ScrollMode.AUTO, width=420, spacing=8),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg), style=ft.ButtonStyle(color=INK_SOFT)),
                     ft.ElevatedButton("Crear usuario", on_click=crear, style=ft.ButtonStyle(
                         bgcolor=BOTON, color=ON_BOTON, shape=ft.RoundedRectangleBorder(radius=4)))],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        page.open(dlg)

    # ── NAVEGACIÓN ───────────────────────────────
    # Las plantillas de solicitudes, dentro de la sala Redacción
    KEYS = ["informe", "archivo", "reporte", "cobros", "inspeccion", "audiencia_provincial", "conclusiones_saneamiento"]
    PESTANAS = {
        "informe":    "Informe Técnico", "archivo": "Archivo", "reporte": "Reporte de Audiencia",
        "cobros":     "Cobros", "inspeccion": "Inspección", "audiencia_provincial": "Provincial",
        "conclusiones_saneamiento": "Conclusiones",
    }
    SUB_PESTANAS = {
        "informe":    "Catastro · Investigación Parcelaria",
        "archivo":    "Archivo · Expediente",
        "reporte":    "Audiencia · Fallo y próxima fecha",
        "cobros":     "Cobros · Verificación de pago",
        "inspeccion": "Inspección · Cuerpo libre",
        "audiencia_provincial":     "Audiencia · Traslado a provincia",
        "conclusiones_saneamiento": "Saneamiento · Modelo fijo",
        "historial":  "Expedientes generados",
    }

    # Las salas del despacho, en el menú de la izquierda (en el celular, en un cajón). Cada sala abre
    # una sección; las que todavía no existen salen con «Pronto».
    SALAS = [
        ("escritorio",   "Escritorio",   ft.Icons.HOME_OUTLINED),
        ("asistente",    "Asistente",    ft.Icons.CHAT_BUBBLE_OUTLINE),
        ("biblioteca",   "Biblioteca",   ft.Icons.MENU_BOOK_OUTLINED),
        ("expedientes",  "Expedientes",  ft.Icons.FOLDER_OUTLINED),
        ("redaccion",    "Redacción",    ft.Icons.EDIT_NOTE),
        ("agenda",       "Agenda",       ft.Icons.CALENDAR_MONTH_OUTLINED),
    ]
    PRONTO  = {"expedientes", "agenda"} | (set() if con_plantillas else {"redaccion"})
    PRIMERA = {"asistente": "jurisprudencia", "redaccion": KEYS[0]}   # la sección con que abre cada sala

    def sala_de(key):
        if key in KEYS or key == "historial":
            return "redaccion"
        return "asistente" if key == "jurisprudencia" else key

    def ir_a(key):
        if sala_de(key) in PRONTO:
            key = "escritorio"
        plantilla["actual"] = key
        rebuild_form(); pintar_menu(); page.update()

    menu_salas = ft.Column(spacing=3)   # en la barra lateral
    menu_panel = ft.Column(spacing=3)   # las mismas salas, en el panel que se abre en el celular

    def boton_sala(clave, nombre, icono, en_panel):
        activa = sala_de(plantilla["actual"]) == clave
        pronto = clave in PRONTO
        color = BAR_BTN_TEXT if activa else NAV_SUB if pronto else NAV_TEXT

        def abrir(e):
            if en_panel:
                menu_movil.visible = False
            ir_a(PRIMERA.get(clave, clave))

        return ft.Container(
            content=ft.Row(controls=[
                ft.Icon(icono, size=20, color=color),
                ft.Text(nombre, size=16, color=color, font_family=FONT_BODY, expand=True,
                        weight=ft.FontWeight.W_600 if activa else None),
                *([ft.Text("Pronto", size=12, italic=True, color=NAV_SUB, font_family=FONT_BODY)] if pronto else []),
            ], spacing=12),
            bgcolor=BAR_BTN if activa else None, border_radius=9,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_click=None if pronto else abrir, ink=not pronto,
            tooltip="Todavía no está lista: viene pronto." if pronto else None,
        )

    def pintar_menu():
        menu_salas.controls = [boton_sala(*s, en_panel=False) for s in SALAS]
        menu_panel.controls = [boton_sala(*s, en_panel=True) for s in SALAS]

    def logo():
        return ft.Row(controls=[
            ft.Container(content=ft.Icon(ft.Icons.BALANCE, size=22, color=BAR_BTN_TEXT), width=40, height=40,
                         bgcolor=BAR_BTN, border_radius=9, alignment=ft.alignment.center),
            ft.Text(NOMBRE_APP, size=25, weight=ft.FontWeight.W_600, color=ON_PANEL, font_family=FONT_DISPLAY),
        ], spacing=12)

    # la prueba gratis: los días que quedan y las preguntas de hoy (se lee una vez al entrar)
    en_prueba = usuario.get("plan") == "prueba"
    dias_prueba = max(0, int(((usuario.get("prueba_hasta") or 0) - time.time() + 86399) // 86400))
    try:
        preguntas_hoy = cuentas.preguntas_de_hoy(usuario["id"]) if en_prueba else 0
    except Exception:
        preguntas_hoy = 0

    def caja_plan():
        if not en_prueba:
            return ft.Container(visible=False)
        tope = cuentas.PREGUNTAS_PRUEBA
        return ft.Container(
            content=ft.Column(controls=[
                ft.Text("PRUEBA GRATIS", size=12, weight=ft.FontWeight.W_600, color=NAV_SUB, font_family=FONT_BODY),
                ft.Text(f"Quedan {dias_prueba} día{'s' if dias_prueba != 1 else ''}", size=19, color=ON_PANEL,
                        font_family=FONT_DISPLAY),
                ft.ProgressBar(value=min(1, preguntas_hoy / tope) if tope else 0, color=NAV_LINEA, bar_height=6,
                               bgcolor=ft.Colors.with_opacity(0.18, ON_PANEL), border_radius=3),
                ft.Text(f"{preguntas_hoy} de {tope} consultas hoy", size=14, color=NAV_SUB, font_family=FONT_BODY),
            ], spacing=8),
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ON_PANEL))),
            padding=ft.padding.only(left=10, right=10, top=16),
        )

    # ── MI CUENTA → APARIENCIA ───────────────────
    def abrir_apariencia():
        def elegir(clave):
            page.close(dlg)
            if clave == (usuario.get("tema") or temas.MARCA):
                return
            try:
                cuentas.cambiar_tema(usuario["id"], clave)
            except Exception:
                snack("No se pudo guardar el tema. Intente de nuevo.", ok=False); return
            usuario["tema"] = clave
            # se vuelve a armar la pantalla con los colores nuevos, en la misma sección; antes se
            # espera a que el diálogo termine de cerrarse (si no, el cambio de tema lo deja pegado)
            time.sleep(0.4)
            page.controls.clear(); page.overlay.clear(); page.on_resized = None
            app_principal(page, usuario, salir, seccion=plantilla["actual"])
            page.update()

        def muestra(clave, t):
            """Tarjeta con la barra, una hoja y el botón del tema, como se verá."""
            elegido = clave == tema_actual
            return ft.Container(
                content=ft.Column(controls=[
                    ft.Container(
                        content=ft.Column(controls=[
                            ft.Container(height=14, bgcolor=t["PANEL_INK"],
                                         border=ft.border.only(bottom=ft.BorderSide(2, t["NAV_LINEA"]))),
                            ft.Container(
                                content=ft.Column(controls=[
                                    ft.Text("Sentencia", size=14, color=t["INK"], font_family=FONT_DISPLAY),
                                    ft.Text("Texto de la consulta", size=11, color=t["INK_SOFT"], font_family=FONT_BODY),
                                    ft.Container(content=ft.Text("Botón", size=10, color=t["ON_BOTON"],
                                                                 font_family=FONT_BODY),
                                                 bgcolor=t["BOTON"], border_radius=3,
                                                 padding=ft.padding.symmetric(horizontal=8, vertical=2)),
                                ], spacing=4, tight=True),
                                bgcolor=t["PAPER"], border=ft.border.all(1, t["PAPER_EDGE"]),
                                margin=ft.margin.all(8), padding=ft.padding.all(8),
                            ),
                        ], spacing=0, tight=True),
                        bgcolor=t["SURFACE"], border_radius=4, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    ),
                    ft.Row(controls=[
                        ft.Text(t["nombre"], size=14, weight=ft.FontWeight.W_600, color=INK,
                                font_family=FONT_BODY, expand=True),
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ACCENT, size=18, visible=elegido),
                    ], spacing=4),
                    ft.Text(t["descripcion"], size=12, color=INK_SOFT, font_family=FONT_BODY),
                ], spacing=6, tight=True),
                col={"xs": 12, "sm": 6}, padding=ft.padding.all(10), border_radius=6,
                border=ft.border.all(2 if elegido else 1, ACCENT if elegido else RULE),
                on_click=lambda e, c=clave: elegir(c), ink=True,
            )

        tema_actual = usuario.get("tema") or temas.MARCA
        dlg = ft.AlertDialog(
            modal=True, bgcolor=PAPER,
            title=ft.Text("Apariencia", font_family=FONT_DISPLAY, color=INK, size=24),
            content=ft.Column(controls=[
                ft.Text("Elija los colores del despacho. Se guardan en su cuenta y se ven igual en todos sus equipos.",
                        size=14, color=INK_SOFT, font_family=FONT_BODY),
                ft.ResponsiveRow(controls=[muestra(c, t) for c, t in temas.TEMAS.items()],
                                 spacing=12, run_spacing=12),
            ], tight=True, scroll=ft.ScrollMode.AUTO, width=520, spacing=14),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg), style=ft.ButtonStyle(color=INK_SOFT))],
        )
        page.open(dlg)

    def opciones_cuenta():
        return [
            ft.PopupMenuItem(text=f'{usuario["nombre"]} ({usuario["usuario"]})', disabled=True),
            ft.PopupMenuItem(text="Apariencia", icon=ft.Icons.PALETTE_OUTLINED, on_click=lambda e: abrir_apariencia()),
            *([ft.PopupMenuItem(text="Usuarios", icon=ft.Icons.GROUP, on_click=lambda e: abrir_usuarios())]
              if usuario["es_admin"] else []),
            ft.PopupMenuItem(text="Cerrar sesión", icon=ft.Icons.LOGOUT, on_click=lambda e: salir()),
        ]

    iniciales = "".join(p[0] for p in usuario["nombre"].split()[:2]).upper() or "?"
    cuenta_lateral = ft.PopupMenuButton(
        bgcolor=PAPER, tooltip="Mi cuenta", items=opciones_cuenta(),
        content=ft.Row(controls=[
            ft.Container(content=ft.Text(iniciales, size=14, weight=ft.FontWeight.W_600, color=BAR_BTN_TEXT,
                                         font_family=FONT_BODY),
                         width=38, height=38, border_radius=19, bgcolor=BAR_BTN, alignment=ft.alignment.center),
            ft.Column(controls=[
                ft.Text(usuario["nombre"], size=15, weight=ft.FontWeight.W_600, color=ON_PANEL, font_family=FONT_BODY,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=160),
                ft.Text("Mi cuenta · Apariencia", size=13, color=NAV_SUB, font_family=FONT_BODY),
            ], spacing=0, tight=True),
        ], spacing=10, tight=True),
    )
    cuenta_movil = ft.PopupMenuButton(icon=ft.Icons.ACCOUNT_CIRCLE, icon_color=ON_PANEL, tooltip=usuario["nombre"],
                                      bgcolor=PAPER, items=opciones_cuenta())

    # ── REDACCIÓN: las plantillas y el historial ──
    conteo = {"n": 0, "ctrl": None}   # expedientes guardados, en la pestaña «Historial»

    def pestanas_redaccion():
        def pestana(key, texto):
            activa = plantilla["actual"] == key
            extra = []
            if key == "historial":
                conteo["ctrl"] = ft.Container(
                    content=ft.Text(str(conteo["n"]), size=12, weight=ft.FontWeight.W_600, color=ON_PANEL,
                                    font_family=FONT_BODY),
                    bgcolor=PANEL_INK, border_radius=10, padding=ft.padding.symmetric(horizontal=7, vertical=1),
                    visible=conteo["n"] > 0)
                extra = [conteo["ctrl"]]
            return ft.Container(
                content=ft.Row(controls=[
                    ft.Text(texto, size=14, color=ON_BOTON if activa else INK, font_family=FONT_BODY,
                            weight=ft.FontWeight.W_600 if activa else None),
                    *extra,
                ], spacing=6, tight=True),
                bgcolor=BOTON if activa else PAPER, border=ft.border.all(1, BOTON if activa else RULE),
                border_radius=20, padding=ft.padding.symmetric(horizontal=14, vertical=8),
                on_click=lambda e: ir_a(key), ink=True, tooltip=SUB_PESTANAS[key],
            )
        return ft.Row(controls=[*[pestana(k, PESTANAS[k]) for k in KEYS], pestana("historial", "Historial")],
                      wrap=True, spacing=8, run_spacing=8)

    def actualizar_contador():
        def tarea():
            try:
                n = historial.contar()
            except Exception:
                return
            conteo["n"] = n
            if conteo["ctrl"]:
                conteo["ctrl"].content.value, conteo["ctrl"].visible = str(n), n > 0
            page.update()
        page.run_thread(tarea)

    # ── ESCRITORIO (inicio) ──────────────────────
    def preguntar(q):
        """Lo que escriben en el Escritorio abre una conversación nueva con el asistente."""
        q = (q or "").strip()
        if len(q) < 2:
            return
        nueva_conversacion()
        if juris_estado.get("enviar"):
            juris_estado["enviar"](q)

    def nueva_conversacion():
        juris_estado["chat"].clear()
        juris_estado["conv_id"] = None
        ir_a("jurisprudencia")

    def abrir_conversacion_guardada(conv_id):
        try:
            mensajes = cuentas.abrir_conversacion(usuario["id"], conv_id)
        except Exception as ex:
            snack(f"No se pudo abrir la conversación: {ex}", ok=False); return
        juris_estado["chat"][:] = mensajes
        juris_estado["conv_id"] = conv_id
        ir_a("jurisprudencia")

    def cuando(ts):
        """'hoy, 8:40 a. m.', 'ayer' o '7 nov'."""
        momento = datetime.fromtimestamp(ts, ZONA_RD)
        dias = (datetime.now(ZONA_RD).date() - momento.date()).days
        if dias == 0:
            return (f"hoy, {momento.hour % 12 or 12}:{momento.minute:02d} "
                    f"{'a. m.' if momento.hour < 12 else 'p. m.'}")
        return "ayer" if dias == 1 else f"{momento.day} {MESES_ANIO[momento.month - 1][:3]}"

    def seccion_escritorio(titulo, contenido, accion=None):
        """Una tarjeta del Escritorio: título, un enlace («Ver todas») y su contenido."""
        return ft.Container(
            content=ft.Column(controls=[
                ft.Row(controls=[
                    ft.Text(titulo, size=22, weight=ft.FontWeight.W_600, color=INK, font_family=FONT_DISPLAY,
                            expand=True),
                    *([ft.TextButton(accion[0], on_click=accion[1], style=ft.ButtonStyle(color=ACCENT_TEXT))]
                      if accion else []),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                *contenido,
            ], spacing=6),
            bgcolor=PAPER, border=ft.border.all(1, PAPER_EDGE), border_radius=12, padding=ft.padding.all(22),
            col={"xs": 12, "lg": 6},
        )

    def renglon(titulo, detalle, al_tocar=None, etiqueta=None, ultimo=False):
        return ft.Container(
            content=ft.Row(controls=[
                ft.Column(controls=[
                    ft.Text(titulo, size=16, weight=ft.FontWeight.W_600, color=INK, font_family=FONT_BODY,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(detalle, size=14, color=INK_SOFT, font_family=FONT_BODY,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),
                *([ft.Container(content=ft.Text(etiqueta, size=13, weight=ft.FontWeight.W_600, color=AVISO_TEXT,
                                                font_family=FONT_BODY),
                                bgcolor=AVISO_BG, border_radius=12,
                                padding=ft.padding.symmetric(horizontal=11, vertical=4))] if etiqueta else []),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(vertical=11),
            border=None if ultimo else ft.border.only(bottom=ft.BorderSide(1, PAPER_EDGE)),
            on_click=al_tocar, ink=bool(al_tocar),
        )

    def build_escritorio():
        ahora = datetime.now(ZONA_RD)
        saludo = "Buenos días" if ahora.hour < 12 else "Buenas tardes" if ahora.hour < 19 else "Buenas noches"
        nombre = (usuario["nombre"].split() or [""])[0].capitalize()
        fecha = f"{DIAS_SEMANA[ahora.weekday()]}, {ahora.day} de {MESES_ANIO[ahora.month - 1]}".upper()
        angosto = (page.width or 1280) < 760

        # audiencias de esta semana: las del historial de reportes (solo en las cuentas con plantillas)
        audiencias = []
        if con_plantillas:
            try:
                for ent in historial.listar():
                    etiqueta = etiqueta_proxima(ent["fecha_proxima"] or "")
                    if etiqueta:
                        audiencias.append((ent, etiqueta))
            except Exception:
                pass
            audiencias.sort(key=lambda a: datetime.strptime(a[0]["fecha_proxima"].strip(), "%d/%m/%Y"))
        if con_plantillas:
            n = len(audiencias)
            resumen = f"{n} audiencia{'s' if n != 1 else ''} esta semana" if n else "Sin audiencias esta semana"
        elif en_prueba:
            resumen = f"Prueba gratis · quedan {dias_prueba} día{'s' if dias_prueba != 1 else ''}"
        else:
            resumen = ""

        cabecera = ft.Container(
            content=ft.ResponsiveRow(controls=[
                ft.Column(controls=[
                    ft.Text(fecha, size=13, weight=ft.FontWeight.W_600, color=HINT, font_family=FONT_BODY),
                    ft.Text(f"{saludo}, {nombre}." if nombre else f"{saludo}.", size=32 if angosto else 40,
                            weight=ft.FontWeight.W_500, color=INK, font_family=FONT_DISPLAY),
                ], spacing=6, col={"xs": 12, "md": 8}),
                ft.Container(content=ft.Text(resumen, size=15, color=INK_SOFT, font_family=FONT_BODY),
                             col={"xs": 12, "md": 4},
                             alignment=ft.alignment.center_left if angosto else ft.alignment.bottom_right),
            ], vertical_alignment=ft.CrossAxisAlignment.END),
            padding=ft.padding.only(bottom=20), border=ft.border.only(bottom=ft.BorderSide(1, INK)),
        )

        pregunta = ft.TextField(
            hint_text="Una duda, un número de sentencia, un artículo…", expand=True,
            on_submit=lambda e: preguntar(pregunta.value), bgcolor=SURFACE, border_color=RULE,
            focused_border_color=ACCENT, cursor_color=ACCENT, border_radius=10,
            text_style=ft.TextStyle(font_family=FONT_BODY, size=17, color=INK),
            hint_style=ft.TextStyle(font_family=FONT_BODY, size=16, color=HINT),
            content_padding=ft.padding.symmetric(horizontal=18, vertical=16),
        )
        # en el celular solo la flecha, para que la pregunta tenga espacio
        boton = ft.IconButton(
            ft.Icons.ARROW_FORWARD, icon_color=ON_BOTON, bgcolor=BOTON, tooltip="Preguntar", icon_size=22,
            on_click=lambda e: preguntar(pregunta.value)) if angosto else ft.ElevatedButton(
            "Preguntar", icon=ft.Icons.ARROW_FORWARD, on_click=lambda e: preguntar(pregunta.value),
            style=ft.ButtonStyle(bgcolor=BOTON, color=ON_BOTON, icon_color=ON_BOTON,
                                 shape=ft.RoundedRectangleBorder(radius=10),
                                 padding=ft.padding.symmetric(horizontal=22, vertical=20)))
        def escribir_prestaciones(e=None):
            # deja una pregunta de ejemplo para cambiarle los datos; los montos los saca el asistente
            # con las reglas fijas de jurisprudencia/prestaciones.py
            pregunta.value = ("Calcule las prestaciones de un despido sin causa: salario de RD$50,000 al mes, "
                              "3 años y 4 meses trabajados.")
            pregunta.focus()

        atajos = [
            ("Plazo para recurrir en casación", lambda e: preguntar("¿Cuál es el plazo para recurrir en casación?")),
            ("Calcular prestaciones", escribir_prestaciones),
            ("Subir un documento", lambda e: subir_documentos()),
            *([("Redactar una solicitud", lambda e: ir_a(KEYS[0]))] if con_plantillas else []),
        ]
        tarjeta_pregunta = ft.Container(
            content=ft.Column(controls=[
                ft.Text("PREGÚNTELE A SU ASISTENTE", size=13, weight=ft.FontWeight.W_600, color=ACCENT_TEXT,
                        font_family=FONT_BODY),
                ft.Row(controls=[pregunta, boton], spacing=10),
                ft.Row(controls=[ft.OutlinedButton(
                    texto, on_click=accion,
                    style=ft.ButtonStyle(color=INK, bgcolor=PAPER, side=ft.BorderSide(1, RULE),
                                         shape=ft.RoundedRectangleBorder(radius=20),
                                         padding=ft.padding.symmetric(horizontal=15, vertical=10)))
                    for texto, accion in atajos], wrap=True, spacing=8, run_spacing=8),
            ], spacing=14),
            bgcolor=PAPER, border=ft.border.all(1, RULE), border_radius=14,
            padding=ft.padding.symmetric(horizontal=22, vertical=20),
            shadow=ft.BoxShadow(blur_radius=28, color=ft.Colors.with_opacity(0.06, INK), offset=ft.Offset(0, 10)),
        )

        try:
            convs = cuentas.listar_conversaciones(usuario["id"])[:4]
        except Exception:
            convs = []
        tarjeta_convs = seccion_escritorio("Conversaciones recientes", [
            renglon(c["titulo"], cuando(c["actualizada"]), lambda e, i=c["id"]: abrir_conversacion_guardada(i),
                    ultimo=n == len(convs) - 1) for n, c in enumerate(convs)
        ] or [ft.Text("Todavía no ha conversado con su asistente. Escriba arriba su primera pregunta.",
                      size=14, color=INK_SOFT, font_family=FONT_BODY)],
            ("Ver todas", lambda e: ir_a("jurisprudencia")))

        tarjeta_audiencias = seccion_escritorio("Audiencias de la semana", [
            renglon(ent["recurrente"] or ent["expediente"] or "Expediente",
                    " · ".join(x for x in (ent["tribunal"], f"Exp. {ent['expediente']}" if ent["expediente"] else "")
                               if x),
                    lambda e: ir_a("historial"), etiqueta, ultimo=n == len(audiencias) - 1)
            for n, (ent, etiqueta) in enumerate(audiencias[:5])
        ] or [ft.Text("No hay audiencias en los próximos 7 días.", size=14, color=INK_SOFT, font_family=FONT_BODY)],
            ("Ver historial", lambda e: ir_a("historial")))

        def mosaico(icono, texto, accion):
            return ft.Container(
                content=ft.Column(controls=[
                    ft.Icon(icono, size=24, color=ACCENT_TEXT),
                    ft.Text(texto, size=15, weight=ft.FontWeight.W_600, color=INK, font_family=FONT_BODY),
                ], spacing=9),
                bgcolor=SURFACE, border=ft.border.all(1, PAPER_EDGE), border_radius=10, padding=ft.padding.all(15),
                on_click=accion, ink=True, col={"xs": 6},
            )
        tarjeta_mano = seccion_escritorio("A la mano", [ft.ResponsiveRow(controls=[
            mosaico(ft.Icons.ADD_COMMENT_OUTLINED, "Nueva conversación", lambda e: nueva_conversacion()),
            mosaico(ft.Icons.UPLOAD_FILE, "Subir un documento", lambda e: subir_documentos()),
            mosaico(ft.Icons.MENU_BOOK_OUTLINED, "Ver la biblioteca", lambda e: ir_a("biblioteca")),
            mosaico(ft.Icons.EDIT_NOTE, "Nueva solicitud", lambda e: ir_a(KEYS[0])) if con_plantillas else
            mosaico(ft.Icons.PALETTE_OUTLINED, "Cambiar los colores", lambda e: abrir_apariencia()),
        ], spacing=10, run_spacing=10)])

        # sus documentos están en la base de jurisprudencia, que puede tardar en despertar: se cuentan aparte
        cuantos_docs = ft.Text("", size=14, color=INK_SOFT, font_family=FONT_BODY)

        def contar_documentos():
            docs = mis_documentos() or []
            cuantos_docs.value = (f"Ha subido {len(docs)} documento{'s' if len(docs) != 1 else ''}." if docs
                                  else "Todavía no ha subido documentos propios.")
            page.update()
        page.run_thread(contar_documentos)
        tarjeta_biblioteca = seccion_escritorio("Su biblioteca", [
            ft.Text("Sentencias de la Suprema Corte, la Ley 108-05 con sus reglamentos y los documentos "
                    "que usted sube.", size=15, color=INK, font_family=FONT_BODY),
            cuantos_docs,
        ], ("Abrir", lambda e: ir_a("biblioteca")))

        tarjeta_pronto = seccion_escritorio("Pronto en su despacho", [
            renglon("Expedientes", "Una carpeta por cliente con sus documentos, conversaciones y plazos."),
            renglon("Agenda", "Audiencias y vencimientos; el escritorio le avisará lo de la semana.", ultimo=True),
        ])

        tarjetas = ([tarjeta_audiencias, tarjeta_convs] if con_plantillas else [tarjeta_convs])
        tarjetas += [tarjeta_mano, tarjeta_biblioteca, tarjeta_pronto]
        return [cabecera, tarjeta_pregunta, ft.ResponsiveRow(controls=tarjetas, spacing=20, run_spacing=20)]

    # ── ENCABEZADO + SECCIÓN ─────────────────────
    SUBTITULOS = {
        "informe":    ("Nueva solicitud al Catastro",  "Complete los campos para generar la solicitud de Informe Técnico."),
        "archivo":    ("Solicitud de Archivo",          "Complete los campos para generar la solicitud de Copia Certificada."),
        "reporte":    ("Reporte de Audiencia",          "Complete los campos para generar el reporte de la audiencia."),
        "cobros":     ("Solicitud de Cobros",           "Complete los campos para verificar existencia de cuenta o pago."),
        "inspeccion": ("Solicitud de Inspección",       "Redacte el cuerpo libremente y genere el documento oficial."),
        "audiencia_provincial": ("Informe de Audiencia Provincial", "Registre el traslado y la audiencia conforme al modelo suministrado."),
        "conclusiones_saneamiento": ("Conclusiones de Saneamiento", "Cambie expediente, reclamante e inmueble; el resto del modelo se conserva."),
        "historial": ("Historial de expedientes", "Cada Reporte de Audiencia generado (Word o PDF) se guarda aquí automáticamente."),
        "jurisprudencia": ("Asistente", "Pregúntele como a un colega; cada respuesta cita sentencias del Boletín Judicial, leyes o sus documentos."),
        "biblioteca": ("Biblioteca", "Las sentencias, las leyes y sus documentos, en un mismo buscador."),
    }

    BUILDERS = {
        "informe":    build_informe,
        "archivo":    build_archivo,
        "reporte":    build_reporte,
        "cobros":     build_cobros,
        "inspeccion": build_inspeccion,
        "audiencia_provincial": build_audiencia_provincial,
        "conclusiones_saneamiento": build_conclusiones_saneamiento,
        "historial": build_historial,
        "jurisprudencia": build_jurisprudencia,
        "biblioteca": build_biblioteca,
    }

    def rebuild_form():
        key = plantilla["actual"]
        if key == "escritorio":
            form_area.controls = build_escritorio()
            return
        titulo, sub = SUBTITULOS[key]
        en_redaccion = sala_de(key) == "redaccion"
        ruta = f"Redacción  ›  {PESTANAS.get(key, 'Historial')}" if en_redaccion else f"{NOMBRE_APP}  ›  {titulo}"
        form_area.controls = [
            ft.Column(controls=[
                ft.Text(ruta, size=12, color=INK_SOFT, font_family=FONT_BODY),
                ft.Text(titulo, size=32, weight=ft.FontWeight.W_500, color=INK, font_family=FONT_DISPLAY),
                ft.Text(sub, size=14, color=INK_SOFT, font_family=FONT_BODY),
            ], spacing=4),
            *([pestanas_redaccion()] if en_redaccion else []),
            *BUILDERS[key](),
        ]

    # ── LA OFICINA: menú de salas + sección ──────
    lateral_col = ft.Column(controls=[
        ft.Column(controls=[ft.Container(content=logo(), padding=ft.padding.symmetric(horizontal=10)), menu_salas],
                  spacing=28),
        ft.Column(controls=[caja_plan(),
                            ft.Container(content=cuenta_lateral, padding=ft.padding.symmetric(horizontal=10))],
                  spacing=16),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True)
    barra_lateral = ft.Container(content=lateral_col, width=256, bgcolor=PANEL_INK,
                                 padding=ft.padding.symmetric(horizontal=16, vertical=28))

    # en el celular: una barra arriba y las salas en un panel que se despliega debajo
    menu_movil = ft.Container(content=ft.Column(controls=[menu_panel, caja_plan()], spacing=16), visible=False,
                              bgcolor=PANEL_INK, padding=ft.padding.only(left=12, right=12, bottom=16))

    def alternar_menu_movil(e):
        menu_movil.visible = not menu_movil.visible
        page.update()

    barra_movil = ft.Container(
        content=ft.Row(controls=[
            ft.IconButton(ft.Icons.MENU, icon_color=ON_PANEL, tooltip="Salas del despacho",
                          on_click=alternar_menu_movil),
            ft.Text(NOMBRE_APP, size=21, weight=ft.FontWeight.W_600, color=ON_PANEL, font_family=FONT_DISPLAY,
                    expand=True),
            cuenta_movil,
        ], spacing=4),
        bgcolor=PANEL_INK, padding=ft.padding.symmetric(horizontal=6, vertical=4),
        border=ft.border.only(bottom=ft.BorderSide(3, NAV_LINEA)),
    )

    rebuild_form()
    pintar_menu()
    contenido = ft.Container(content=form_area, expand=True)

    def ajustar_ancho():
        """Menú a la izquierda en pantallas anchas y en un cajón en el celular; la sección centrada."""
        ancho, alto = page.width or 1280, page.height or 800
        con_menu = ancho >= 900
        barra_lateral.visible, barra_movil.visible = con_menu, not con_menu
        menu_movil.visible = menu_movil.visible and not con_menu
        # en pantallas bajas el menú se desliza; si no, la cuenta queda abajo del todo
        lateral_col.scroll = None if alto >= 760 else ft.ScrollMode.AUTO
        util = ancho - (256 if con_menu else 0)
        lado = max(32, (util - ANCHO_MAX) / 2) if util >= 760 else 16
        contenido.padding = ft.padding.symmetric(horizontal=lado, vertical=32 if util >= 760 else 16)

    def on_resized(e):
        ajustar_ancho()
        compacto = (page.width or 1280) < 760
        if plantilla["actual"] == "historial" and compacto != hist_estado.get("compacto"):
            rebuild_form()
        page.update()

    page.on_resized = on_resized
    ajustar_ancho()

    page.add(ft.Column(controls=[
        barra_movil,
        menu_movil,
        ft.Row(controls=[barra_lateral, contenido], spacing=0, expand=True,
               vertical_alignment=ft.CrossAxisAlignment.STRETCH),
    ], spacing=0, expand=True))
    if con_plantillas:
        actualizar_contador()


# ══════════════════════════════════════════════════
#  INICIO DE SESIÓN
# ══════════════════════════════════════════════════
CLAVE_SESION = "solicitudes_legales.sesion"
DIR_SUBIDAS  = "uploads"


def proveedor_google():
    """Entrar con Google (variables GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET); None si no está configurado.
    En Google Cloud, la URL de redirección autorizada es <dirección de la app>/oauth_callback."""
    cliente = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    secreto = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not (cliente and secreto):
        return None
    from flet.auth.oauth_provider import OAuthProvider
    # Render pone la dirección pública en RENDER_EXTERNAL_URL
    base = (os.environ.get("APP_URL") or os.environ.get("RENDER_EXTERNAL_URL")
            or f"http://localhost:{os.environ.get('PORT', 8080)}").rstrip("/")
    return OAuthProvider(
        client_id=cliente, client_secret=secreto,
        authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        redirect_url=f"{base}/oauth_callback",
        user_scopes=["openid", "email", "profile"],
        user_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
        user_id_fn=lambda u: u["sub"])


def pantalla_login(page: ft.Page, al_entrar):
    """Formulario de entrada; la primera vez permite crear el administrador."""
    try:
        primera_vez = not cuentas.hay_usuarios()
    except Exception as ex:
        page.add(ft.Container(ft.Text(f"No se pudo conectar con la base de datos: {ex}", color=PDF_COLOR),
                              padding=40))
        return
    # En el servidor, el primer administrador exige el código de instalación (variable de entorno)
    codigo_instalacion = os.environ.get("CODIGO_INSTALACION", "").strip()
    pide_codigo = primera_vez and bool(historial.DATABASE_URL)

    def campo(etiqueta, clave=False, al_enviar=None):
        return ft.TextField(label=etiqueta, password=clave, can_reveal_password=clave, on_submit=al_enviar,
                            border_color=RULE, focused_border_color=ACCENT, cursor_color=ACCENT, bgcolor=SURFACE,
                            border_radius=8, text_style=ft.TextStyle(font_family=FONT_BODY, size=16, color=INK),
                            label_style=ft.TextStyle(font_family=FONT_BODY, size=15, color=INK_SOFT))

    error = ft.Text("", size=13, color=PDF_COLOR, font_family=FONT_BODY, visible=False)   # solo ocupa lugar con texto

    def avisar(texto, es_error=True):
        # la base gratis tarda unos segundos en despertar: sin aviso parece que el botón no hace nada
        error.value, error.color, error.visible = texto, (PDF_COLOR if es_error else INK_SOFT), bool(texto)
        page.update()

    def entrar(e=None):
        avisar("Un momento…", es_error=False)
        try:
            r = cuentas.iniciar_sesion(tf_usuario.value or "", tf_clave.value or "")
        except Exception as ex:
            avisar(f"No se pudo conectar: {ex}"); return
        if not r:
            avisar("Usuario o contraseña incorrectos."); return
        al_entrar(*r)

    def crear_admin(e=None):
        if pide_codigo and (not codigo_instalacion or (tf_codigo.value or "").strip() != codigo_instalacion):
            avisar("Código de instalación incorrecto."); return
        if (tf_clave.value or "") != (tf_clave2.value or ""):
            avisar("Las contraseñas no coinciden."); return
        avisar("Creando la cuenta…", es_error=False)
        try:
            cuentas.crear_usuario(tf_usuario.value or "", tf_clave.value or "", tf_nombre.value or "", es_admin=True,
                                  plantillas=True)
        except ValueError as ex:
            avisar(str(ex)); return
        except Exception as ex:
            avisar(f"No se pudo conectar: {ex}"); return
        entrar()

    # Entrar con Google: la primera vez crea la cuenta en plan de prueba; después entra a la misma cuenta
    google = None if primera_vez else proveedor_google()
    otro_enlace = ft.TextButton("¿No se abrió Google? Toque aquí", visible=False, url_target=ft.UrlTarget.BLANK,
                                style=ft.ButtonStyle(color=INK_SOFT))

    def con_google(e):
        def abrir(url):
            # si el navegador bloquea la ventana, queda el enlace para abrirla con un toque
            otro_enlace.url, otro_enlace.visible = url, True
            page.launch_url(url, web_window_name="flet_oauth_signin", web_popup_window=True)
            avisar("Elija su cuenta de Google en la ventana que se abrió…", es_error=False)
        try:
            page.login(google, on_open_authorization_url=abrir)
        except Exception as ex:
            avisar(f"No se pudo abrir Google: {ex}")

    def al_volver_de_google(e):
        if e.error:
            avisar("No se completó la entrada con Google. Intente otra vez."); return
        datos = dict(page.auth.user) if page.auth and page.auth.user else {}
        avisar("Un momento…", es_error=False)
        try:
            r = cuentas.entrar_con_google(datos.get("email", ""), datos.get("name", ""),
                                          bool(datos.get("email_verified")))
        except ValueError as ex:
            avisar(str(ex)); return
        except Exception as ex:
            avisar(f"No se pudo conectar: {ex}"); return
        al_entrar(*r)

    if google:
        page.on_login = al_volver_de_google

    tf_usuario = campo("Usuario")
    tf_clave   = campo("Contraseña", True, crear_admin if primera_vez else entrar)
    tf_nombre, tf_clave2, tf_codigo = campo("Nombre completo"), campo("Repita la contraseña", True), campo("Código de instalación", True)

    if primera_vez:
        titulo, sub = "Crear administrador", "Primera vez: cree la cuenta principal del sistema."
        campos = [tf_nombre, tf_usuario, tf_clave, tf_clave2, *([tf_codigo] if pide_codigo else [])]
        boton = ("Crear y entrar", crear_admin)
        if pide_codigo and not codigo_instalacion:
            error.value, error.visible = "Falta la variable CODIGO_INSTALACION en el servidor para crear el administrador.", True
    else:
        titulo, sub = "Entrar a su despacho", "Con su usuario y contraseña."
        campos = [tf_usuario, tf_clave]
        boton = ("Entrar", entrar)

    boton_principal = ft.ElevatedButton(boton[0], on_click=boton[1], style=ft.ButtonStyle(
        bgcolor=PANEL_INK, color=ON_PANEL, shape=ft.RoundedRectangleBorder(radius=8),
        padding=ft.padding.symmetric(vertical=18)))

    if google:
        # Para los clientes, Google va primero; debajo, usuario y contraseña (las cuentas del despacho)
        sub = "Con su cuenta de Gmail, en un clic."
        cuerpo = [
            ft.OutlinedButton(
                content=ft.Row(controls=[
                    ft.Image(src="/google_g.svg", width=20, height=20),
                    ft.Text("Continuar con Google", size=16, weight=ft.FontWeight.W_600, color="#1F1F1F",
                            font_family=FONT_BODY),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=12),
                on_click=con_google,
                style=ft.ButtonStyle(bgcolor="#FFFFFF", side=ft.BorderSide(1, "#747775"),
                                     shape=ft.RoundedRectangleBorder(radius=8),
                                     padding=ft.padding.symmetric(vertical=16))),
            otro_enlace,
            ft.Row(controls=[ft.Container(height=1, bgcolor=PAPER_EDGE, expand=True), ft.Text("o con usuario y contraseña", size=14, color=HINT, font_family=FONT_BODY),
                             ft.Container(height=1, bgcolor=PAPER_EDGE, expand=True)],
                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            *campos, error, boton_principal,
            ft.Container(
                content=ft.Text(spans=[
                    ft.TextSpan("¿Primera vez? ", ft.TextStyle(weight=ft.FontWeight.W_600, color=INK)),
                    ft.TextSpan("Su despacho se abre solo al entrar con Google: "),
                    ft.TextSpan(f"{cuentas.DIAS_PRUEBA} días gratis", ft.TextStyle(weight=ft.FontWeight.W_600,
                                                                                    color=ACCENT_TEXT)),
                    ft.TextSpan(", sin tarjeta."),
                ], size=14, color=INK_SOFT, font_family=FONT_BODY),
                bgcolor=SURFACE, border=ft.border.all(1, PAPER_EDGE), border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=12)),
        ]
    else:
        cuerpo = [*campos, error, boton_principal]

    # La recepción: a la izquierda qué es el despacho; a la derecha, la entrada
    ancho = page.width or 1280
    angosto = ancho < 760
    lado = max(20, (ancho - 1240) / 2)

    def dato(fuerte, resto):
        return ft.Text(spans=[ft.TextSpan(fuerte, ft.TextStyle(weight=ft.FontWeight.W_600, color=INK)),
                              ft.TextSpan(f" {resto}")], size=15, color=INK_SOFT, font_family=FONT_BODY)

    presentacion = ft.Column(controls=[
        ft.Text("PARA ABOGADOS DE REPÚBLICA DOMINICANA", size=14, weight=ft.FontWeight.W_600, color=ACCENT_TEXT,
                font_family=FONT_BODY),
        ft.Text("Todo su trabajo, en una sola oficina.", size=36 if angosto else 54, weight=ft.FontWeight.W_500,
                color=INK, font_family=FONT_DISPLAY),
        ft.Text("Investigue con las sentencias de la Suprema Corte y las leyes, calcule prestaciones y guarde sus "
                "documentos sin salir de aquí. Su asistente lee por usted y le muestra la página exacta de cada cita.",
                size=17 if angosto else 19, color=INK_SOFT, font_family=FONT_BODY),
        ft.Container(
            content=ft.Row(controls=[dato("Sentencias", "de la Suprema Corte"), dato("Leyes", "artículo por artículo"),
                                     dato("Sus documentos", "en el mismo buscador")],
                           wrap=True, spacing=28, run_spacing=10),
            padding=ft.padding.only(top=20), border=ft.border.only(top=ft.BorderSide(1, PAPER_EDGE))),
    ], spacing=22, col={"xs": 12, "md": 7})

    entrada = ft.Container(
        col={"xs": 12, "md": 5}, alignment=ft.alignment.center,
        content=ft.Container(
            width=None if angosto else 460, bgcolor=PAPER, border=ft.border.all(1, PAPER_EDGE), border_radius=14,
            padding=ft.padding.all(24 if angosto else 34),
            shadow=ft.BoxShadow(blur_radius=44, color=ft.Colors.with_opacity(0.10, INK), offset=ft.Offset(0, 18)),
            content=ft.Column(controls=[
                ft.Column(controls=[
                    ft.Text(titulo, size=28, weight=ft.FontWeight.W_500, color=INK, font_family=FONT_DISPLAY),
                    ft.Text(sub, size=15, color=INK_SOFT, font_family=FONT_BODY),
                ], spacing=6),
                *cuerpo,
            ], spacing=16, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        ),
    )

    page.add(
        ft.Container(
            content=ft.Row(controls=[
                ft.Container(content=ft.Icon(ft.Icons.BALANCE, size=22, color=ON_BOTON), width=42, height=42,
                             bgcolor=BOTON, border_radius=9, alignment=ft.alignment.center),
                ft.Text(NOMBRE_APP, size=27, weight=ft.FontWeight.W_600, color=PANEL_INK, font_family=FONT_DISPLAY),
            ], spacing=12),
            padding=ft.padding.symmetric(horizontal=lado, vertical=18),
            border=ft.border.only(bottom=ft.BorderSide(1, PAPER_EDGE)),
        ),
        ft.Container(
            # en el celular la entrada va primero, para no tener que bajar a buscarla
            content=ft.ResponsiveRow(controls=[entrada, presentacion] if angosto else [presentacion, entrada],
                                     spacing=48, run_spacing=40,
                                     vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=lado, vertical=32 if angosto else 72),
        ),
    )


def main(page: ft.Page):
    page.title   = NOMBRE_APP
    page.padding = 0
    page.scroll  = ft.ScrollMode.AUTO
    page.fonts   = FUENTES
    aplicar_tema(page)

    def leer_token():
        try:
            return page.client_storage.get(CLAVE_SESION)
        except Exception:
            return None

    def mostrar_login():
        page.controls.clear(); page.overlay.clear(); page.on_resized = None
        page.scroll = ft.ScrollMode.AUTO   # adentro el menú queda fijo y cada sección se desliza
        aplicar_tema(page)   # la entrada siempre con la marca, aunque adentro use otro tema
        pantalla_login(page, entrar)
        page.update()

    def entrar(usuario, token):
        try:
            page.client_storage.set(CLAVE_SESION, token)
        except Exception:
            pass
        page.controls.clear(); page.overlay.clear()
        app_principal(page, usuario, salir)
        page.update()

    def salir():
        token = leer_token()
        try:
            cuentas.cerrar_sesion(token)
            page.client_storage.remove(CLAVE_SESION)
        except Exception:
            pass
        mostrar_login()

    token = leer_token()
    try:
        usuario = cuentas.usuario_de_sesion(token) if token else None
    except Exception:
        usuario = None
    if usuario:
        entrar(usuario, token)
    else:
        mostrar_login()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    os.environ.setdefault("FLET_SECRET_KEY", secrets.token_hex(32))   # firma las URLs de subida
    pathlib.Path(DIR_SUBIDAS).mkdir(exist_ok=True)
    print(f"IA: {juris_ia.estado()}", flush=True)
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, assets_dir="assets", upload_dir=DIR_SUBIDAS)
