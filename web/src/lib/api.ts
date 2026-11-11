import type { Turno } from './tipos'

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
  borrar: <T>(ruta: string) => pedir<T>(ruta, { method: 'DELETE' }),
}

/**
 * Le pregunta al asistente. El servidor contesta por partes (una línea JSON por evento):
 * los avances («Buscando en las sentencias…») y al final la respuesta con la conversación guardada.
 */
export async function preguntarAlAsistente(
  texto: string,
  convId: number | null,
  alAvanzar: (texto: string) => void,
): Promise<{ turno: Turno; conv_id: number | null }> {
  let r: Response
  try {
    r = await fetch('/api/asistente', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto, conv_id: convId }),
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
      if (evento.avance) alAvanzar(evento.avance)
      if (evento.turno) return evento
    }
  }
  throw new ErrorApi('La respuesta se cortó. Intente de nuevo.', 0)
}

/** Sube un PDF o Word a la parte del buscador de la persona */
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
