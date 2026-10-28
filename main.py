"""
Automatización de Solicitudes Legales
======================================
UI principal — generación de documentos en generators/
"""

import os, base64, copy, platform, pathlib, re, uuid, time, threading
from datetime import date, datetime

import flet as ft

import historial
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
INK        = "#0F2A3F"
INK_SOFT   = "#2C4A63"
ACCENT     = "#B8860B"
PAPER      = "#FBF7EE"
PAPER_EDGE = "#EFE7D2"
RULE       = "#D9C998"
SURFACE    = "#F7F2E6"
PANEL_INK  = "#0F2A3F"

ACCENT_TEXT = "#8A6508"   # dorado oscuro: legible como texto sobre papel
HINT        = "#6E6E6E"
NAV_TEXT    = "#C9D3DC"

FONT_DISPLAY = "EB Garamond"
FONT_BODY    = "Lato"
ANCHO_MAX    = 1040       # ancho máximo del contenido en pantallas grandes
PDF_COLOR    = "#6B1A1A"

KT_NUM    = ft.KeyboardType.NUMBER
RE_FECHA  = re.compile(r"[^0-9/]")
RE_CEDULA = re.compile(r"[^0-9\-]")

# ── LISTAS DE TRIBUNALES Y SALAS ─────────────────
TRIBUNALES_INMOBILIARIA = [
    "SUPREMA CORTE DE JUSTICIA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE AZUA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE BARAHONA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE DUARTE",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE EL SEIBO",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE ESPAILLAT",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE HERMANAS MIRABAL",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE LA ALTAGRACIA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE LA VEGA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MARIA TRINIDAD SÁNCHEZ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MONSEÑOR NOUEL",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MONTE CRISTI",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE MONTE PLATA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE PERAVIA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE PUERTO PLATA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAMANÁ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAN CRISTÓBAL",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAN JUAN DE LA MAGUANA",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SAN PEDRO DE MACORÍS",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SÁNCHEZ RAMÍREZ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SANTIAGO",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE SANTIAGO RODRIGUEZ",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DE VALVERDE",
    "TRIBUNAL DE TIERRAS DE JURISDICCION ORIGINAL DEL DISTRITO NACIONAL",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO CENTRAL",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO ESTE",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO NORESTE",
    "TRIBUNAL SUPERIOR DE TIERRAS DEL DEPARTAMENTO NORTE",
]

TRIBUNALES_CIVIL = [
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE BARAHONA",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN FRANCISCO DE MACORÍS",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE LA VEGA",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN CRISTÓBAL",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN JUAN DE LA MAGUANA",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SAN PEDRO DE MACORÍS",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SANTIAGO",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DE SANTO DOMINGO",
    "CÁMARA CIVIL Y COMERCIAL DE LA CORTE DE APELACIÓN DEL DISTRITO NACIONAL",
    "CÁMARA CIVIL Y COMERCIAL DEL JUZGADO DE PRIMERA INSTANCIA DE AZUA",
]

SALAS_INMOBILIARIA = [
    "Primera Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Segunda Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Tercera Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Cuarta Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Quinta Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Sexta Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Séptima Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
    "Octava Sala del Tribunal de Tierras de Jurisdicción Original del Distrito Nacional",
]

ASUNTOS_INMOBILIARIA = [
    "SOLICITUD DE DESLINDE",
    "SANEAMIENTO",
    "LITIS SOBRE DERECHOS REGISTRADOS",
]

TIPOS_AUDIENCIA_PROVINCIAL = [
    "Deslinde",
    "Deslinde y su división",
    "Deslinde, su división y refundición",
    "Saneamiento",
    "Litis sobre Derechos Registrados",
]

RECLAMANTES_SANEAMIENTO = [
    "COMISIÓN PERMANENTE DE TITULACIÓN DE TERRENOS DEL ESTADO (UTEC).",
    "INSTITUTO AGRARIO DOMINICANO (IAD), REPRESENTADO POR LA COMISIÓN PERMANENTE DE TITULACIÓN DE TERRENOS DEL ESTADO.",
]


# ── DESCARGA ─────────────────────────────────────
def _descargar(page, contenido: bytes, nombre: str, mime: str, snack_fn):
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
                        bgcolor=PANEL_INK, color=PAPER,
                        side={ft.ControlState.DEFAULT: ft.BorderSide(1, ACCENT)},
                        shape=ft.RoundedRectangleBorder(radius=2),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        page.open(dlg)


def _guardar_y_abrir(page, contenido: bytes, nombre: str, snack_fn):
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    _descargar(page, contenido, nombre, mime, snack_fn)


def _guardar_pdf(page, contenido: bytes, nombre: str, snack_fn):
    _descargar(page, contenido, nombre, "application/pdf", snack_fn)


# ── HELPERS UI ───────────────────────────────────
def fila_campos(*controles):
    """Campos lado a lado en pantallas anchas; uno debajo del otro en el celular."""
    for c in controles:
        c.col = {"xs": 12, "md": 12 // len(controles)}
        c.expand = False
    return ft.ResponsiveRow(controls=list(controles), spacing=24, run_spacing=14)


def campo(label, form, key, on_change, hint=None, multiline=False, required=False, expand=True,
          keyboard_type=None, char_filter=None, date_format=False):

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
                   filter_on_type=True):
    """Campo con lista desplegable. Si filter_on_type=False, la lista siempre muestra todas las opciones."""

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


def materia_selector(page, form, key, on_materia_change):
    """Selector de dos opciones con lista en los colores de la plantilla."""
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


def tarjeta(romano, titulo, subtitulo, contenido):
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


def boton_generar(on_click, texto="GENERAR DOCUMENTO WORD"):
    return ft.Container(
        content=ft.Row(controls=[
            ft.Icon(ft.Icons.DOWNLOAD, color=PAPER, size=18),
            ft.Text(texto, size=14,
                    weight=ft.FontWeight.W_500, color=PAPER, font_family=FONT_DISPLAY),
            ft.Text("·", size=22, color=ACCENT),
        ], spacing=14, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=PANEL_INK,
        padding=ft.padding.symmetric(vertical=16, horizontal=34),
        border=ft.border.all(1, ACCENT),
        on_click=on_click, ink=True, border_radius=2,
    )


def boton_pdf(on_click):
    return ft.Container(
        content=ft.Row(controls=[
            ft.Icon(ft.Icons.PICTURE_AS_PDF, color=PAPER, size=18),
            ft.Text("GENERAR DOCUMENTO PDF", size=14,
                    weight=ft.FontWeight.W_500, color=PAPER, font_family=FONT_DISPLAY),
            ft.Text("·", size=22, color=ACCENT),
        ], spacing=14, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=PDF_COLOR,
        padding=ft.padding.symmetric(vertical=16, horizontal=34),
        border=ft.border.all(1, ACCENT),
        on_click=on_click, ink=True, border_radius=2,
    )


def nota_descarga():
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
def main(page: ft.Page):
    page.title   = "Solicitudes Legales"
    page.bgcolor = SURFACE
    page.padding = 0
    page.scroll  = ft.ScrollMode.AUTO

    page.fonts = {
        FONT_DISPLAY: "/fonts/EBGaramond.ttf",
        FONT_BODY:    "/fonts/Lato-Regular.ttf",
    }
    page.theme = ft.Theme(font_family=FONT_BODY)

    hoy = date.today()
    plantilla = {"actual": "informe"}

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
            content=ft.Text(msg, color=PAPER, font_family=FONT_BODY),
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
            bgcolor="#FAEEDA", border=ft.border.all(1, RULE), border_radius=4,
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
                                                      color="#633806", font_family=FONT_BODY),
                                      bgcolor="#FAEEDA", border_radius=10,
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

    # ── NAVEGACIÓN ───────────────────────────────
    KEYS = ["informe", "archivo", "reporte", "cobros", "inspeccion", "audiencia_provincial", "conclusiones_saneamiento"]
    PESTANAS = {
        "informe": "Informe Técnico", "archivo": "Archivo", "reporte": "Reporte de Audiencia",
        "cobros": "Cobros", "inspeccion": "Inspección", "audiencia_provincial": "Provincial",
        "conclusiones_saneamiento": "Conclusiones",
    }

    tabs_row = ft.Row(controls=[], spacing=2, scroll=ft.ScrollMode.AUTO)

    def ir_a(key):
        plantilla["actual"] = key
        rebuild_form(); rebuild_tabs(); page.update()

    def on_arrow_click(e):
        actual = plantilla["actual"]
        idx = KEYS.index(actual) if actual in KEYS else -1
        ir_a(KEYS[idx + 1] if idx < len(KEYS) - 1 else KEYS[0])

    scroll_hint = ft.Container(
        content=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ACCENT, size=26),
        padding=ft.padding.symmetric(horizontal=6, vertical=10),
        tooltip="Siguiente plantilla",
        on_click=on_arrow_click, ink=True, border_radius=4,
    )

    def tab_btn(key):
        activa = plantilla["actual"] == key
        return ft.Container(
            content=ft.Text(PESTANAS[key], size=14, weight=ft.FontWeight.W_600 if activa else ft.FontWeight.W_400,
                            color=PAPER if activa else NAV_TEXT, font_family=FONT_BODY),
            bgcolor=INK_SOFT if activa else "transparent",
            padding=ft.padding.symmetric(vertical=12, horizontal=16),
            border=ft.border.only(bottom=ft.BorderSide(3, ACCENT if activa else "transparent")),
            on_click=lambda e, k=key: ir_a(k), ink=True,
            border_radius=ft.border_radius.only(top_left=4, top_right=4),
        )

    contador = ft.Container(
        content=ft.Text("", size=12, weight=ft.FontWeight.W_600, color=PAPER, font_family=FONT_BODY),
        bgcolor=PANEL_INK, border_radius=10, padding=ft.padding.symmetric(horizontal=7, vertical=1),
        visible=False,
    )
    historial_txt = ft.Text("Historial", size=14, weight=ft.FontWeight.W_600, color=PANEL_INK, font_family=FONT_BODY)
    historial_btn = ft.Container(
        content=ft.Row(controls=[ft.Icon(ft.Icons.HISTORY, color=PANEL_INK, size=18), historial_txt, contador],
                       spacing=6, tight=True),
        bgcolor=ACCENT, border_radius=4, padding=ft.padding.symmetric(horizontal=14, vertical=9),
        on_click=lambda e: ir_a("historial"), ink=True, tooltip="Ver expedientes generados",
    )

    def rebuild_tabs():
        tabs_row.controls = [tab_btn(k) for k in KEYS]
        scroll_hint.visible = plantilla["actual"] != KEYS[-1]
        en_historial = plantilla["actual"] == "historial"
        historial_btn.bgcolor = PAPER if en_historial else ACCENT
        historial_btn.border = ft.border.all(2, ACCENT) if en_historial else None

    def actualizar_contador():
        def tarea():
            try:
                n = historial.contar()
            except Exception:
                return
            contador.content.value = str(n)
            contador.visible = n > 0
            page.update()
        page.run_thread(tarea)

    rebuild_tabs()

    # ── ENCABEZADO + FORMULARIO ──────────────────
    SUBTITULOS = {
        "informe":    ("Nueva solicitud al Catastro",  "Complete los campos para generar la solicitud de Informe Técnico."),
        "archivo":    ("Solicitud de Archivo",          "Complete los campos para generar la solicitud de Copia Certificada."),
        "reporte":    ("Reporte de Audiencia",          "Complete los campos para generar el reporte de la audiencia."),
        "cobros":     ("Solicitud de Cobros",           "Complete los campos para verificar existencia de cuenta o pago."),
        "inspeccion": ("Solicitud de Inspección",       "Redacte el cuerpo libremente y genere el documento oficial."),
        "audiencia_provincial": ("Informe de Audiencia Provincial", "Registre el traslado y la audiencia conforme al modelo suministrado."),
        "conclusiones_saneamiento": ("Conclusiones de Saneamiento", "Cambie expediente, reclamante e inmueble; el resto del modelo se conserva."),
        "historial": ("Historial de expedientes", "Cada Reporte de Audiencia generado (Word o PDF) se guarda aquí automáticamente."),
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
    }

    def rebuild_form():
        key = plantilla["actual"]
        titulo, sub = SUBTITULOS[key]
        ruta = "Inicio  ›  Historial" if key == "historial" else f"Plantillas  ›  {PESTANAS[key]}"
        form_area.controls = [
            ft.Column(controls=[
                ft.Text(ruta, size=12, color=INK_SOFT, font_family=FONT_BODY),
                ft.Text(titulo, size=32, weight=ft.FontWeight.W_500, color=INK, font_family=FONT_DISPLAY),
                ft.Text(sub, size=14, color=INK_SOFT, font_family=FONT_BODY),
            ], spacing=4),
            *BUILDERS[key](),
        ]

    rebuild_form()

    # ── BARRA SUPERIOR ───────────────────────────
    titulo_app = ft.Text("Automatización Legal", size=24,
                         weight=ft.FontWeight.W_500, color=PAPER, font_family=FONT_DISPLAY)
    topbar = ft.Container(
        content=ft.Column(controls=[
            ft.Row(controls=[
                ft.Column(controls=[
                    ft.Text("DEPARTAMENTO LEGAL", size=12, color=RULE, font_family=FONT_BODY),
                    titulo_app,
                ], spacing=0, tight=True, expand=True),
                historial_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row(controls=[
                ft.Container(content=tabs_row, expand=True),
                scroll_hint,
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.END),
        ], spacing=8),
        bgcolor=PANEL_INK,
        border=ft.border.only(bottom=ft.BorderSide(3, ACCENT)),
    )
    contenido = ft.Container(content=form_area, expand=True)

    def ajustar_ancho():
        """Contenido centrado con ancho máximo; márgenes chicos en el celular."""
        ancho = page.width or 1280
        lado  = max(24, (ancho - ANCHO_MAX) / 2) if ancho >= 760 else 16
        titulo_app.size = 24 if ancho >= 480 else 19
        topbar.padding    = ft.padding.only(top=16, bottom=0, left=lado, right=lado)
        contenido.padding = ft.padding.symmetric(horizontal=lado, vertical=24 if ancho >= 760 else 16)

    def on_resized(e):
        ajustar_ancho()
        compacto = (page.width or 1280) < 760
        if plantilla["actual"] == "historial" and compacto != hist_estado.get("compacto"):
            rebuild_form()
        page.update()

    page.on_resized = on_resized
    ajustar_ancho()

    page.add(ft.Column(controls=[topbar, contenido], spacing=0, expand=True))
    actualizar_contador()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, assets_dir="assets")
