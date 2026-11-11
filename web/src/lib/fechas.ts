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
