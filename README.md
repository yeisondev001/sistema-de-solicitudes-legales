# Sistema de Solicitudes Legales

Aplicación web para el Departamento Legal que estandariza la captura de datos y la generación de documentos jurídicos en formato Word y PDF.

El sistema reduce la redacción repetitiva, conserva la estructura de los modelos institucionales y facilita la descarga de documentos listos para revisión y firma.

## Aplicación en línea

Pruebe la versión publicada en [sistema-de-solicitudes-legales.onrender.com](https://sistema-de-solicitudes-legales.onrender.com/).

> La primera carga puede tomar unos instantes cuando el servicio gratuito de Render se está reactivando.

## Funcionalidades

- Generación de documentos en `.docx` y `.pdf`.
- Formularios guiados con validación de datos obligatorios.
- Listas de tribunales, salas y materias para reducir errores de digitación.
- Diseño adaptable para computador y móvil.
- Descarga directa del documento generado; en Windows se guarda además en la carpeta **Descargas**.
- Formato documental homogéneo con fuente Century Gothic.

## Plantillas disponibles

| # | Plantilla | Uso |
|---:|---|---|
| 1 | Informe Técnico | Solicitud de investigación parcelaria al Catastro. |
| 2 | Solicitud de Archivo | Solicitud de copia certificada de expediente. |
| 3 | Reporte de Audiencia | Registro estructurado de audiencia, fallo y próxima fecha. |
| 4 | Solicitud de Cobros | Verificación de existencia de cuenta o pago. |
| 5 | Solicitud de Inspección | Solicitud de inspección con contenido personalizado. |
| 6 | Informe de Audiencia Provincial | Informe narrativo de traslado, audiencia y resultado en una provincia. Admite traslados de uno o dos días. |
| 7 | Conclusiones de Saneamiento | Modelo de conclusiones con expediente, reclamante e inmueble variables. |

## Inicio rápido

Requiere Python 3.11 o superior.

```bash
git clone https://github.com/yeisondev001/sistema-de-solicitudes-legales.git
cd sistema-de-solicitudes-legales
python -m pip install -r requirements.txt
python main.py
```

La aplicación estará disponible en `http://localhost:8080`.

## Uso

1. Seleccione la plantilla en la barra superior.
2. Complete los campos requeridos, identificados con un asterisco.
3. Revise los datos antes de generar el documento.
4. Elija **Generar documento Word** o **Generar documento PDF**.
5. Valide el contenido jurídico y proceda con la firma institucional correspondiente.

> Los documentos se generan a partir de los datos introducidos. La revisión legal y la autorización de firma siguen siendo responsabilidad del equipo competente.

## Estructura del proyecto

```text
├── main.py                         # Interfaz y formularios Flet
├── generators/
│   ├── base.py                     # Utilidades compartidas para documentos Word
│   ├── informe.py                  # Informe Técnico
│   ├── archivo.py                  # Solicitud de Archivo
│   ├── reporte.py                  # Reporte de Audiencia
│   ├── cobros.py                   # Solicitud de Cobros
│   ├── inspeccion.py               # Solicitud de Inspección
│   ├── audiencia_provincial.py     # Informe de Audiencia Provincial
│   ├── conclusiones_saneamiento.py # Conclusiones de Saneamiento
│   └── pdf_gen.py                  # Generadores PDF
├── assets/                         # Íconos y recursos visuales
├── requirements.txt                # Dependencias de Python
├── render.yaml                     # Configuración de despliegue en Render
└── Procfile                        # Comando de arranque para Render
```

## Agregar una plantilla

1. Cree un generador en `generators/` con una función `generar(d: dict) -> bytes`.
2. Exporte la función desde `generators/__init__.py`.
3. Agregue el formulario, validaciones y pestaña en `main.py`.
4. Incorpore su equivalente PDF en `generators/pdf_gen.py`.
5. Pruebe ambos formatos con datos representativos antes de publicar.

## Despliegue

El repositorio incluye la configuración necesaria para desplegar en [Render](https://render.com/). Render instala las dependencias y sirve la aplicación Flet en modo web.

La instancia pública actual está disponible en [https://sistema-de-solicitudes-legales.onrender.com/](https://sistema-de-solicitudes-legales.onrender.com/).

## Contribuciones

Las pautas de desarrollo y verificación están disponibles en [CONTRIBUTING.md](CONTRIBUTING.md).

## Datos y privacidad

Evite versionar expedientes, cédulas, documentos generados u otra información sensible. Los archivos de prueba y las descargas deben permanecer fuera del control de versiones.

## Licencia

Este proyecto se distribuye bajo la [Licencia MIT](LICENSE).
