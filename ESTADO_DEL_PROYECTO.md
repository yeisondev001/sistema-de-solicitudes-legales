# Estado del proyecto

Resumen para retomar el trabajo (personas o agentes). Actualizado: **11 de noviembre de 2026**.

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

- **Planes:** `activo` (cuentas creadas por el administrador), `beta` (ilimitado y gratis: el abogado), `prueba` (5 días desde el 11 nov, antes 14, y 20 preguntas por día, variables `PRUEBA_DIAS` y `PRUEBA_PREGUNTAS_DIA`) y `vencido`.
- **Google:** quien entra por primera vez queda en `prueba`. Si el administrador le pone un correo a una cuenta existente (panel **Usuarios**), con ese Gmail entra a esa misma cuenta.
- **Plantillas:** casilla **"Ve las plantillas de solicitudes"** por cuenta, en el panel Usuarios. Sin ella, la cuenta entra directo a Jurisprudencia, sin pestañas ni historial. Las cuentas nuevas la traen apagada. Se aplica cuando la persona vuelve a entrar.
- Las preguntas se cuentan por día en la tabla `uso`.
- **Tema de colores:** cada cuenta guarda el suyo en `usuarios.tema` (lo elige en Apariencia).

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
- **Leyes comentadas (`OBRAS`, origen `doctrina`):** el dueño decidió cargar *La Ley 108-05 comentada por Registradores de Títulos* (Escuela Nacional de la Judicatura, 2022): 133 comentarios (principios + arts. 1–132), ~435 fragmentos, ~4 MB. Cada comentario tiene el mismo `numero` que su artículo ("Ley 108-05, art. 81"), así sale junto a la ley. **Licencia CC BY-NC-ND 4.0** (no comercial, sin derivadas): siempre se citan obra y autores, en pantalla solo salen extractos cortos y la IA lo resume sin copiar párrafos. Si la Escuela lo pide, se quita con `python cargar_leyes.py --quitar-comentarios`. Conviene pedirle permiso por escrito antes de cobrar. El dueño también decidió cargar el *Código Penal Comentado* (ENJ, 2026, misma licencia, `leyes/codigo-penal-comentado.pdf`): 393 artículos del nuevo Código Penal (Ley 74-25), cada uno con su texto y su comentario, se cita "Código Penal, art. N". El Código Penal anterior (1884) está como norma "Código Penal (derogado)" (481 artículos); "código penal anterior/derogado" en la pregunta apunta a ese. Falta el texto oficial consolidado de la Ley 74-25 con la Ley 44-26 (DGII bloquea la descarga automática).
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
- **Si *Import Notebook* se queda en "Loading file…"** (pasó la primera vez): crear el cuaderno vacío, abrir `huellas.py` en el Bloc de notas y pegar todo en una sola celda de código. Funciona igual.

## Diseño y marca (decidido el 10 nov 2026)

El concepto: **la app es la oficina del abogado** (nombre de entonces; hoy es Papiniano). Cada parte es una sala: Escritorio (inicio), Asistente (el chat), Biblioteca (sentencias, leyes y documentos), Expedientes (una carpeta por cliente), Redacción (plantillas) y Agenda. Las pantallas, el recorrido del abogado y la marca están en un lienzo de diseño privado del dueño (pedírselo).

- **Paleta de la marca: «Vino y madera».** Es la de la página pública, la entrada, los correos y el pago, y el tema por defecto adentro. El vino son los libros y la madera el escritorio. Todos los contrastes pasan 4,5:1.

  | Color | Valor | Uso |
  |---|---|---|
  | Vino | `#7A1F2B` | Principal: logo, botones, enlaces importantes, color en Lemon Squeezy |
  | Nogal | `#3E2C20` | Menú lateral, encabezados, pie |
  | Marfil | `#F8F4EC` | Fondo |
  | Roble | `#8A5A36` | Citas, etiquetas de materia, líneas |
  | Tinta | `#241C17` | Texto |

- **Letras:** **Literata** para títulos y textos largos (hecha para leer en pantalla) y **Atkinson Hyperlegible** para botones, menús y números (no confunde I/l/1 ni O/0: importa en números de sentencia, expediente y montos). Tamaños: lectura 18 px con interlineado 1,7; botones 16 px; nada por debajo de 13 px; renglones de ~70 letras como máximo.
- **Temas por dentro:** el abogado elige en **Mi cuenta → Apariencia** entre 4 temas cerrados (no un selector libre de colores, para que siempre se lea bien): *Vino y madera* (por defecto), *Papel y tinta* (lo más legible), *Cuero vino y azul oscuro* y *Biblioteca de noche* (oscuro). También **tamaño de letra: Normal, Grande, Muy grande**. Se guarda en su cuenta.
- **Ya en la app (10 nov):**
  - **Temas:** los 4 están en `temas.py`, con todos los contrastes en 5,9:1 o más. La entrada siempre usa la marca.
  - **Dónde se elige:** en el menú de la cuenta → **Apariencia**. Se guarda en la columna `usuarios.tema`; vacío quiere decir la marca.
  - **Cómo lo usa `main.py`:**
    - `app_principal` toma los colores del tema de la persona.
    - Las ayudas de afuera (`campo`, `tarjeta`, `boton_generar`…) reciben el tema con `t=`.
    - Un color nuevo se agrega en los 4 temas y en `temas.NOMBRES`.
  - **Letras:** Literata y Atkinson Hyperlegible se cargan desde jsDelivr (Fontsource). Flet admite un solo archivo por letra, así que la negrita la dibuja el navegador.
- **La oficina por dentro (11 nov):**
  - **Menú de salas** a la izquierda; en el celular, con el botón ☰ arriba. Las salas son Escritorio, Asistente, Biblioteca, Expedientes, Redacción y Agenda.
  - **Las que todavía no existen dicen «Pronto»:** Expedientes y Agenda para todos, y Redacción para las cuentas sin plantillas.
  - **Escritorio (el inicio):**
    - Saludo con la fecha y una caja para preguntarle al asistente (abre una conversación nueva).
    - Conversaciones recientes, cosas a la mano y su biblioteca.
    - Para las cuentas con plantillas, también las audiencias de la semana (salen del historial de reportes).
  - **Asistente:** el chat de siempre. **Biblioteca:** qué hay y «Mis documentos», que antes estaba debajo del chat.
  - **Redacción:** las 7 plantillas y el historial, como pestañas.
  - **No hay sala de Calculadoras** (se quitó el 11 nov): los cálculos los pide el abogado al asistente.
    - Los montos de prestaciones no los saca la IA: salen de las reglas fijas de `jurisprudencia/prestaciones.py` y la IA solo los explica.
    - En el Asistente, uno de los ejemplos de la bienvenida es un cálculo de prestaciones.
    - Cuando se agreguen plazos e intereses, hacerlos igual: reglas en el código y la IA explicando.
  - **Abajo del menú:**
    - La cuenta, con **Apariencia** y **Cerrar sesión**.
    - En plan `prueba`, los días que quedan y las consultas del día.
  - **Entrada nueva («recepción»):** a la izquierda qué es el despacho; a la derecha, Google y usuario/contraseña, los dos a la vista. En el celular la entrada va primero.
  - **El nombre:** era «Despacho», provisional; el 11 nov pasó a ser **Papiniano** (ver abajo).
- **Falta:**
  - El tamaño de letra en la app de Flet (en la app nueva ya está).
  - **Funciones nuevas:** Expedientes (una carpeta por cliente) y Agenda (audiencias y plazos).
  - El botón «Elegir plan» con Lemon Squeezy.
  - Completar los borradores legales y los precios de la página pública.
- **App nueva: pantallas en React, Python detrás (empezó el 11 nov).** El dueño decidió pasar todas las pantallas a React porque el diseño se hace mucho más fácil que en Flet. Lo de fondo se queda en Python.
  - **Stack:** React + TypeScript + Vite + Tailwind + shadcn/ui en `web/`; Python con FastAPI en `servidor.py`. Se descartó Next.js: con Vite, el mismo servicio de Render da la API y las pantallas, sin un segundo servidor que se duerma.
  - **`servidor.py`** usa lo mismo que la app de Flet: `cuentas`, `historial`, `temas`, `jurisprudencia/*` y `generators/*`. La sesión es la de la tabla `sesiones`, guardada en una cookie que JavaScript no puede leer.
    - **Google:** el flujo se hace a mano con `httpx`. La redirección sigue siendo `/oauth_callback`, así que no hay que tocar Google Cloud.
    - **Asistente:** contesta por partes (`/api/asistente`, una línea JSON por evento) para mostrar «Buscando…». La conversación se lee de la base, no de la pantalla.
    - **Si la biblioteca o la IA fallan,** la tabla de prestaciones sale igual (es cálculo fijo) y el abogado ve un aviso en palabras normales; el error técnico solo queda en el registro del servidor.
    - **Visor de páginas:** solo abre PDFs de las fuentes oficiales (`FUENTES_PERMITIDAS`), no cualquier dirección.
  - **Ya hechas:** entrada (Google, usuario y crear administrador), menú de salas con panel en el celular, Escritorio, Asistente (lista de conversaciones, fuentes, visor de la página, copiar), Biblioteca (subir y quitar documentos), Apariencia (los 4 temas, cambian al instante), Redacción (las 7 plantillas en Word y PDF, y el historial: buscar, editar, usar como base, borrar y descargar todo en Word) y Usuarios (solo administradores, en el menú de la cuenta).
  - **Redacción:** `redaccion.py` tiene lo de cada plantilla (valores iniciales, campos obligatorios, generadores, nombre del archivo) y las listas de tribunales, salas y asuntos, que antes estaban en `main.py`. Los campos de cada formulario en pantalla están en `web/src/lib/plantillas.ts`. Lo escrito se guarda en el navegador de ese equipo, por cuenta (`papiniano.redaccion.<id>` en localStorage): no se pierde al recargar ni al cambiar de sala, y no sale del equipo. «Empezar esta plantilla en blanco» lo borra. Si faltan campos obligatorios, se marcan en rojo con «Falta: …» y la pantalla va al primero.
  - **Página pública (antes de entrar), al estilo de clerk.do pero con la marca:** en `/` (`web/src/pages/inicio.tsx`): lo principal con un ejemplo de respuesta, qué lee (solo lo que de verdad está cargado), qué hay adentro, cómo funciona, planes, preguntas frecuentes, un último botón y el pie con columnas. **La entrada es otra página**, `/entrar` (`web/src/pages/entrada.tsx`); «Entrar» y «Empiece gratis» llevan allí, y Google vuelve allí si hay error. Los precios dicen [PRECIO] en `PLANES` hasta que el dueño los decida. No se nombran las obras comentadas de la Escuela Nacional de la Judicatura (licencia no comercial) hasta tener su permiso.
  - **Páginas legales:** `/terminos`, `/privacidad`, `/reembolso` y `/contacto` (`web/src/pages/legal.tsx`). Son **borradores**: falta el titular, el correo, el WhatsApp, la fecha y los días de reembolso (entre corchetes), y que los revise un abogado antes de cobrar.
  - **Escritorio sin caja de preguntas** (lo pidió el dueño el 11 nov): para preguntar se va directo al Asistente, por el menú o por el mosaico «Preguntar al asistente». La app de Flet todavía la tiene.
  - **El producto se llama Papiniano** (decidido el 11 nov, tras un análisis de competencia): igual que su asistente, una sola figura y un solo nombre. «Despacho» quedó atrás. En `NOMBRE_APP` (`web/src/lib/tema.ts` y `main.py`). El logo es el camafeo con el nombre (`web/src/components/logo.tsx`); el ícono de la pestaña es `web/public/favicon.svg`. Se descartaron Digesto y Toga (ya son software legal en Brasil, Bélgica e Italia) y Estrado («Estrados» existe). **Pendiente del dueño:** buscar «Papiniano» en ONAPI y registrarlo (clases 9 y 42), y reservar papiniano.do y .com.
  - **El asistente se llama Papiniano** (lo decidió el dueño el 11 nov), por Emilio Papiniano, el jurista más respetado de Roma. En la app nueva reemplaza a «Asistente» en el menú, en los títulos y en la página pública; la sala está en `/papiniano`. Su ícono (`web/src/components/papiniano.tsx`) es un camafeo: su perfil sin barba en marfil sobre vino, con corona de laurel, toga y borde de perlas doradas (lo eligió el dueño entre varios estilos), igual en todos los temas. La IA también se presenta como Papiniano (`jurisprudencia/ia.py`, también en la app de Flet).
  - **Revisión de diseño (11 nov):** borrar es rojo de verdad (`--destructive` #B42318, variante `peligro` del botón; el vino de la marca se confundía con el rojo); todo lo que se toca mide 44 px o más y los íconos tienen nombre para lectores de pantalla; tamaño de letra Normal / Grande / Muy grande (columna `usuarios.letra`, `/api/letra`; la página entera está en rem, así que basta cambiar la letra de `html`); renglones grises mientras carga (`cargando.tsx`); las respuestas de Papiniano en Literata; menos «Pronto» (la página pública muestra solo lo que funciona y una línea de lo que viene). Vista previa al compartir el enlace: `web/public/og.png` (1200×630) y `apple-touch-icon.png`; las etiquetas `og:` de `web/index.html` usan la dirección de Render: si cambia el dominio, cambiarlas.
  - **El escrito al lado de la conversación (12 nov):** si el abogado le pide un escrito a Papiniano («redácteme una instancia de…»), lo escribe en una hoja blanca tipo Word al lado del chat (desde 1200 px de ancho; más angosto, pestañas Conversación / Escrito) y lo cambia según lo que le pidan por el chat («quítele el segundo atendido»). Las consultas en esa misma conversación se contestan normal y no tocan el escrito; «agréguele eso al escrito» usa las sentencias de la consulta anterior.
    - **Cómo decide:** `preparar_busqueda` tiene el tipo `escrito` (redactar o cambiar el escrito abierto); `ia.escribir` devuelve JSON con el mensaje del chat y el escrito completo o cambios puntuales (buscar / poner). Si un «buscar» no está tal cual, se le pide el escrito completo.
    - **Dónde se guarda:** columna `conversaciones.escrito` (JSON con el texto y hasta 20 versiones para «Deshacer»). Rutas: `PUT /api/conversaciones/{id}/escrito` (corrección a mano), `POST …/escrito/deshacer` y `POST /api/escrito/{docx|pdf}`.
    - **Formato:** el escrito es texto simple; las mismas reglas lo dibujan en la hoja (`web/src/lib/escrito.ts`) y en el Word y el PDF (`generators/escrito.py`): título centrado, ATENDIDO: y PRIMERO: en negrita, firma centrada y junto a la fecha, número de página.
  - **Modelos de escritos (12 nov):** 26 modelos en `modelos/` (un `.txt` por modelo y su ficha en `catalogo.json`: grupo, materia, tribunal, cuándo se usa y palabras clave). Salen de escritos reales del departamento legal de Bienes Nacionales que dio el dueño, **sin ningún dato del caso** (nombres, cédulas, expedientes, parcelas, montos y sentencias citadas pasaron a datos por llenar) y escritos desde «su cliente», no desde el Estado. Las reglas para hacer más están en el informe de la sesión; la clave: mismo texto entre corchetes = mismo dato, y los del abogado son solo [NOMBRE/CÉDULA/MATRÍCULA/DOMICILIO PROFESIONAL/CIUDAD DEL ESTUDIO DEL ABOGADO].
    - **Papiniano los sugiere:** si le piden un escrito nuevo y hay modelos que sirven (`modelos.sugerir`: si el pedido dice el tipo —conclusiones, defensa, acto, carta…— el modelo tiene que ser de ese tipo), contesta con los modelos y los botones Ver / Usar este / Redactarlo sin modelo (`modelo: "ninguno"`). Si no hay ninguno, redacta como antes. También se eligen en el botón «Modelos» de la sala.
    - **Al usar uno** (`POST /api/asistente` con `modelo`): va a la hoja tal cual, sin la IA y sin contar como consulta, y se abren solos los «Datos por llenar», agrupados (tribunal, partes, inmueble, actos y fechas, otros, y los suyos). [FECHA DE HOY] la pone la app. Antes de descargar, si falta algo, avisa qué falta (antes avisaba después).
    - **Mis modelos:** el abogado sube su Word (.docx); `POST /api/modelos/leer` lo convierte sin guardarlo ni pasarlo por la IA y cambia solo cédulas, RNC, correos, teléfonos, montos y fechas; los nombres los marca él con «Convertir en dato». Se guarda en `modelos_propios` (solo lo ve él, hasta 100), clave `propio-<id>`, y Papiniano también lo sugiere.
    - **Que lo revise un abogado antes de anunciarlo:** citas de la Ley 3726 que ya reemplazó la Ley 2-23 (`recurso-casacion-civil`, `memorial-casacion-justiprecio`, y si este último sigue «libre de costas» por la Ley 1494); el art. 1676 del Código Civil (lesión) en `defensa-litis-nulidad-contrato` y `recurso-casacion-civil`; la Ley 317 (¿derogada por la 150-14?) en `conclusiones-justiprecio`; los «intereses legales» (Ley 183-02) en `demanda-rescision-contrato-desalojo`; los arts. 38 y 131 de la Ley 108-05 en `demanda-intervencion-voluntaria`; los arts. 28 a 30 en `conclusiones-intervencion-en-apelacion`; el art. 339 del Código de Procedimiento Civil en `acto-intervencion-forzosa-justiprecio`; el TERCERO de `conclusiones-apelacion-tierras` (antes se adhería al Abogado del Estado); y si proceden costas en `conclusiones-contencioso-administrativo`.
  - **La entrada nueva (12 nov):** foto real sin cara (Unsplash, de ergonofis, libre de uso: `web/public/entrada.webp`) con el tono de la marca, Papiniano en una burbuja de chat y campos blancos con borde marcado. Como el plan gratis de Render se duerme, a los 4 s dice «Despertando el servidor…» y reintenta solo (10 veces, cada 3 s) antes de dar error.
  - **Página pública (12 nov):** cifras reales redondeadas hacia abajo (`cifras` en `inicio.tsx`: más de 28.000 sentencias, más de 20 normas), «Cómo funciona» con una demostración animada (se ve una vez al llegar; sin movimiento si el sistema lo pide), qué lee por materia (Tierras, Laboral, Civil, Penal), «¿Por qué no ChatGPT?», «Su información» y el cierre con la foto de la entrada. El ejemplo laboral de la demostración (preaviso, cesantía, art. 80) conviene que lo lea un abogado.
    - **Datos por llenar (Ley 172-13):** Papiniano deja [NOMBRE DEL SOLICITANTE], [CÉDULA…] sin inventarlos; el abogado los llena en «Datos por llenar» y solo se ponen al descargar: no pasan por la IA y se guardan solo en el equipo (los del abogado, para todos sus escritos). Lo que queda vacío sale en amarillo en el Word.
    - En Redacción hay un acceso «Escrito libre con Papiniano». **Falta probarlo con la IA de verdad** (en local se probó con una IA de mentira).
  - **Colores:** salen de `temas.py`. `/api/sesion` manda los del tema de la persona y `web/src/lib/tema.ts` los pone en las variables `--t-*` de `web/src/index.css`.
  - **Letras:** Literata y Atkinson Hyperlegible desde npm (Fontsource), con negrita y cursiva de verdad.
  - **Render ya corre la app nueva desde el 11 nov** (deploy en vivo, conectada a la base real y con Google). Auto-Deploy está en «On Commit»: cada push a master despliega solo. Antes: Build `pip install -r requirements.txt` y Start `python main.py`.
  - **Cómo se hizo el cambio** (en el panel de Render, Settings del servicio):
    1. **Build Command:** `bash render-build.sh` (instala Python y arma las pantallas en `web/dist`; Render trae Node).
    2. **Start Command:** `uvicorn servidor:app --host 0.0.0.0 --port $PORT`.
    3. `NODE_VERSION` no hizo falta: el Node que trae Render armó las pantallas bien.
    4. Las demás variables quedan igual. Google Cloud no se toca: la vuelta sigue siendo `/oauth_callback`.
    5. **Para volver a Flet:** poner los comandos de antes, que están anotados arriba en `render.yaml`.
    6. Después, probar con la base real: Papiniano, la biblioteca, Redacción y la entrada con Google. Las sesiones de Flet no pasan a la app nueva: cada quien entra otra vez.
  - **La app de Flet (`main.py`) queda en el repo solo para volver atrás**; se puede borrar cuando la nueva esté probada.
  - **En local:** ver `web/README.md`. Vite va en el puerto 5180, porque el 5173 lo usa otro proyecto del dueño.
- **Lo que se descartó:** azul marino con dorado (es el estándar del sector y fue lo que no le gustó al dueño), el verde y la pizarra azul.

## Para vender con Lemon Squeezy

Revisado en su documentación (nov 2026): **República Dominicana puede cobrar a cuenta de banco** (o PayPal; mínimo US$50 por pago); aceptan **software por suscripción**, pero normalmente **no** "servicios": en el cuestionario se describe como software para abogados, no como asesoría legal. Comisión: 5 % + US$0,50 por cobro (más recargos según el caso). Aprobación en 2–3 días laborables.

Falta, en orden:
1. **Decidir precios y nombre** (los planes de la página dicen [PRECIO]).
2. **Página pública** con la marca nueva: qué es, salas, precios, y las páginas de **Términos, Privacidad (Ley 172-13), Reembolso y Contacto** (borradores para que los revise el abogado). Una **cuenta de demostración** por si la revisión quiere ver la app.
3. **El dueño:** cuenta y tienda en Lemon Squeezy, cuestionario, verificación de identidad, cuenta de banco, planes.
4. **Conectar los pagos:** botón "Elegir plan" → checkout con el correo del abogado; un *webhook* que reciba pagos, renovaciones y cancelaciones y cambie el plan de la cuenta (`prueba` → `activo` → `vencido`); enlace "Gestionar mi suscripción". Probar todo en modo de prueba.
5. **Publicar la pantalla de consentimiento de Google** (hoy solo entran los *test users*).
6. Cuando pague el primer cliente: Render de pago (~US$7/mes) para que no se duerma.

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
- **Sin `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`** la entrada no muestra el botón de Google (solo usuario y contraseña). Es normal en local; en Render sí aparece.

```bash
python cargar_boletines.py --mes 2025-05 --sin-vectores   # cargar un mes
python crear_usuario.py --admin                           # crear un usuario
python main.py                                            # abrir la app (puerto 8080)
```

## Cálculo de prestaciones laborales (`jurisprudencia/prestaciones.py`)
La IA calculaba mal las prestaciones (dividía entre 30, inventaba escalas, sumaba los 6 meses del art. 95 sin juicio).
Si la pregunta habla de despido/desahucio/prestaciones y trae salario y tiempo, la app calcula con las reglas fijas
del Código de Trabajo (arts. 76, 80, 177-182, 219-220; salario diario = mensual / 23.83) y le pasa el cálculo a la
IA, que solo lo explica. El art. 95 se menciona aparte, nunca se suma. Además, `ia.cifras_sin_respaldo` revisa que
cada "N días / meses / años" de una respuesta salga de las fuentes (si no, pide corregir una vez y si no, avisa).

