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

## Historial de expedientes

Cada **Reporte de Audiencia** generado (Word o PDF) se guarda automáticamente en el **Historial** (botón dorado arriba a la derecha). Desde ahí se puede:

- **Buscar** por expediente, recurrente, tribunal o parcela.
- **Ver completo** cualquier expediente tocando su fila.
- **Editar** un expediente: se abre el formulario con todos sus datos y, al generar, se actualiza ese mismo registro.
- **Usar como base** un expediente: se abre una copia para cambiar solo lo necesario y se guarda como uno nuevo.
- **Borrar** expedientes.
- **Descargar todo en Word** con el formato de *EXPEDIENTES* (una tabla por expediente: No., tribunal, fechas, partes, objeto, parcela y fallo).

Las próximas audiencias de los siguientes 7 días se resaltan en la lista. Si se genera de nuevo un reporte con el mismo No. de expediente y fecha de audiencia, se actualiza en lugar de duplicarse.

- **En producción** el historial se guarda en PostgreSQL ([Neon](https://neon.tech), plan gratuito). Configure la variable de entorno `DATABASE_URL` con la cadena de conexión.
- **En local**, si no existe `DATABASE_URL`, se usa un archivo SQLite (`historial.db`) que se crea solo.

## Usuarios y jurisprudencia

La aplicación pide **usuario y contraseña**. La primera vez se crea la cuenta de administrador, que luego puede crear más usuarios desde el menú de la cuenta (arriba a la derecha) → **Usuarios**. Las contraseñas se guardan cifradas con scrypt.

También se pueden crear desde la terminal (la contraseña no se ve al escribirla). Con `DATABASE_URL` definida se crean en Neon:

```bash
python crear_usuario.py           # usuario normal
python crear_usuario.py --admin   # administrador
```

La sección **Jurisprudencia** permite preguntar en lenguaje normal y responde con sentencias reales, indicando número, sala y página:

- Busca en el **Boletín Judicial** (público) y en los **documentos propios** de cada usuario.
- Cada usuario puede **subir PDF digitales o Word**; solo él los ve. Los PDF escaneados (sin texto) todavía no se leen.
- La búsqueda es **híbrida**: por palabras (búsqueda de texto de PostgreSQL en español) y por significado (vectores de Cloudflare guardados con pgvector). Así encuentra tanto números de expediente y artículos como ideas dichas con otras palabras. Si Cloudflare no responde, busca solo por palabras.
- La IA solo redacta con las fuentes encontradas, y se eliminan las citas que no correspondan a una fuente real. Es una herramienta de apoyo: las citas deben verificarse.
- Las respuestas las redacta Groq; si llega a su límite gratis, contesta Cloudflare.

### Carga del Boletín Judicial

`cargar_boletines.py` descarga el Boletín mensual de la Suprema Corte, lo corta en sentencias, lo guarda y borra el PDF. Desde 2025 el índice trae materia y decisión (se descartan las entradas de prueba); los boletines anteriores se cortan por la cabecera de cada sentencia. Después calcula los vectores que falten, sin pasarse de la cuota gratis del día. Los meses ya cargados se saltan.

El Boletín sale con más de un año de atraso, así que los meses se cuentan desde el último publicado. Se conservan los últimos 60 meses publicados (`--conservar`).

El 1 GB gratis de un proyecto de Neon alcanza para unos 18 meses de Boletín. Para más, se crean otros proyectos en la misma cuenta y se ponen en `JURIS_ARCHIVO_URLS`: cada mes va a la primera base con espacio (la principal al final, con 200 MB libres para los documentos de los usuarios) y el buscador busca en todas a la vez.

```bash
python cargar_boletines.py                 # últimos 60 meses publicados que falten
python cargar_boletines.py --mes 2025-05   # un mes concreto
```

En GitHub corre solo todos los días (`.github/workflows/boletines.yml`). Necesita los secretos `JURIS_DATABASE_URL`, `JURIS_ARCHIVO_URLS`, `CF_ACCOUNT_ID` y `CF_API_TOKEN` en *Settings → Secrets and variables → Actions*.

### Variables de entorno

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | Historial, usuarios y sesiones (PostgreSQL / Neon). Sin ella se usa SQLite local |
| `JURIS_DATABASE_URL` | Base del buscador de jurisprudencia (PostgreSQL / Neon, proyecto aparte) |
| `JURIS_ARCHIVO_URLS` | Opcional: más bases para el Boletín cuando no cabe en una, separadas por espacios |
| `JURIS_LIMITE_MB` | Opcional: hasta cuántos MB se llena cada base (por defecto 870, del 1 GB gratis) |
| `IA_API_KEY` | Clave del proveedor de IA (por defecto Groq). Sin ella se muestran solo los fragmentos |
| `IA_BASE_URL`, `IA_MODELO`, `IA_MODELO_RAPIDO` | Opcional: cambiar de proveedor o de modelo (API compatible con OpenAI). Por defecto `openai/gpt-oss-120b` redacta y `openai/gpt-oss-20b` arma las búsquedas y lo reemplaza si llega al límite |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | Cloudflare Workers AI: vectores de significado y reemplazo de la IA cuando Groq se llena. Sin ellas la búsqueda es solo por palabras |
| `EMB_MODELO`, `CF_MODELO_TEXTO` | Opcional: modelos de Cloudflare (por defecto `@cf/qwen/qwen3-embedding-0.6b` y `@cf/openai/gpt-oss-120b`) |
| `CODIGO_INSTALACION` | Obligatoria en el servidor para crear el primer administrador |
| `FLET_SECRET_KEY` | Opcional: firma de las subidas de archivos (si falta, se genera una al arrancar) |

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
├── historial.py                    # Historial de expedientes (PostgreSQL o SQLite)
├── cuentas.py                      # Usuarios, contraseñas y sesiones
├── crear_usuario.py                # Crear usuarios desde la terminal
├── cargar_boletines.py             # Cargar el Boletín Judicial y sus vectores
├── jurisprudencia/                 # Buscador: procesar documentos, búsqueda e IA
├── generators/
│   ├── base.py                     # Utilidades compartidas para documentos Word
│   ├── informe.py                  # Informe Técnico
│   ├── archivo.py                  # Solicitud de Archivo
│   ├── reporte.py                  # Reporte de Audiencia
│   ├── cobros.py                   # Solicitud de Cobros
│   ├── inspeccion.py               # Solicitud de Inspección
│   ├── audiencia_provincial.py     # Informe de Audiencia Provincial
│   ├── conclusiones_saneamiento.py # Conclusiones de Saneamiento
│   ├── expedientes.py              # Historial en Word (formato EXPEDIENTES)
│   └── pdf_gen.py                  # Generadores PDF
├── assets/                         # Íconos, fuentes (EB Garamond, Lato) y recursos visuales
├── requirements.in                 # Dependencias directas
├── requirements.txt                # Versiones fijas de todas las dependencias
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
