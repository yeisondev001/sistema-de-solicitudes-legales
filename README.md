# Sistema de Solicitudes Legales

Sistema web desarrollado en **Python + Flet** para automatizar la generación de documentos legales en formato Word (`.docx`) con el formato oficial de la institución.

## Plantillas disponibles

| # | Plantilla | Descripción |
|---|-----------|-------------|
| 1 | **Informe Técnico** | Solicitud al Catastro para Investigación Parcelaria |
| 2 | **Solicitud de Archivo** | Solicitud de Copia Certificada de Expediente |
| 3 | **Reporte de Audiencia** | Reporte de audiencia con fallo y próxima fecha |
| 4 | **Solicitud de Cobros** | Verificación de existencia de cuenta o pago |
| 5 | **Solicitud de Inspección** | Solicitud de inspección con cuerpo libre |

## Características

- Interfaz web con estética **navy + dorado** (Cormorant Garamond / Source Serif 4)
- Generación de documentos `.docx` con **formato exacto** al original
- Fuente **Century Gothic** en todos los documentos
- Campos dinámicos: anexos, demandados y partes configurables
- Vista previa en tiempo real
- El documento se guarda automáticamente en la carpeta **Descargas** y se abre en Word

## Tecnologías

- [Flet](https://flet.dev/) `0.25.2` — Framework web en Python
- [python-docx](https://python-docx.readthedocs.io/) `1.1.2` — Generación de documentos Word

## Instalación y uso local

```bash
# Clonar el repositorio
git clone https://github.com/yeisondev001/sistema-de-solicitudes-legales.git
cd sistema-de-solicitudes-legales

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la app
python main.py
```

Luego abrir el navegador en: **http://localhost:8080**

## Estructura del proyecto

```
├── main.py            # App principal (UI + generadores de documentos)
├── requirements.txt   # Dependencias
├── Procfile           # Configuración para deploy en Render.com
├── render.yaml        # Configuración de Render.com
└── README.md
```

## Deploy

El proyecto está configurado para desplegarse en **[Render.com](https://render.com)** (tier gratuito).

---

Desarrollado para automatizar el flujo de solicitudes del departamento legal.
