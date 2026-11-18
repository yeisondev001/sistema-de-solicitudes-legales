// Fechas con la hora de República Dominicana (no cambia en verano), sea cual sea la del equipo
const ZONA = 'America/Santo_Domingo'

function partes(fecha: Date) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('es-DO', { timeZone: ZONA, hour: 'numeric', hourCycle: 'h23', day: 'numeric', month: 'numeric', year: 'numeric' })
      .formatToParts(fecha)
      .map((x) => [x.type, x.value]),
  )
  return { hora: Number(p.hour), dia: `${p.year}-${p.month}-${p.day}` }
}

/** «miércoles, 11 de noviembre» */
export function fechaDeHoy() {
  return new Intl.DateTimeFormat('es-DO', { timeZone: ZONA, weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
}

/** «12 de noviembre de 2026», para la fecha de un escrito */
export function fechaLarga() {
  return new Intl.DateTimeFormat('es-DO', { timeZone: ZONA, day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())
}

export function saludo() {
  const { hora } = partes(new Date())
  return hora < 12 ? 'Buenos días' : hora < 19 ? 'Buenas tardes' : 'Buenas noches'
}

/** Cuándo se tocó una conversación: «hoy, 11:47 a. m.», «ayer», «8 de noviembre» */
export function cuando(segundos: number) {
  const fecha = new Date(segundos * 1000)
  const ahora = new Date()
  const hoy = partes(ahora).dia
  const ayer = partes(new Date(ahora.getTime() - 86400000)).dia
  const dia = partes(fecha).dia
  const hora = new Intl.DateTimeFormat('es-DO', { timeZone: ZONA, hour: 'numeric', minute: '2-digit' }).format(fecha)
  if (dia === hoy) return `hoy, ${hora}`
  if (dia === ayer) return `ayer, ${hora}`
  return new Intl.DateTimeFormat('es-DO', { timeZone: ZONA, day: 'numeric', month: 'long' }).format(fecha)
}

// ── Las fechas de la agenda (AAAA-MM-DD): son días del calendario, sin hora ni zona ──
function aDia(iso: string) {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d))
}
const formato = (opciones: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('es-DO', { timeZone: 'UTC', ...opciones })

/** Hoy en República Dominicana: «2026-11-18» */
export function hoyIso() {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', { timeZone: ZONA, year: 'numeric', month: '2-digit', day: '2-digit' })
      .formatToParts(new Date())
      .map((x) => [x.type, x.value]),
  )
  return `${p.year}-${p.month}-${p.day}`
}

export function sumarDias(iso: string, dias: number) {
  const f = aDia(iso)
  f.setUTCDate(f.getUTCDate() + dias)
  return f.toISOString().slice(0, 10)
}

/** Días que faltan (negativo: ya pasó) */
export function diasPara(iso: string) {
  return Math.round((aDia(iso).getTime() - aDia(hoyIso()).getTime()) / 86400000)
}

/** «jueves 19 de noviembre» */
export function diaLargo(iso: string) {
  return formato({ weekday: 'long', day: 'numeric', month: 'long' }).format(aDia(iso)).replace(',', '')
}

/** El número del día y el mes corto, para la cajita del calendario: ['19', 'nov'] */
export function diaYMes(iso: string): [string, string] {
  return [String(aDia(iso).getUTCDate()), formato({ month: 'short' }).format(aDia(iso)).replace('.', '')]
}

/** «noviembre de 2026» */
export function mesLargo(iso: string) {
  return formato({ month: 'long', year: 'numeric' }).format(aDia(iso))
}

/** «Hoy», «Mañana», «En 3 días», «Ayer», «Hace 5 días» */
export function cuandoEs(iso: string) {
  const n = diasPara(iso)
  if (n === 0) return 'Hoy'
  if (n === 1) return 'Mañana'
  if (n === -1) return 'Ayer'
  return n > 0 ? `En ${n} días` : `Hace ${-n} días`
}

/** «9:00 a. m.» (vacía si es para todo el día) */
export function horaBonita(hhmm: string) {
  if (!hhmm) return ''
  const [h, m] = hhmm.split(':').map(Number)
  return formato({ hour: 'numeric', minute: '2-digit' }).format(new Date(Date.UTC(2000, 0, 1, h, m)))
}
