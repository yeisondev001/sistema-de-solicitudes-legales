# Estado del proyecto

Resumen para retomar el trabajo (personas o agentes). Actualizado: **5 de noviembre de 2026**.

> **El repositorio es público.** Nunca escribir aquí claves, tokens, cadenas de conexión ni IDs de cuenta.
> Solo se nombran las variables y dónde están guardadas.

## Qué es

App web en Flet para un departamento legal:

- **Plantillas en Word/PDF:** informes, solicitudes y reportes de audiencia.
- **Historial de expedientes.**
- **Inicio de sesión con usuarios.**
- **Sección Jurisprudencia:** un buscador RAG que responde preguntas con sentencias reales de la Suprema Corte de Justicia (Boletín Judicial) y con los documentos que sube cada usuario.

El primer usuario real es un abogado del área **Inmobiliario (Tierras)**, pero el buscador cubre **todas las materias**.

**Regla del dueño:** todo gratis hasta tener clientes. No proponer servicios de pago ni pesados sin preguntar.

## Dónde corre cada cosa

| Pieza | Servicio | Detalle |
|---|---|---|
| Web | **Render**, plan gratis | Despliega la rama `master`; arranca con `python main.py`. Se duerme sin uso: la primera carga tarda hasta ~1 min |
| Usuarios, sesiones e historial | **Neon**, proyecto `solicitudes-legales` | Variable `DATABASE_URL`. No tocar |
| Jurisprudencia | **Neon**, 4 proyectos en AWS US East 2 (Ohio) | `jurisprudencia-rd` (principal: documentos de usuarios y parte del Boletín) y `jurisprudencia-archivo-1`, `-2`, `-3` (solo Boletín) |
| Carga del Boletín | **GitHub Actions**, `.github/workflows/boletines.yml` | Todos los días a las 5:00 a. m. (RD). También a mano: *Actions → Cargar boletines → Run workflow* |
| Respuestas de la IA | **Groq** | `openai/gpt-oss-120b` redacta y `openai/gpt-oss-20b` arma las búsquedas |
| Vectores, y respaldo de la IA | **Cloudflare Workers AI** | Vectores con `@cf/qwen/qwen3-embedding-0.6b` (1024 dimensiones). Si Groq llega a su límite, responde `@cf/openai/gpt-oss-120b`. Plan gratis: 10.000 neuronas por día |

### Variables (solo los nombres)

| Dónde | Variables |
|---|---|
| Render → Environment | `DATABASE_URL`, `JURIS_DATABASE_URL`, `JURIS_ARCHIVO_URLS`, `IA_API_KEY`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CODIGO_INSTALACION` |
| GitHub → Settings → Secrets → Actions | `JURIS_DATABASE_URL`, `JURIS_ARCHIVO_URLS`, `CF_ACCOUNT_ID`, `CF_API_TOKEN` |

- Las cadenas de Neon se pueden pegar con el nombre del proyecto delante: el código toma solo lo que empieza en `postgresql://`.
- También pueden ir todas en una sola variable: **la primera es la principal**.
- Usar la conexión **directa**, no la `-pooler`.

## Cómo funciona la jurisprudencia

Los archivos están en `jurisprudencia/`.

- **`buscador.py`: búsqueda híbrida en todas las bases a la vez**, con un hilo por base. Arma tres listas:
  - **Por número**, de sentencia o de expediente. Reconoce `SCJ-TS-25-1451` y también el formato viejo "núm. 10 del 27 de enero de 2021".
  - **Por palabras**, con el buscador de texto de PostgreSQL en español. Exige al menos 2 palabras importantes y quita las palabras comunes de la tabla `terminos_comunes`.
  - **Por significado**, con pgvector: índice HNSW binario y luego reordenado con el vector completo.

  Las tres se mezclan con RRF; el número pesa 3 veces. Salen como máximo 2 fragmentos por documento. Si una base falla, se busca en las demás.
- **`ia.py`:**
  - Antes de buscar, descarta saludos y textos que no son consulta: primero con un filtro sin IA (`parece_consulta`) y luego la IA devuelve las búsquedas vacías si no es jurídica. A un saludo se responde "¿En qué le puedo ayudar?" sin buscar.
  - Solo redacta con las fuentes encontradas y borra las citas a fuentes que no existen.
- **`basedatos.py`:**
  - Varias bases (`bases()`): primero la principal, después las de archivo.
  - Cada base se llena hasta `JURIS_LIMITE_MB`, 870 MB por defecto. La principal deja 200 MB libres para los documentos de los usuarios.
- **`procesar.py`:**
  - Saca el texto: `pdftotext` si está instalado, si no `pypdf`, y `python-docx` para Word.
  - Detecta la ficha de la sentencia y la parte en fragmentos de ~400 palabras.
  - Calcula los vectores con prioridad: primero los documentos propios, después **Tierras e Inmobiliario**, después lo más nuevo.
- **`boletin.py`:** lee el Boletín. **El formato cambia según el año:**
  - El código elige solo: si el índice trae `|` (materia, recurso, decisión), corta con el índice. Comprobado en mayo 2025; febrero–abril 2025 sin revisar.
  - Si no trae `|`, corta por la cabecera de cada sentencia en el cuerpo del PDF. Comprobado en julio 2020, enero 2021, junio 2022, junio 2023, enero 2024 y enero 2025. Puede ser "SENTENCIA DEL … NÚM. 10" (antes de 2022, la numeración vuelve a empezar en cada sala) o "NÚM. SCJ-PS-22-1765". En enero 2025 el número se repite arriba de cada página.
  - El nombre del archivo cambia de mayúsculas según el año (`MAYO.pdf`, `Mayo.pdf`, `junio.pdf`) y el servidor las distingue: `buscar_url()` prueba las tres.
- **`cargar_boletines.py`:**
  - Cuenta los meses **desde el último Boletín publicado**, porque la Suprema va atrasada más de un año: lo último publicado es agosto 2025.
  - Carga los últimos 60 y **no borra nada**: los meses nuevos se van sumando. `--conservar N` existe, pero está apagado.
  - Cada mes va a la primera base con espacio: primero las de archivo, la principal al final.
  - `--max-meses` dice cuántos meses descarga por corrida; en el workflow es la opción `max_meses`, 12 por defecto.
  - Los vectores gastan como máximo 7.000 neuronas por día y dejan el resto para las respuestas.
- **Fuente:** `https://consultaglobal.blob.core.windows.net/boletines/Boletines/{AÑO}/{MES}.pdf`. Es público; la Ley 65-00, art. 41, permite reutilizar textos judiciales citando la fuente.

## Por dónde vamos (5 nov 2026)

- **En producción:** `master` = `a8dab9f`, con login, jurisprudencia, carga diaria y filtro de saludos.
- **Usuarios:** el administrador ya se creó en el servidor. Falta, o está por confirmar, la cuenta del abogado.
- **Primera carga del Boletín:** corrida manual `42106471497`, con 12 meses, la más reciente primero. **Estaba corriendo** cuando se escribió esto.
- **Siguiente paso inmediato:** cuando termine, lanzar otra corrida con `max_meses = 48` para completar los 5 años (2–3 horas). Nunca lanzar dos a la vez: el workflow tiene `concurrency` para que esperen.
- **Volumen esperado** (cálculo con muestras):
  - 60 boletines, unas **32.000 sentencias** y **~340.000 fragmentos**.
  - Ocupan **~2,4 GB** repartidos en las 4 bases; la capacidad es ~3,3 GB.
  - Cada mes nuevo agrega ~40 MB: alcanza para ~2 años más.
- **Vectores:** Tierras e Inmobiliario (~22.000 fragmentos) en ~3 días; el resto en ~6–7 semanas por la cuota gratis. Mientras tanto, la búsqueda por palabras funciona con todo lo cargado.

## Pendientes

1. **Lanzar la corrida de 48 meses** y, al terminar, contar sentencias y MB reales por base. Actualizar este archivo.
2. **Probar en producción el filtro de la IA:** `hola cómo estás` no debe buscar; `deslinde` y `me botaron del trabajo sin pagarme` sí.
3. **Login:**
   - El botón "Crear y entrar" no muestra "Creando…" mientras espera a Neon, y parece que no hace nada.
   - `crear_admin` en `main.py` solo captura `ValueError`: mostrar en pantalla cualquier error.
4. **Seguridad:** cambiar la contraseña de `jurisprudencia-rd` (Neon → Roles → Reset password) antes de guardar documentos de clientes, y actualizarla en Render y GitHub.
5. **Vectores más rápidos sin pagar** (opcional):
   - Calcularlos en GitHub Actions con el mismo modelo abierto (Qwen3-Embedding-0.6B).
   - **Antes, comprobar que salgan iguales** a los de Cloudflare, porque las preguntas se siguen vectorizando con Cloudflare.
6. **Detalles del lector:**
   - `detectar_ficha` no reconoce el número viejo ("NÚM. 10") en documentos subidos.
   - En enero 2025 algunos anexos traen otro número arriba y salen como sentencia aparte (pocos casos).
7. **Fuentes futuras, públicas:**
   - Tribunal Constitucional: revisar sus condiciones de uso.
   - Leyes (primero la **Ley 108-05 de Registro Inmobiliario** y sus reglamentos).
   - Decretos y normas de la DGII o la Junta Monetaria.
   - **No** usar el depósito del Poder Judicial (`sjdeposito`), que tiene el acceso bloqueado.
8. **Cuando las bases se llenen** (~2 años): crear `jurisprudencia-archivo-4` en Neon y agregarlo al final de `JURIS_ARCHIVO_URLS`. El plan gratis permite 100 proyectos y 20 GB por cuenta.
9. **Cuando haya clientes:** pasar a Neon Launch (se paga por GB) y juntar todo en una sola base. El código funciona igual con una base.

## Reglas para trabajar en este repo

- Los commits van **solo a nombre del dueño**, sin "Co-Authored-By" ni menciones a asistentes de IA.
- **No subir a `master` sin el visto bueno del dueño.** Render despliega `master` en cuanto llega.
- **Nunca** poner claves en archivos del repo (es público). Van en Render y en GitHub Secrets.
- No mandar datos personales de clientes a IAs externas (Ley 172-13): en la app se avisa que no se escriban en la pregunta.
- Explicar al dueño en español sencillo y recomendar una opción, en vez de dar muchas.

## Probar en local

- **Requisitos:** Python 3.11+, un PostgreSQL con `pgvector` y `pdftotext` (poppler) para leer el Boletín rápido.
- **Variables:** `JURIS_DATABASE_URL` y, si se quiere varias bases, `JURIS_ARCHIVO_URLS`. Sin `DATABASE_URL`, los usuarios y el historial van a SQLite local.

```bash
python cargar_boletines.py --mes 2025-05 --sin-vectores   # cargar un mes
python crear_usuario.py --admin                           # crear un usuario
python main.py                                            # abrir la app (puerto 8080)
```
