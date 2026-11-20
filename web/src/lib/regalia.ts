/**
 * Regalía pascual (salario de Navidad) para la calculadora pública (/calculadora-regalia-pascual).
 * Código de Trabajo: la duodécima parte del salario ordinario ganado en el año calendario (art. 219), en proporción al
 * tiempo trabajado si no trabajó todo el año (art. 220). Los meses del año se cuentan igual que en la calculadora de
 * prestaciones (lib/prestaciones.ts y jurisprudencia/prestaciones.py): así las dos dan lo mismo.
 */
import { mensualDe, mesesEntre, type Periodo } from './prestaciones'

export interface DatosRegalia {
  modo: 'salario' | 'total'
  salario: number // lo que gana en el período (modo «salario»)
  periodo: Periodo
  entrada: string // AAAA-MM-DD; vacío si ya trabajaba antes de este año
  salida: string // AAAA-MM-DD: hasta cuándo trabajó; vacío si sigue trabajando (cuenta hasta diciembre)
  totalAnual: number // modo «total»: lo ganado en el año, sin horas extra ni bonificación
  anio: number
}

export interface Regalia {
  monto: number
  meses: number // meses del año que cuentan (con fracción), en el modo «salario»
  mensual: number
}

export function calcularRegalia(d: DatosRegalia): Regalia | null {
  if (d.modo === 'total') {
    if (!(d.totalAnual > 0)) return null
    return { monto: d.totalAnual / 12, meses: 12, mensual: d.totalAnual / 12 }
  }
  const mensual = mensualDe(d.salario, d.periodo)
  if (!(mensual > 0)) return null
  const hasta = d.salida || `${d.anio}-12-31`
  const [, mes, dia] = hasta.split('-').map(Number)
  if (!mes || !dia) return null
  // los meses del año calendario hasta la salida (31 de diciembre cuenta como el año completo)
  let meses = Math.min(12, mes - 1 + dia / 30)
  // si entró este año, solo cuenta desde la entrada
  if (d.entrada && d.entrada > `${d.anio - 1}-12-31`) {
    if (!(hasta > d.entrada)) return null
    meses = Math.min(meses, mesesEntre(d.entrada, hasta))
  }
  return { monto: (mensual * meses) / 12, meses, mensual }
}
