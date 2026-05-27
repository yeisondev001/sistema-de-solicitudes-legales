"""
Script de arranque: reemplaza favicon y animación de Flet antes de iniciar la app.
"""
import os, shutil, pathlib, flet_web

web_dir = pathlib.Path(flet_web.__file__).parent / "web"

# Reemplazar favicon con el escudo RDL
shutil.copy("assets/favicon.png", web_dir / "favicon.png")

# Reemplazar animación con PNG transparente
shutil.copy("assets/icons/loading-animation.png", web_dir / "icons" / "loading-animation.png")

# Iniciar la app
import main
import flet as ft

port = int(os.environ.get("PORT", 8080))
ft.app(target=main.main, view=ft.AppView.WEB_BROWSER, port=port, assets_dir="assets")
