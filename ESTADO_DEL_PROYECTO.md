# Estado del proyecto

Resumen para retomar el trabajo (personas o agentes). Actualizado: **8 de noviembre de 2026**.

> **El repositorio es público.** Nunca escribir aquí claves, tokens, cadenas de conexión ni IDs de cuenta.
> Solo se nombran las variables y dónde están guardadas.

## Qué es

App web en Flet para un departamento legal:

- **Plantillas en Word/PDF:** informes, solicitudes y reportes de audiencia. **Solo las ven las cuentas que las tienen activadas** (hoy: Gregorio).
- **Historial de expedientes**, que va con las plantillas.
- **Inicio de sesión:** con Google para clientes (prueba gratis) y con usuario y contraseña para el administrador.
- **Sección Jurisprudencia:** un chat RAG que responde preguntas con sentencias reales de la Suprema Corte de Justicia (Boletín Judicial), con los artículos de la Ley 108-05 y sus reglamentos y con los documentos que sube cada usuario, con citas y un análisis.

El primer usuario real es un abogado del área **Inmobiliario (Tierras)**, que es el "cliente beta", pero el buscador cubre **todas las materias**.

**Regla del dueño:** todo gratis hasta tener clientes. No proponer servicios de pago ni pesados sin preguntar.

## Dónde corre cada cosa

| Pieza | Servicio | Detalle |
|---|---|---|
| Web | **Render**, plan gratis | **El despliegue es manual:** después de cada push a `master` hay que entrar a Render → **Manual Deploy → Deploy latest commit**. Después de cambiar variables, **Restart service**. Se duerme sin uso: la primera carga tarda hasta ~1 min |
| Usuarios, sesiones e historial | **Neon**, proyecto `solicitudes-legales` | Variable `DATABASE_URL`. No tocar |
| Jurisprudencia | **Neon**, 5 proyectos en AWS US East 2 (Ohio) | `jurisprudencia-rd` (principal: solo documentos de usuarios) y `jurisprudencia-archivo-1` a `-4` (Boletín) |
| Carga del Boletín | **GitHub Actions**, `.github/workflows/boletines.yml` | Todos los días a las 5:00 a. m. (RD); GitHub la atrasa a veces varias horas. También a mano: *Actions → Cargar boletines → Run workflow* |
| Carga de leyes | **GitHub Actions**, `.github/workflows/leyes.yml` | Solo a mano: *Actions → Cargar leyes → Run workflow*. Se puede repetir sin duplicar |
| Huellas atrasadas | **Kaggle**, GPU gratis | Una sola vez: `kaggle/huellas.ipynb` (ver abajo) |
| Respuestas de la IA | **Groq** | `openai/gpt-oss-120b` redacta y `openai/gpt-oss-20b` prepara las búsquedas |
| Huellas (vectores), y respaldo de la IA | **Cloudflare Workers AI** | `@cf/qwen/qwen3-embedding-0.6b` (1024 dimensiones). Si Groq llega a su límite, responde `@cf/openai/gpt-oss-120b`. Plan gratis: 10.000 neuronas por día |
| Entrar con Google | **Google Cloud**, pantalla de consentimiento | Está en modo **Testing**: solo entran los correos agregados como *test users*. Para clientes hay que **publicarla** |

### Variables (solo los nombres)

| Dónde | Variables |
|---|---|
| Render → Environment | `DATABASE_URL`, `JURIS_DATABASE_URL` (todas las bases de jurisprudencia en una, la principal primero), `IA_API_KEY`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CODIGO_INSTALACION`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| GitHub → Settings → Secrets → Actions | `JURIS_DATABASE_URL` (principal), `JURIS_ARCHIVO_URLS` (los 4 archivos), `CF_ACCOUNT_ID`, `CF_API_TOKEN` |
| Kaggle → Add-ons → Secrets | `JURIS_URLS` (todas las bases, igual que en Render) |

- Las cadenas de Neon se pueden pegar con el nombre del proyecto delante: el código toma solo lo que empieza en `postgresql://`.
- Usar la conexión **directa**, no la `-pooler`.
- Un secreto de GitHub no se puede leer ni completar: para agregar una base hay que volver a pegar **todas** las cadenas.

## Cuentas y planes (`cuentas.py`)

- **Planes:** `activo` (cuentas creadas por el administrador), `beta` (ilimitado y gratis: el abogado), `prueba` (14 días y 20 preguntas por día, variables `PRUEBA_DIAS` y `PRUEBA_PREGUNTAS_DIA`) y `vencido`.
- **Google:** quien entra por primera vez queda en `prueba`. Si el administrador le pone un correo a una cuenta existente (panel **Usuarios**), con ese Gmail entra a esa misma cuenta.
- **Plantillas:** casilla **"Ve las plantillas de solicitudes"** por cuenta, en el panel Usuarios. Sin ella, la cuenta entra directo a Jurisprudencia, sin pestañas ni historial. Las cuentas nuevas la traen apagada. Se aplica cuando la persona vuelve a entrar.
- Las preguntas se cuentan por día en la tabla `uso`.

## Cómo funciona la jurisprudencia

Los archivos están en `jurisprudencia/`.

- **`buscador.py`: búsqueda híbrida en todas las bases a la vez**, con un hilo por base. Arma tres listas:
  - **Por número**, de sentencia o de expediente. Reconoce `SCJ-TS-25-1451` y también el formato viejo "núm. 10 del 27 de enero de 2021".
  - **Por palabras**, con el buscador de texto de PostgreSQL en español. Exige al menos 2 palabras importantes y quita las palabras comunes de la tabla `terminos_comunes`.
  - **Por significado**, con pgvector: índice HNSW binario y luego reordenado con el vector completo. **Solo encuentra los fragmentos que ya tienen huella.**

  Las tres se mezclan con RRF; el número pesa 3 veces. Salen como máximo 2 fragmentos por documento. Si una base falla, se busca en las demás.
- **`ia.py`, el chat:**
  - Un filtro sin IA (`parece_consulta`) contesta saludos y preguntas sobre el asistente ("¿ya funciona?") sin buscar.
  - `preparar_busqueda` mira la conversación y decide: **nueva** (reescribe la pregunta para que se entienda sola y arma 2–4 búsquedas), **seguimiento** ("explíquelo más simple": usa las mismas sentencias) o **no jurídica**.
  - `responder` recuerda los últimos 4 mensajes y responde así: respuesta directa, **Lo que dice la jurisprudencia** con citas [n] y **Análisis**. Usa solo las fuentes que sirven y borra las citas a fuentes que no existen. En la pantalla se muestran solo las sentencias citadas.
  - Si la IA no está, el mensaje dice qué claves ve el servidor (`estado()`); al arrancar también lo escribe en el log (`IA: Groq sí, Cloudflare sí`).
- **`basedatos.py`:**
  - Varias bases (`bases()`): primero la principal, después las de archivo.
  - Cada base se llena hasta `JURIS_LIMITE_MB` (850 MB por defecto); la principal hasta 650 MB, para dejar lugar a los documentos de los usuarios.
  - `tamano_final_mb` suma lo que van a ocupar las huellas que faltan (3,5 KB cada una) para decidir dónde cabe un mes.
- **`procesar.py`:**
  - Saca el texto: `pdftotext` si está instalado, si no `pypdf`, y `python-docx` para Word.
  - Detecta la ficha de la sentencia y la parte en fragmentos de ~400 palabras.
  - Calcula las huellas con prioridad: primero los documentos propios, después **Tierras e Inmobiliario**, después lo más nuevo.
- **`boletin.py`:** lee el Boletín. **El formato cambia según el año:**
  - Si el índice trae `|` (materia, recurso, decisión), corta con el índice (mayo 2025).
  - Si no, corta por la cabecera de cada sentencia en el cuerpo del PDF: "SENTENCIA DEL … NÚM. 10" (antes de 2022, la numeración vuelve a empezar en cada sala) o "NÚM. SCJ-PS-22-1765". En enero 2025 el número se repite arriba de cada página.
  - El nombre del archivo cambia de mayúsculas según el año (`MAYO.pdf`, `Mayo.pdf`, `junio.pdf`): `buscar_url()` prueba las tres.
- **`cargar_boletines.py`:**
  - Cuenta los meses **desde el último Boletín publicado** (la Suprema va atrasada más de un año; lo último publicado es agosto 2025). Carga los últimos 60 y **no borra nada**.
  - Cada mes va a la primera base donde cabe contando sus huellas futuras: primero las de archivo, la principal al final. Si todas están llenas, lo dice en el log.
  - Las huellas gastan como máximo 7.000 neuronas por día; después de calcularlas hace `VACUUM`, porque cada huella reescribe su fila.
- **Fuente:** `https://consultaglobal.blob.core.windows.net/boletines/Boletines/{AÑO}/{MES}.pdf`. Es público; la Ley 65-00, art. 41, permite reutilizar textos judiciales citando la fuente.

## Leyes y reglamentos (`jurisprudencia/leyes.py`, `cargar_leyes.py`)

- **Qué se carga:** la Ley 108-05 (texto de la recopilación de 2011, con los cambios de la Ley 51-07) y los 4 reglamentos de 2022: Tribunales (Res. 787-2022), Registro de Títulos (788), Mensuras Catastrales (789) y Regularización Parcelaria y Deslinde (790). **820 artículos, ~840 fragmentos**, unos 10–15 MB con vectores.
- **Fuentes oficiales:** ri.gob.do (la ley) y transparencia.poderjudicial.gob.do (los reglamentos). Las URL están en `NORMAS`.
- **Cómo se guarda:** cada artículo es un documento público (`origen = 'ley'`) en la **base principal**. `numero` = cómo se cita ("Ley 108-05, art. 81"), `titulo` = nombre del artículo, `sala` = nombre completo de la norma, `materia` = Inmobiliario (por eso sus vectores salen antes que el resto).
- **El lector:** cada norma dice dónde empieza y termina su articulado en el PDF (`desde` / `hasta`), porque los PDFs traen antes un índice y el de la ley trae además la Ley 51-07 y los reglamentos viejos de 2009. Un artículo empieza solo si su número sigue al anterior, así no se cuelan las referencias del texto. Probado con los 5 PDFs: no falta ningún artículo.
- **En la búsqueda:** "art. 81 de la Ley 108-05" o "artículo 12 del reglamento de mensuras" se buscan como número exacto (`leyes.citas`). Se guardan hasta 2 lugares para artículos de ley entre las fuentes, solo si vienen al caso. El chat agrega la sección **Lo que dice la ley**.
- **No se recalculan las palabras comunes de la principal** al cargar leyes: con solo leyes saldrían comunes "registro" o "inmueble".
- **Leyes comentadas (`OBRAS`, origen `doctrina`):** el dueño decidió cargar *La Ley 108-05 comentada por Registradores de Títulos* (Escuela Nacional de la Judicatura, 2022): 133 comentarios (principios + arts. 1–132), ~435 fragmentos, ~4 MB. Cada comentario tiene el mismo `numero` que su artículo ("Ley 108-05, art. 81"), así sale junto a la ley. **Licencia CC BY-NC-ND 4.0** (no comercial, sin derivadas): siempre se citan obra y autores, en pantalla solo salen extractos cortos y la IA lo resume sin copiar párrafos. Si la Escuela lo pide, se quita con `python cargar_leyes.py --quitar-comentarios`. Conviene pedirle permiso por escrito antes de cobrar. El *Código Penal Comentado* (ENJ, 2026, misma licencia) **no** se cargó: no hay clientes de penal y ocuparía ~8 MB.
- **Más leyes (8 nov), en la carpeta `leyes/` del repo** (PDFs que bajó el dueño; se abren en la app desde GitHub): Código Civil, Código de Procedimiento Civil, Código de Trabajo, Ley 189-11 (fideicomiso e hipotecas) y su modificación 338-21, Ley 82-25 (Bien de Familia), Ley 5038 (Condominios), Ley 675 (Urbanización y Ornato), Ley 176-07 (Municipios, PDF escaneado con errores de lectura), Ley 202-04 (Áreas Protegidas), Res. 517-2007 (Constancias Anotadas), Res. 82-2025 (modifica el Reglamento de Deslinde) y Res. 008-2020 del CPJ. ~5.000 fragmentos, ~35–40 MB. También la Ley 64-00 (Medio Ambiente): el dueño indicó que los artículos que faltan (79–115) fueron quitados; ese PDF tiene páginas repetidas y fuera de orden, por eso usa `orden_libre`. **No** se cargaron los libros comentados del Código Penal y de la Constitución.
- **Al volver a cargar**, lo que ya está con los mismos artículos no se toca (no se recalculan sus vectores).
- **Para cargar solo los libros:** *Actions → Cargar leyes* con la casilla "Solo los libros comentados" o `python cargar_leyes.py --solo-comentarios`.
- **Para agregar otra ley:** sumar una entrada en `NORMAS` (URL, `desde`, `hasta`, `alias`) y probar con `python cargar_leyes.py --probar`.

## Ver la página dentro de la app (`jurisprudencia/visor.py`)

- El botón **"Ver la página aquí"** de cada fuente abre una ventana con la página del PDF oficial tal como es (imagen), con flechas para pasar de página. Sirve para sentencias, leyes y comentarios; los documentos subidos por el usuario muestran su texto ("Leer aquí").
- Los PDFs del Boletín pesan cientos de MB y **no se descargan**: pikepdf (qpdf) lee a pedazos con HTTP Range solo el índice y los objetos de esa página, se arma un PDF de una página y pypdfium2 lo dibuja. Medido: ~2–3 s y ~3 MB la primera página de un mes, casi al instante las siguientes.
- Trampas medidas: pdfium solo, o qpdf con `inherit_page_attributes=True`, `pages.append` o `copy_foreign`, recorren todas las páginas y bajan el PDF entero (~100 s).

## Huellas con Kaggle (`kaggle/huellas.ipynb`)

- Calcula las huellas que faltan con el **mismo modelo abierto** que usa Cloudflare (Qwen/Qwen3-Embedding-0.6B) en la GPU gratis de Kaggle (30 horas por semana).
- **Comprobado:** las huellas salen iguales a las de Cloudflare (similitud 1,0000 en 40 de 40, y 12 de 12 recalculadas). Por eso se pueden mezclar, y las preguntas se siguen vectorizando con Cloudflare.
- Sin GPU no sirve: en un procesador tarda 8,6 s por fragmento (~860 horas para todo). Por eso no se hace en GitHub Actions.
- Antes de guardar, compara 64 huellas con las de Cloudflare y se detiene si no salen iguales. Solo toca el Boletín: los documentos de los usuarios no salen de Cloudflare.
- Guarda por tandas de 2.048 con `VACUUM` cada 5 tandas. **Si una base pasa de 990 MB, la deja ahí y sigue con la siguiente.** Si se corta, se vuelve a correr y sigue donde quedó.
- **Ya se corrió (8 nov 2026):** 352.178 huellas en 4 h 49 min con GPU T4 x2. Solo hace falta volver a correrlo si se carga mucho de golpe sin huellas.
- **Cómo correrlo:** crear un cuaderno en Kaggle → *File → Import Notebook* → `huellas.ipynb`. En *Session options*: **GPU T4 x2** e **Internet On** (la cuenta debe tener el teléfono verificado). En *Add-ons → Secrets*: `JURIS_URLS`. Después: **Save Version → Save & Run All (Commit)**.
- `kaggle/huellas.py` es el mismo código en forma de script; el `.ipynb` se genera desde ahí.

## Por dónde vamos (8 nov 2026)

- **En GitHub:** `master` tiene el chat, las plantillas por cuenta y el cuaderno de Kaggle. **En Render puede seguir la versión anterior** hasta que se haga *Deploy latest commit*.
- **Boletín cargado:** los 5 años, **58 meses (noviembre 2020 a agosto 2025), 28.493 sentencias y 360.595 fragmentos.** Ya se buscan por palabras y por significado.

  | Base | Meses | Sentencias | Fragmentos | Con huella | Tamaño (8 nov) |
  |---|---|---|---|---|---|
  | principal | — (documentos de usuarios) | — | 0 | — | 8 MB |
  | archivo 1 | 2024-05 → 2025-08 | 8.564 | 97.131 | todos | 825 MB |
  | archivo 2 | 2023-02 → 2024-04 | 8.131 | 93.582 | todos | 789 MB |
  | archivo 3 | 2022-01 → 2023-01 | 5.732 | 90.536 | todos | 773 MB |
  | archivo 4 | 2020-11 → 2021-12 | 6.066 | 79.346 | todos | 681 MB |

- **Huellas: todas hechas.** El cuaderno de Kaggle terminó bien el 8 nov: 352.178 huellas nuevas (más las 8.417 de antes), todas iguales a las de Cloudflare (similitud 1,0000 en 64 de 64). Ninguna base llegó a 990 MB.
- **Espacio:** quedaron en ~3,4 KB por huella, como se había calculado. El archivo 1 (825 MB) está casi en su tope de 850 MB; los meses nuevos irán a las bases con más lugar (el archivo 4 tiene ~170 MB libres). Cuando ya no quepan, toca el pendiente de crear otra base.
- **Faltan dos meses:** septiembre y octubre de 2020 no se encontraron con ninguna de las tres formas del nombre. Julio 2025 trae solo 6 sentencias porque el PDF publicado tiene 31 páginas.

## Pendientes

1. **Kaggle: hecho** (8 nov). Ninguna base se detuvo; no hace falta `jurisprudencia-archivo-5` por ahora.
2. **Probar la búsqueda por significado** con preguntas de materias fuera de Tierras, que antes no tenían huella.
3. **Render:** hacer *Deploy latest commit* y, en el panel Usuarios, dejar la casilla de plantillas **solo en la cuenta de Gregorio**.
4. **Probar el chat en producción:** `¿ya funciona?` no debe buscar; `deslinde aprobado sin citar a los colindantes` debe responder con citas y análisis; `explíquelo más simple` debe usar las mismas sentencias.
5. **El abogado (cliente beta):** ponerle su Gmail a su cuenta y el plan `beta`.
6. **Google:** para clientes nuevos, agregar sus correos como *test users* o publicar la pantalla de consentimiento.
7. **Seguridad:** cambiar la contraseña de `jurisprudencia-rd` (Neon → Roles → Reset password) antes de guardar documentos de clientes, y el secreto de Google. Actualizarlos en Render, GitHub y Kaggle.
8. **Opcional:** que la carga diaria termine en rojo (y GitHub mande correo) cuando todas las bases estén llenas.
9. **Revisar** las direcciones de septiembre y octubre de 2020 en el sitio del Poder Judicial.
10. **Detalles del lector:**
    - `detectar_ficha` no reconoce el número viejo ("NÚM. 10") en documentos subidos.
    - En enero 2025 algunos anexos traen otro número arriba y salen como sentencia aparte (pocos casos).
11. **Leyes: cargadas** (8 nov, *Actions → Cargar leyes*): 820 artículos, 858 fragmentos, todos con vector; la base principal quedó en 14 MB. Falta: *Deploy latest commit* en Render y probar «¿qué dice el art. 81 de la Ley 108-05?». Preguntarle al abogado si la Ley 108-05 tuvo cambios después de 2007 (el texto cargado es de 2011). Después, los códigos: Civil, Procedimiento Civil, Trabajo, Penal, Procesal Penal, Comercio, Sociedades (479-08), Constitución y Ley 137-11.
12. **Fuentes futuras, públicas:**
    - Tribunal Constitucional: revisar sus condiciones de uso.
    - Decretos y normas de la DGII o la Junta Monetaria.
    - **No** usar el depósito del Poder Judicial (`sjdeposito`), que tiene el acceso bloqueado.
13. **Cuando las bases se llenen:** crear otro proyecto en Neon y agregarlo al final de las variables. El plan gratis permite 100 proyectos y 20 GB por cuenta.
14. **Cuando haya clientes:** pasar a Neon Launch (se paga por GB) y juntar todo en una sola base. El código funciona igual con una base.

## Reglas para trabajar en este repo

- Los commits van **solo a nombre del dueño**, sin "Co-Authored-By" ni menciones a asistentes de IA.
- **No subir a `master` sin el visto bueno del dueño** ("súbelo").
- **Nunca** poner claves en archivos del repo (es público). Van en Render, GitHub Secrets y Kaggle Secrets.
- No mandar datos personales de clientes a IAs externas (Ley 172-13): en la app se avisa que no se escriban en la pregunta, y los documentos de los usuarios no van a Kaggle.
- Explicar al dueño en español sencillo, paso a paso, y recomendar una opción en vez de dar muchas.

## Probar en local

- **Requisitos:** Python 3.11+, un PostgreSQL con `pgvector` y `pdftotext` (poppler) para leer el Boletín rápido.
- **Variables:** `JURIS_DATABASE_URL` y, si se quiere varias bases, `JURIS_ARCHIVO_URLS`. Sin `DATABASE_URL`, los usuarios y el historial van a SQLite local.

```bash
python cargar_boletines.py --mes 2025-05 --sin-vectores   # cargar un mes
python crear_usuario.py --admin                           # crear un usuario
python main.py                                            # abrir la app (puerto 8080)
```
