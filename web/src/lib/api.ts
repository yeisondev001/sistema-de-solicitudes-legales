import type { Escrito, Turno } from './tipos'

/** Error con el mensaje que mandó el servidor (ya en palabras para el abogado) */
export class ErrorApi extends Error {
  estado: number
  constructor(mensaje: string, estado: number) {
    super(mensaje)
    this.estado = estado
  }
}

/** Avisa a la app que la sesión terminó (para volver a la entrada) */
export const SESION_TERMINADA = 'sesion-terminada'

async function respuesta(r: Response, ruta: string) {
  if (r.ok) return r
  let detalle = 'No se pudo conectar con el servidor. Intente en un momento.'
  try {
    const d = await r.json()
    if (typeof d.detail === 'string') detalle = d.detail
  } catch {
    // sin cuerpo JSON: queda el mensaje general
  }
  if (r.status === 401 && ruta !== '/api/entrar') window.dispatchEvent(new Event(SESION_TERMINADA))
  throw new ErrorApi(detalle, r.status)
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  let r: Response
  try {
    r = await fetch(ruta, {
      credentials: 'same-origin',
      ...opciones,
      headers: opciones.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ErrorApi('No hay conexión con el servidor. Revise su internet.', 0)
  }
  return (await respuesta(r, ruta)).json()
}

export const api = {
  get: <T>(ruta: string) => pedir<T>(ruta),
  post: <T>(ruta: string, datos?: unknown) =>
    pedir<T>(ruta, { method: 'POST', body: datos === undefined ? undefined : JSON.stringify(datos) }),
  put: <T>(ruta: string, datos: unknown) => pedir<T>(ruta, { method: 'PUT', body: JSON.stringify(datos) }),
  patch: <T>(ruta: string, datos: unknown) => pedir<T>(ruta, { method: 'PATCH', body: JSON.stringify(datos) }),
  borrar: <T>(ruta: string) => pedir<T>(ruta, { method: 'DELETE' }),
}

/**
 * Le pregunta al asistente. El servidor contesta por partes (una línea JSON por evento):
 * los avances («Buscando en las sentencias…», con escrito: true si está escribiendo el escrito) y al final
 * la respuesta con la conversación guardada (y el escrito, si lo escribió o lo cambió).
 */
export async function preguntarAlAsistente(
  texto: string,
  convId: number | null,
  alAvanzar: (texto: string, escrito: boolean) => void,
  /** el modelo que eligió para el escrito; «ninguno» si lo quiere sin modelo */
  modelo?: string,
  /** en una conversación nueva: el expediente donde queda guardada */
  expedienteId?: number,
): Promise<{ turno: Turno; conv_id: number | null; escrito?: Escrito }> {
  let r: Response
  try {
    r = await fetch('/api/asistente', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto, conv_id: convId, modelo, expediente_id: expedienteId }),
    })
  } catch {
    throw new ErrorApi('No hay conexión con el servidor. Revise su internet.', 0)
  }
  await respuesta(r, '/api/asistente')
  const lector = r.body!.pipeThrough(new TextDecoderStream()).getReader()
  let resto = ''
  for (;;) {
    const { value, done } = await lector.read()
    if (done) break
    resto += value
    const lineas = resto.split('\n')
    resto = lineas.pop() ?? ''
    for (const linea of lineas) {
      if (!linea.trim()) continue
      const evento = JSON.parse(linea)
      if (evento.avance) alAvanzar(evento.avance, Boolean(evento.escrito))
      if (evento.turno) return evento
    }
  }
  throw new ErrorApi('La respuesta se cortó. Intente de nuevo.', 0)
}

/**
 * Pide un documento (Word o PDF) y lo descarga con el nombre que puso el servidor.
 * Con cuerpo es un POST (las plantillas); sin cuerpo, un GET (el historial en Word).
 * Devuelve los encabezados, por si traen algo más (X-Historial).
 */
export async function descargar(ruta: string, cuerpo?: unknown): Promise<Headers> {
  let r: Response
  try {
    r = await fetch(ruta, {
      method: cuerpo === undefined ? 'GET' : 'POST',
      credentials: 'same-origin',
      headers: cuerpo === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    })
  } catch {
    throw new ErrorApi('No hay conexión con el servidor. Revise su internet.', 0)
  }
  await respuesta(r, ruta)
  const nombre = decodeURIComponent(r.headers.get('X-Nombre') ?? 'documento')
  const url = URL.createObjectURL(await r.blob())
  const enlace = Object.assign(document.createElement('a'), { href: url, download: nombre })
  document.body.append(enlace)
  enlace.click()
  enlace.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30_000)
  return r.headers
}

/** Sube un PDF o Word a la parte del buscador de la persona */
/** El Word de un modelo propio convertido en texto (sin guardarlo): ya trae cambiados los datos que se reconocen */
export async function leerModelo(archivo: File): Promise<{ nombre: string; texto: string; cambios: number }> {
  let r: Response
  try {
    r = await fetch('/api/modelos/leer', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Nombre': encodeURIComponent(archivo.name), 'Content-Type': 'application/octet-stream' },
      body: archivo,
    })
  } catch {
    throw new ErrorApi(`«${archivo.name}» no se pudo subir: revise su internet.`, 0)
  }
  return (await respuesta(r, '/api/modelos/leer')).json()
}

export async function subirDocumento(archivo: File): Promise<{ titulo: string; numero: string; paginas: number }> {
  let r: Response
  try {
    r = await fetch('/api/documentos', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Nombre': encodeURIComponent(archivo.name), 'Content-Type': 'application/octet-stream' },
      body: archivo,
    })
  } catch {
    throw new ErrorApi(`«${archivo.name}» no se pudo subir: revise su internet.`, 0)
  }
  return (await respuesta(r, '/api/documentos')).json()
}

/** Lo que devuelve la sala Redacción al leer el documento: el texto ya sin los datos de las personas */
export interface DocumentoLeido {
  nombre: string
  texto: string
  /** «PERSONA 1» → el nombre real; vuelve solo a este navegador y nunca va a la IA */
  mapa: Record<string, string>
  /** cuántos datos de cada tipo se quitaron */
  cuenta: Record<string, number>
}

/** Lee el PDF o Word de la otra parte y le quita los datos de las personas (sin guardarlo ni usar la IA) */
export async function leerParaRedactar(archivo: File): Promise<DocumentoLeido> {
  let r: Response
  try {
    r = await fetch('/api/redactar/leer', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Nombre': encodeURIComponent(archivo.name), 'Content-Type': 'application/octet-stream' },
      body: archivo,
    })
  } catch {
    throw new ErrorApi(`«${archivo.name}» no se pudo subir: revise su internet.`, 0)
  }
  return (await respuesta(r, '/api/redactar/leer')).json()
}

/** Papiniano redacta a partir del documento: avisa los avances y devuelve la conversación con el escrito */
export async function redactarEscrito(
  datos:
    | { tipo: string; modo?: 'documento'; texto: string; nombre: string; indicaciones: string }
    | { tipo: string; modo: 'propio'; respuestas: Record<string, string>; modelo: string | null },
  alAvanzar: (texto: string) => void,
): Promise<{ conv_id: number; mapa?: Record<string, string> }> {
  let r: Response
  try {
    r = await fetch('/api/redactar', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    })
  } catch {
    throw new ErrorApi('No hay conexión con el servidor. Revise su internet.', 0)
  }
  await respuesta(r, '/api/redactar')
  const lector = r.body!.pipeThrough(new TextDecoderStream()).getReader()
  let resto = ''
  for (;;) {
    const { value, done } = await lector.read()
    if (done) break
    resto += value
    const lineas = resto.split('\n')
    resto = lineas.pop() ?? ''
    for (const linea of lineas) {
      if (!linea.trim()) continue
      const evento = JSON.parse(linea)
      if (evento.avance) alAvanzar(evento.avance)
      if (evento.error) throw new ErrorApi(evento.error, 0)
      if (evento.conv_id) return evento as { conv_id: number; mapa?: Record<string, string> }
    }
  }
  throw new ErrorApi('La respuesta se cortó. Intente de nuevo.', 0)
}
