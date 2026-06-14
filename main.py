"""
Automatización de Solicitudes Legales
======================================
UI principal — generación de documentos en generators/
"""

import os, base64, platform, pathlib, re, uuid, time
from datetime import date

import flet as ft

from generators import (
    generar_informe_tecnico,
    generar_copia_certificada,
    generar_reporte_audiencia,
    generar_solicitud_cobros,
    generar_solicitud_inspeccion,
    nombre_archivo,
    pdf_informe_tecnico,
    pdf_copia_certificada,
    pdf_reporte_audiencia,
    pdf_solicitud_cobros,
    pdf_solicitud_inspeccion,
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

FONT_DISPLAY = "Cormorant Garamond"
FONT_BODY    = "Source Serif 4"
PDF_COLOR    = "#6B1A1A"   # rojo vino — clásico PDF, armoniza con navy+gold

# Teclado numérico para fechas y cédulas
KT_NUM       = ft.KeyboardType.NUMBER
RE_FECHA     = re.compile(r"[^0-9/]")   # solo dígitos y /
RE_CEDULA    = re.compile(r"[^0-9\-]")  # solo dígitos y -


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
        try:
            now = time.time()
            for f in dl_dir.iterdir():
                if f.is_file() and (now - f.stat().st_mtime) > 3600:
                    f.unlink(missing_ok=True)
        except Exception:
            pass
        uid   = uuid.uuid4().hex[:8]
        safe  = re.sub(r"[^\w._-]", "_", nombre)
        fname = f"{uid}_{safe}"
        (dl_dir / fname).write_bytes(contenido)

        # Diálogo con botón url= nativo — iOS Safari lo permite porque
        # Flutter web lo convierte en un <a> real tocado por el usuario
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
                    font_family=FONT_BODY, color=INK_SOFT, size=11, italic=True,
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
def ornamento(color=ACCENT):
    return ft.Row(
        controls=[
            ft.Container(width=44, height=1, bgcolor=color),
            ft.Container(width=8, height=8, bgcolor=color,
                         border_radius=4, margin=ft.margin.symmetric(horizontal=6)),
            ft.Container(width=44, height=1, bgcolor=color),
        ],
        alignment=ft.MainAxisAlignment.CENTER, spacing=0,
    )


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
        hint_style=ft.TextStyle(font_family=FONT_BODY, italic=True, color="#999"),
        content_padding=ft.padding.symmetric(vertical=8, horizontal=2),
        keyboard_type=keyboard_type,
        on_change=_on_change,
    )
    req_star = ft.Text(" *", color=ACCENT, size=10) if required else ft.Text("")
    return ft.Column(
        controls=[
            ft.Row(controls=[
                ft.Text(label.upper(), size=10, weight=ft.FontWeight.W_600,
                        color=INK_SOFT, font_family=FONT_BODY),
                req_star,
            ], spacing=0),
            tf,
        ],
        spacing=4, expand=expand,
    )


def tarjeta(romano, titulo, subtitulo, contenido):
    return ft.Container(
        content=ft.Column(controls=[
            ft.Row(controls=[
                ft.Container(
                    content=ft.Text(romano, size=18, italic=True,
                                    color=ACCENT, font_family=FONT_DISPLAY),
                    width=38, height=38,
                    border=ft.border.all(1, ACCENT),
                    alignment=ft.alignment.center,
                ),
                ft.Column(controls=[
                    ft.Text(titulo, size=20, weight=ft.FontWeight.W_500,
                            color=INK, font_family=FONT_DISPLAY),
                    ft.Text(subtitulo, size=11, italic=True,
                            color=INK_SOFT, font_family=FONT_BODY),
                ], spacing=2, tight=True),
            ], spacing=14),
            ft.Container(height=1, bgcolor=RULE,
                         margin=ft.margin.symmetric(vertical=12), opacity=0.6),
            contenido,
        ], spacing=0),
        bgcolor=PAPER, border=ft.border.all(1, PAPER_EDGE), padding=ft.padding.all(22),
    )


def boton_generar(on_click):
    return ft.Container(
        content=ft.Row(controls=[
            ft.Icon(ft.Icons.DOWNLOAD, color=PAPER, size=18),
            ft.Text("GENERAR DOCUMENTO WORD", size=14,
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
            size=11, italic=True, color=INK_SOFT, font_family=FONT_BODY,
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
        FONT_DISPLAY: "https://fonts.gstatic.com/s/cormorantgaramond/v16/co3YmX5slCNuHLi8bLeY9MK7whWMhyjornGV.ttf",
        FONT_BODY:    "https://fonts.gstatic.com/s/sourceserifpro/v15/neIQzD-0qpwxpaWvjeD0X88SAOeauXE-pg.ttf",
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
        "tipo_proceso":         "deslinde",
        "tribunal":             "",
        "firmante_nombre":      "YOLANDA DE LA CRUZ VARGAS.",
        "firmante_cargo":       "Directora Legal.",
        "iniciales":            "YDCV/rr",
    }

    form_reporte = {
        "tribunal":        "",
        "expediente":      "",
        "demandantes":     "",
        "demandados":      [""],
        "asunto":          "Solicitud de Deslinde.",
        "parcela":         "",
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
        "tipo_proceso":       "Saneamiento",
        "parcela":            "Designación Posesional No.",
        "municipio":          "",
        "provincia":          "",
        "expediente":         "",
        "cedula":             "",
        "tribunal":           "",
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
                        hint_style=ft.TextStyle(font_family=FONT_BODY, italic=True, color="#999"),
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
                    ft.Text("Agregar anexo", color=ACCENT, size=13, font_family=FONT_BODY),
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
                ft.Row(controls=[campo("Fecha de la carta", form,"fecha_carta",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Asunto",form,"asunto",rf,required=True)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Destinatario",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Nombre (Atención)",form,"atencion_nombre",rf),
                                 campo("Cargo (Atención)",form,"atencion_cargo",rf)], spacing=24),
            ])),
            tarjeta("II",  "Inmueble", "Inscripción catastral, anexos y propietario", ft.Column(controls=[
                ft.Row(controls=[ft.Text("ANEXOS",size=10,weight=ft.FontWeight.W_600,color=INK_SOFT,font_family=FONT_BODY),
                                 ft.Text(" *",color=ACCENT,size=10)], spacing=0),
                anexos_col, ft.Container(height=14),
                campo("No. Inscripción Catastral (cuerpo)",form,"inscripcion_no",rf,required=True),
                ft.Container(height=14),
                campo("Nombre del propietario / propietarios",form,"propietario",rf,multiline=True,required=True),
            ])),
            tarjeta("III", "Audiencia", "Fecha, lugar y expediente", ft.Column(controls=[
                ft.Row(controls=[
                    campo("Fecha de audiencia",form,"fecha_audiencia",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                    ft.Row(controls=[campo("Salón",form,"salon",rf), campo("Piso",form,"piso",rf)], spacing=16, expand=True),
                ], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Lugar",form,"lugar",rf),
                                 campo("No. Expediente",form,"expediente",rf,required=True)], spacing=24),
                ft.Container(height=14),
                campo("Nombre del cliente",form,"cliente",rf,multiline=True,required=True),
            ])),
            tarjeta("IV",  "Firma", "Quien suscribe la solicitud", ft.Column(controls=[
                ft.Row(controls=[campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)], spacing=24),
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

        def _validar_archivo():
            reqs = [("nombre_cliente","Nombre del cliente"),("cedula","Cédula"),
                    ("descripcion_inmueble","Descripción del inmueble"),("tipo_proceso","Tipo de proceso"),("tribunal","Tribunal")]
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
                                 campo("Asunto",form,"asunto",rf,required=True)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Destinatario (A)",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)], spacing=24),
            ])),
            tarjeta("II",  "Expediente", "Cliente, inmueble y tribunal", ft.Column(controls=[
                ft.Row(controls=[campo("Nombre del cliente",form,"nombre_cliente",rf,required=True,multiline=True),
                                 campo("Cédula de identidad",form,"cedula",rf,hint="000-0000000-0",required=True,keyboard_type=KT_NUM,char_filter=RE_CEDULA)], spacing=24),
                ft.Container(height=14),
                campo("Descripción del inmueble",form,"descripcion_inmueble",rf,
                      hint="Parcela No. X, del Distrito Catastral No. X…",multiline=True,required=True),
                ft.Container(height=14),
                ft.Row(controls=[campo("Tipo de proceso",form,"tipo_proceso",rf,hint="deslinde / desalojo…",required=True),
                                 campo("Tribunal / Sala",form,"tribunal",rf,multiline=True,required=True)], spacing=24),
            ])),
            tarjeta("III", "Firma", "Quien suscribe la solicitud", ft.Column(controls=[
                ft.Row(controls=[campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)], spacing=24),
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
                        hint_style=ft.TextStyle(font_family=FONT_BODY, italic=True, color="#999"),
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
                    ft.Text("Agregar demandado", color=ACCENT, size=13, font_family=FONT_BODY),
                ], spacing=6), on_click=on_agregar,
            ))

        build_demandados()

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
                dem   = next((x.strip() for x in form.get("demandados",[]) if x.strip()), "")
                ident = dem or form.get("expediente","Reporte")
                _guardar_y_abrir(page, contenido, nombre_archivo("Reporte de Audiencia", ident), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        def on_pdf_reporte(e):
            faltantes = _validar_reporte()
            if faltantes:
                snack("Campos requeridos: " + ", ".join(faltantes), ok=False); return
            try:
                contenido = pdf_reporte_audiencia(form)
                dem   = next((x.strip() for x in form.get("demandados",[]) if x.strip()), "")
                ident = dem or form.get("expediente","Reporte")
                _guardar_pdf(page, contenido, nombre_archivo("Reporte de Audiencia", ident).replace(".docx",".pdf"), snack)
            except Exception as ex:
                snack(f"Error: {ex}", ok=False)

        return [
            tarjeta("I",   "Expediente", "Tribunal, partes y parcela", ft.Column(controls=[
                ft.Row(controls=[campo("No. Expediente",form,"expediente",rf,required=True),
                                 campo("Asunto",form,"asunto",rf,required=True)], spacing=24),
                ft.Container(height=14),
                campo("Tribunal",form,"tribunal",rf,multiline=True,required=True),
                ft.Container(height=14),
                campo("Parcela / Designación",form,"parcela",rf,required=True),
            ])),
            tarjeta("II",  "Partes", "Demandante y demandado(s)", ft.Column(controls=[
                campo("Demandante(s)",form,"demandantes",rf,multiline=True,required=True),
                ft.Container(height=14),
                ft.Row(controls=[ft.Text("DEMANDADO(S)",size=10,weight=ft.FontWeight.W_600,
                                         color=INK_SOFT,font_family=FONT_BODY),
                                 ft.Text(" *",color=ACCENT,size=10)], spacing=0),
                dem_col,
            ])),
            tarjeta("III", "Audiencia", "Fecha, fallo y próxima audiencia", ft.Column(controls=[
                ft.Row(controls=[campo("Fecha de la audiencia",form,"fecha_audiencia",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Caja No.",form,"caja_no",rf),
                                 campo("Rol",form,"rol",rf)], spacing=24),
                ft.Container(height=14),
                campo("Fallo",form,"fallo",rf,multiline=True,required=True,hint="Ej: Aplazada a los fines de que…"),
                ft.Container(height=14),
                ft.Row(controls=[campo("Fecha próxima audiencia",form,"fecha_proxima",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Abogado(s) que compareció",form,"abogados",rf,multiline=True,required=True)], spacing=24),
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
                                 campo("Asunto",form,"asunto",rf,required=True)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Destinatario (A LA)",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)], spacing=24),
            ])),
            tarjeta("II",  "Cliente", "Datos del cliente e inmueble", ft.Column(controls=[
                campo("Nombre del cliente",form,"nombre_cliente",rf,required=True,multiline=True,
                      hint="Nombre completo tal como aparece en el expediente"),
                ft.Container(height=14),
                ft.Row(controls=[campo("Tipo de proceso",form,"tipo_proceso",rf,hint="Saneamiento / Deslinde…",required=True),
                                 campo("Parcela / Designación",form,"parcela",rf,hint="Designación Posesional No. …",required=True)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Municipio",form,"municipio",rf,required=True),
                                 campo("Provincia",form,"provincia",rf,required=True)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("No. Expediente",form,"expediente",rf,required=True),
                                 campo("Cédula",form,"cedula",rf,hint="000-0000000-0",required=True,keyboard_type=KT_NUM,char_filter=RE_CEDULA)], spacing=24),
            ])),
            tarjeta("III", "Proceso Legal", "Tribunal, sentencia y tribunal original", ft.Column(controls=[
                campo("Tribunal",form,"tribunal",rf,multiline=True,required=True),
                ft.Container(height=14),
                ft.Row(controls=[campo("No. Sentencia",form,"sentencia",rf,required=True),
                                 campo("Fecha sentencia",form,"fecha_sentencia",rf,hint="01 Julio del 2022",required=True)], spacing=24),
                ft.Container(height=14),
                campo("Tribunal que dictó la sentencia",form,"tribunal_original",rf,multiline=True,required=True),
            ])),
            tarjeta("IV",  "Firma", "Quien suscribe la solicitud", ft.Column(controls=[
                ft.Row(controls=[campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)], spacing=24),
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
                ft.Row(controls=[campo("Fecha de la carta",form,"fecha_carta",rf,hint="DD/MM/AAAA",required=True,keyboard_type=KT_NUM),
                                 campo("Asunto",form,"asunto",rf,required=True)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Destinatario (A)",form,"destinatario",rf,required=True),
                                 campo("Cargo del destinatario",form,"cargo_destinatario",rf)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Atención (nombre)",form,"atencion_nombre",rf),
                                 campo("Atención (cargo)",form,"atencion_cargo",rf)], spacing=24),
            ])),
            tarjeta("II",  "Contenido", "Cuerpo de la solicitud", ft.Column(controls=[
                campo("Párrafo 1 — Cuerpo principal",form,"cuerpo_1",rf,multiline=True,required=True,
                      hint="Muy cortésmente, por medio de la presente, solicitamos que…"),
                ft.Container(height=14),
                campo("Párrafo 2 — Adicional (opcional)",form,"cuerpo_2",rf,multiline=True,
                      hint="Es oportuno mencionar que…"),
            ])),
            tarjeta("III", "Firma", "Quien suscribe y copia", ft.Column(controls=[
                ft.Row(controls=[campo("Nombre del firmante",form,"firmante_nombre",rf,required=True),
                                 campo("Cargo del firmante",form,"firmante_cargo",rf)], spacing=24),
                ft.Container(height=14),
                ft.Row(controls=[campo("Iniciales",form,"iniciales",rf,expand=False),
                                 campo("Cc.",form,"cc",rf,hint="Dirección General.",expand=True)], spacing=24),
            ])),
            ft.Container(height=6),
            ft.Container(content=boton_generar(on_generar), alignment=ft.alignment.center),
            ft.Container(height=8),
            ft.Container(content=boton_pdf(on_pdf_inspeccion), alignment=ft.alignment.center),
            nota_descarga(),
        ]

    # ── TABS ─────────────────────────────────────
    KEYS = ["informe", "archivo", "reporte", "cobros", "inspeccion"]

    tabs_row = ft.Row(controls=[], spacing=4, scroll=ft.ScrollMode.AUTO)

    def on_arrow_click(e):
        idx = KEYS.index(plantilla["actual"])
        plantilla["actual"] = KEYS[idx + 1] if idx < len(KEYS) - 1 else KEYS[0]
        rebuild_form(); rebuild_tabs(); page.update()

    scroll_hint = ft.Container(
        content=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ACCENT, size=26),
        padding=ft.padding.symmetric(horizontal=6, vertical=10),
        tooltip="Siguiente plantilla",
        on_click=on_arrow_click, ink=True, border_radius=4,
    )

    def tab_btn(label, subtitulo, key):
        is_active = plantilla["actual"] == key

        def on_click(e, k=key):
            plantilla["actual"] = k
            rebuild_form(); rebuild_tabs(); page.update()

        return ft.Container(
            content=ft.Column(controls=[
                ft.Text(label, size=15, weight=ft.FontWeight.W_500,
                        color=PAPER if is_active else RULE, font_family=FONT_DISPLAY),
                ft.Text(subtitulo, size=10, italic=True,
                        color=RULE if is_active else INK_SOFT, font_family=FONT_BODY),
            ], spacing=2, tight=True),
            bgcolor=INK_SOFT if is_active else "transparent",
            padding=ft.padding.symmetric(vertical=12, horizontal=20),
            border=ft.border.only(bottom=ft.BorderSide(3, ACCENT if is_active else "transparent")),
            on_click=on_click, ink=True,
            border_radius=ft.border_radius.only(top_left=4, top_right=4),
        )

    def rebuild_tabs():
        tabs_row.controls = [
            tab_btn("Informe Técnico",        "Catastro · Investigación Parcelaria", "informe"),
            tab_btn("Solicitud de Archivo",   "Archivo · Expediente",                "archivo"),
            tab_btn("Reporte de Audiencia",   "Audiencia · Fallo y próxima fecha",   "reporte"),
            tab_btn("Solicitud de Cobros",    "Cobros · Verificación de pago",       "cobros"),
            tab_btn("Solicitud de Inspección","Inspección · Cuerpo libre",           "inspeccion"),
        ]
        scroll_hint.visible = plantilla["actual"] != KEYS[-1]

    rebuild_tabs()

    # ── HEADER + FORM ─────────────────────────────
    SUBTITULOS = {
        "informe":    ("Nueva solicitud al Catastro",  "Complete los campos para generar la solicitud de Informe Técnico."),
        "archivo":    ("Solicitud de Archivo",          "Complete los campos para generar la solicitud de Copia Certificada."),
        "reporte":    ("Reporte de Audiencia",          "Complete los campos para generar el reporte de la audiencia."),
        "cobros":     ("Solicitud de Cobros",           "Complete los campos para verificar existencia de cuenta o pago."),
        "inspeccion": ("Solicitud de Inspección",       "Redacte el cuerpo libremente y genere el documento oficial."),
    }

    header_titulo = ft.Text("", size=30, weight=ft.FontWeight.W_500, color=INK, font_family=FONT_DISPLAY)
    header_sub    = ft.Text("", size=13, italic=True, color=INK_SOFT, font_family=FONT_BODY)

    BUILDERS = {
        "informe":    build_informe,
        "archivo":    build_archivo,
        "reporte":    build_reporte,
        "cobros":     build_cobros,
        "inspeccion": build_inspeccion,
    }

    def rebuild_form():
        key = plantilla["actual"]
        header_titulo.value, header_sub.value = SUBTITULOS[key]
        form_area.controls = [
            ft.Container(
                content=ft.Column(controls=[
                    ornamento(ACCENT), ft.Container(height=10),
                    ft.Text("EXPEDIENTE", size=12, color=INK_SOFT, font_family=FONT_BODY),
                    header_titulo, header_sub,
                ], horizontal_alignment=ft.CrossAxisAlignment.START),
                padding=ft.padding.only(bottom=6),
            ),
            *BUILDERS[key](),
        ]

    rebuild_form()

    # ── TOPBAR ───────────────────────────────────
    topbar = ft.Container(
        content=ft.Column(controls=[
            ft.Row(controls=[
                ft.Column(controls=[
                    ft.Text("SISTEMA DE SOLICITUDES", size=10, italic=True,
                            color=RULE, font_family=FONT_BODY),
                    ft.Text("Automatización Legal", size=22,
                            weight=ft.FontWeight.W_500, color=PAPER, font_family=FONT_DISPLAY),
                ], spacing=2, tight=True),
            ], alignment=ft.MainAxisAlignment.START),
            ft.Row(controls=[
                ft.Container(content=tabs_row, expand=True),
                scroll_hint,
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.END),
        ], spacing=0),
        bgcolor=PANEL_INK,
        padding=ft.padding.only(top=18, bottom=0, left=36, right=8),
        border=ft.border.only(bottom=ft.BorderSide(3, ACCENT)),
    )

    page.add(ft.Column(controls=[
        topbar,
        ft.Container(content=form_area, padding=ft.padding.symmetric(horizontal=48, vertical=24), expand=True),
    ], spacing=0, expand=True))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, assets_dir="assets")
