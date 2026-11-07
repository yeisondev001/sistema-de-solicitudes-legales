"""
Crea un usuario desde la terminal, sin pasar por la pantalla de inicio.
Usa la misma base que la app: DATABASE_URL (Neon) si está definida, si no historial.db.

    python crear_usuario.py                 -> usuario normal (solo jurisprudencia)
    python crear_usuario.py --admin         -> administrador
    python crear_usuario.py --plantillas    -> que vea también las plantillas de solicitudes
"""

import sys
from getpass import getpass

import cuentas
import historial


def main():
    es_admin = "--admin" in sys.argv
    plantillas = "--plantillas" in sys.argv
    destino = "Neon / PostgreSQL" if historial.DATABASE_URL else f"SQLite ({historial.SQLITE_PATH})"
    print(f"Base de datos: {destino}")
    print("Nuevo " + ("ADMINISTRADOR" if es_admin else "usuario"))

    nombre  = input("Nombre completo: ").strip()
    usuario = input("Usuario: ").strip()
    clave   = getpass("Contraseña (no se ve al escribir): ")
    if clave != getpass("Repita la contraseña: "):
        sys.exit("Las contraseñas no coinciden.")

    try:
        cuentas.crear_usuario(usuario, clave, nombre, es_admin=es_admin, plantillas=plantillas)
    except ValueError as ex:
        sys.exit(str(ex))
    print(f'Listo: "{usuario}" creado' + (" como administrador." if es_admin else "."))


if __name__ == "__main__":
    main()
