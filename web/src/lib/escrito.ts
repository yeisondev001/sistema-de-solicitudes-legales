/**
 * El escrito que Papiniano redacta al lado de la conversación es texto simple: párrafos separados por
 * una línea en blanco. Estas reglas le dan el formato en la hoja; son las mismas del Word y el PDF
 * (generators/escrito.py), así lo que se ve es lo que se descarga.
 */

export type TipoParrafo = 'titulo' | 'centro' | 'firma' | 'lineas' | 'normal'
export interface Parrafo {
  tipo: TipoParrafo
  lineas: string[]
}
export interface Pieza {
  texto: string
  negrita: boolean
  /** un dato por llenar: [NOMBRE DEL SOLICITANTE] */
  espacio: boolean
}

const ESPACIO = /\[([^[\]\n]{2,80})\]/g
const CLAVE = /^((?:[A-ZÁÉÍÓÚÜÑ]{2,} ?)+[:,])/
const MAYUSCULA = /[A-ZÁÉÍÓÚÜÑ]/
const MINUSCULA = /[a-záéíóúüñ]/

/** [NOMBRE DEL SOLICITANTE] es un dato por llenar; [2] o [ver nota] no */
const esEspacio = (dentro: string) => MAYUSCULA.test(dentro) && !MINUSCULA.test(dentro)

export function parrafos(texto: string): Parrafo[] {
  const bloques = texto.trim().split(/\n[ \t]*\n/).filter((b) => b.trim())
  return bloques.map((b, i) => {
    const lineas = b.split('\n').map((l) => l.trim()).filter(Boolean)
    const sola = lineas.length === 1 ? lineas[0] : ''
    const tipo: TipoParrafo =
      i === 0
        ? 'titulo'
        : sola && esEspacio(sola) && sola.length <= 100 && !sola.endsWith(':')
          ? 'centro'
          : i >= bloques.length - 2 && lineas.every((l) => l.length <= 60)
            ? 'firma'
            : lineas.length > 1 && lineas.every((l) => l.length <= 80)
              ? 'lineas'
              : 'normal'
    return { tipo, lineas }
  })
}

export function piezas(linea: string, negrita = false): Pieza[] {
  const salida: Pieza[] = []
  const m = negrita ? null : linea.match(CLAVE)
  if (m) {
    salida.push({ texto: m[1], negrita: true, espacio: false })
    linea = linea.slice(m[1].length)
  }
  let pos = 0
  for (const e of linea.matchAll(ESPACIO)) {
    if (!esEspacio(e[1])) continue
    salida.push({ texto: linea.slice(pos, e.index), negrita, espacio: false })
    salida.push({ texto: e[0], negrita, espacio: true })
    pos = e.index! + e[0].length
  }
  salida.push({ texto: linea.slice(pos), negrita, espacio: false })
  return salida.filter((p) => p.texto)
}

/** Los datos por llenar del escrito, sin repetir, en el orden en que aparecen: «NOMBRE DEL SOLICITANTE» */
export function espacios(texto: string): string[] {
  return [...new Set([...texto.matchAll(ESPACIO)].map((e) => e[1]).filter(esEspacio))]
}

/** El escrito con los datos que llenó el abogado (los que dejó en blanco quedan entre corchetes) */
export function llenar(texto: string, datos: Record<string, string>): string {
  return texto.replace(ESPACIO, (todo, dentro: string) => (esEspacio(dentro) && datos[dentro]?.trim()) || todo)
}

/** «NOMBRE DEL SOLICITANTE» → «Nombre del solicitante», para la etiqueta del campo */
export const etiqueta = (espacio: string) => espacio.charAt(0) + espacio.slice(1).toLowerCase()

/** El título del escrito para la barra: «Instancia en solicitud de…» (como el nombre del archivo) */
export function titulo(texto: string) {
  const primero = parrafos(texto)[0]
  const t = primero ? primero.lineas.join(' ').replace(/\s+/g, ' ') : ''
  if (!t) return 'Escrito'
  return esEspacio(t) ? t.charAt(0) + t.slice(1).toLowerCase() : t
}
