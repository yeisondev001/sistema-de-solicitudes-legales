/**
 * Prestaciones laborales con las reglas fijas del Código de Trabajo, para la calculadora pública.
 * Son las MISMAS reglas de jurisprudencia/prestaciones.py (la que usa Papiniano por dentro): si cambia una, cambiar
 * la otra. Aquí se calcula en el navegador, sin llamar al servidor.
 *
 *   salario diario   salario mensual / 23.83 (el que usa el Ministerio de Trabajo), redondeado a centavos
 *   preaviso   76    3 a 6 meses: 7 días; más de 6 meses hasta 1 año: 14; más de 1 año: 28
 *   cesantía   80    3 a 6 meses: 6 días; 6 meses a 1 año: 13; 1 a 5 años: 21 por año; 5 años o más: 23 por año;
 *                    la fracción de año mayor de 3 meses: 6 días (hasta 6 meses) o 13 (más de 6)
 *   vacaciones 180   escala del art. 180 sobre los meses del año en curso (más de 5 meses: 6 días … más de 11: 12)
 *   Navidad    219   la duodécima parte de lo ganado en el año calendario
 *
 * Según cómo terminó el contrato (verificado contra el Código de Trabajo, leyes/codigo-de-trabajo.pdf):
 *   desahucio del empleador (arts. 75 y 80)         preaviso + cesantía + vacaciones + Navidad
 *   despido injustificado (art. 95)                 lo mismo, y un tribunal puede sumar los salarios desde la demanda
 *                                                   hasta la sentencia, sin pasar de 6 meses (art. 95, ord. 3)
 *   dimisión justificada (arts. 97 y 101)           las mismas indemnizaciones del art. 95
 *   despido justificado (arts. 87 y 88)             solo vacaciones y Navidad
 *   dimisión injustificada (art. 102)               solo vacaciones y Navidad; el trabajador puede deber el preaviso
 *   renuncia sin causa (desahucio del trabajador)   solo vacaciones y Navidad; si no avisa, deberá el preaviso (art. 79)
 *   Navidad se paga «sea cual fuere la causa de la resolución» (art. 220).
 */

export type Motivo =
  | 'desahucio'
  | 'injustificado'
  | 'justificado'
  | 'dimision_justificada'
  | 'dimision_injustificada'
  | 'renuncia'

export const MOTIVOS: { valor: Motivo; texto: string; ayuda: string }[] = [
  {
    valor: 'desahucio',
    texto: 'La empresa terminó el contrato sin acusar al trabajador de nada',
    ayuda: 'Se llama desahucio: la empresa decide terminar el contrato sin alegar ninguna falta. Es el caso más común.',
  },
  {
    valor: 'injustificado',
    texto: 'La empresa lo despidió por una falta que no se pudo probar',
    ayuda: 'Despido injustificado: la empresa dijo que hubo una falta (por ejemplo, ausencias o robo), pero no logró demostrarla.',
  },
  {
    valor: 'justificado',
    texto: 'La empresa lo despidió por una falta que sí se probó',
    ayuda: 'Despido justificado: la falta está en la lista del art. 88 y la empresa la demostró. Es lo que decide, al final, un tribunal.',
  },
  {
    valor: 'dimision_justificada',
    texto: 'El trabajador renunció por una falta de la empresa (por ejemplo, no pagarle)',
    ayuda: 'Dimisión justificada: el trabajador se va por una causa del art. 97, como falta de pago del salario, y la prueba.',
  },
  {
    valor: 'dimision_injustificada',
    texto: 'El trabajador renunció culpando a la empresa, pero no pudo probarlo',
    ayuda: 'Dimisión injustificada: el trabajador alegó una causa del art. 97, pero un tribunal decide que no la demostró.',
  },
  {
    valor: 'renuncia',
    texto: 'El trabajador renunció por su cuenta, sin culpar a la empresa',
    ayuda: 'Renuncia sin causa: el trabajador decide irse sin alegar ninguna falta de la empresa.',
  },
]

export const DIAS_MES = 23.83

export type Periodo = 'mes' | 'quincena' | 'semana'

export interface Datos {
  salario: number // lo que gana en el período
  periodo: Periodo
  entrada: string // AAAA-MM-DD
  salida: string // AAAA-MM-DD
  tomoVacaciones: boolean // ya disfrutó las vacaciones del año en curso
  motivo?: Motivo // cómo terminó el contrato; sin ponerlo, desahucio
}

export interface Fila {
  concepto: string
  articulo: string
  dias: string
  monto: number
}

export interface Calculo {
  mensual: number
  diario: number
  meses: number // tiempo trabajado, en meses con fracción
  anios: number
  resto: number // meses después de los años cumplidos
  filas: Fila[]
  total: number
  sinPreaviso: boolean // menos de 3 meses
  mesesDelAnio: number
  vacacionesUltimoAnio: number // días del último año cumplido, por si no las disfrutó (arts. 177 y 182)
  motivo: Motivo
  /** lo que este motivo explica: por qué no corresponde algo, plazos y riesgos */
  notasMotivo: string[]
  /** montos posibles que NO suman al total (dependen de un tribunal o de lo que el trabajador deba) */
  posibles: { concepto: string; articulo: string; texto: string; monto: number }[]
  /** preaviso y cesantía corresponden al trabajador con este motivo */
  pagaIndemnizacion: boolean
}

const fecha = (iso: string) => {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d))
}

/** La misma fecha n meses después (el 31 de enero + 1 mes es el 28 o 29 de febrero) */
function sumarMeses(f: Date, n: number) {
  const total = f.getUTCMonth() + n
  const anio = f.getUTCFullYear() + Math.floor(total / 12)
  const mes = ((total % 12) + 12) % 12
  const ultimo = new Date(Date.UTC(anio, mes + 1, 0)).getUTCDate()
  return new Date(Date.UTC(anio, mes, Math.min(f.getUTCDate(), ultimo)))
}

/** Tiempo trabajado en meses: los meses completos más los días que sobran, a 30 por mes */
export function mesesEntre(entrada: string, salida: string) {
  const a = fecha(entrada)
  const b = fecha(salida)
  if (!(b > a)) return 0
  let meses = (b.getUTCFullYear() - a.getUTCFullYear()) * 12 + (b.getUTCMonth() - a.getUTCMonth())
  if (sumarMeses(a, meses) > b) meses--
  const dias = (b.getTime() - sumarMeses(a, meses).getTime()) / 86_400_000
  return meses + dias / 30
}

function escalaVacaciones(meses: number) {
  for (const [limite, dias] of [[11, 12], [10, 11], [9, 10], [8, 9], [7, 8], [6, 7], [5, 6]])
    if (meses > limite) return dias
  return 0
}

export function mensualDe(salario: number, periodo: Periodo) {
  return periodo === 'quincena' ? salario * 2 : periodo === 'semana' ? salario * 4.33 : salario
}

/** null si faltan datos o no cuadran */
export function calcular(d: Datos): Calculo | null {
  const mensual = mensualDe(d.salario, d.periodo)
  const meses = d.entrada && d.salida ? mesesEntre(d.entrada, d.salida) : 0
  if (!(mensual > 0) || !(meses > 0)) return null

  const diario = Math.round((mensual / DIAS_MES) * 100) / 100
  const anios = Math.floor(meses / 12)
  const resto = meses - 12 * anios

  let preaviso = 0
  let cesantia = 0
  if (meses >= 3) {
    preaviso = meses <= 6 ? 7 : meses <= 12 ? 14 : 28
    if (meses < 12) cesantia = meses <= 6 ? 6 : 13
    else cesantia = anios * (anios >= 5 ? 23 : 21) + (resto <= 3 ? 0 : resto <= 6 ? 6 : 13)
  }
  const motivo: Motivo = d.motivo ?? 'desahucio'
  // el trabajador cobra preaviso y cesantía cuando termina por el empleador sin causa probada o por una dimisión justificada
  const pagaIndemnizacion = motivo === 'desahucio' || motivo === 'injustificado' || motivo === 'dimision_justificada'
  const preavisoTeorico = preaviso * (Math.round((mensual / DIAS_MES) * 100) / 100)
  if (!pagaIndemnizacion) {
    preaviso = 0
    cesantia = 0
  }
  const vacaciones = d.tomoVacaciones ? 0 : escalaVacaciones(meses < 12 ? meses : resto)
  const salida = fecha(d.salida)
  const mesesDelAnio = Math.min(meses, salida.getUTCMonth() + salida.getUTCDate() / 30)
  const navidad = (mensual * mesesDelAnio) / 12

  const base = motivo === 'injustificado' ? 'art. 95' : motivo === 'dimision_justificada' ? 'art. 101' : null
  const noCorresponde = (articulo: string) => ({ dias: 'no corresponde', articulo })
  const notasMotivo: string[] = []
  const posibles: Calculo['posibles'] = []
  if (motivo === 'injustificado' || motivo === 'dimision_justificada') {
    posibles.push({
      concepto: 'Salarios desde la demanda hasta la sentencia',
      articulo: 'art. 95, ord. 3',
      texto: 'Si el caso llega a un tribunal y el empleador no prueba la causa, se suma el salario de ese tiempo, hasta un máximo de 6 meses.',
      monto: 6 * mensual,
    })
  }
  if (motivo === 'justificado')
    notasMotivo.push(
      'Con un despido justificado no corresponden preaviso ni cesantía. Pero la causa debe estar en el art. 88 y la prueba la tiene el empleador: si no la prueba, el despido es injustificado y sí se paga (arts. 87 y 95).',
    )
  if (motivo === 'dimision_justificada')
    notasMotivo.push(
      'Para que la dimisión sea justificada, la causa debe estar en el art. 97, se debe renunciar dentro de 15 días de que nació el derecho (art. 98) y comunicarla en 48 horas al empleador y al Departamento de Trabajo (art. 100). Si un tribunal la declara justificada, corresponden las mismas indemnizaciones del art. 95 (art. 101).',
    )
  if (motivo === 'dimision_injustificada') {
    notasMotivo.push('Con una dimisión injustificada no corresponden preaviso ni cesantía.')
    posibles.push({
      concepto: 'Lo que el trabajador puede deber al empleador',
      articulo: 'art. 102',
      texto: 'Si un tribunal declara injustificada la dimisión, condena al trabajador a pagar al empleador una indemnización igual al preaviso.',
      monto: preavisoTeorico,
    })
  }
  if (motivo === 'renuncia') {
    notasMotivo.push(
      'Quien renuncia sin causa no cobra preaviso ni cesantía: la cesantía es solo cuando el empleador ejerce el desahucio (art. 80).',
    )
    posibles.push({
      concepto: 'Si no dio el preaviso',
      articulo: 'arts. 75 a 79',
      texto: 'Quien renuncia debe avisar con el mismo plazo del preaviso; si no, el empleador puede reclamarle una indemnización equivalente.',
      monto: preavisoTeorico,
    })
  }

  const filas: Fila[] = [
    {
      concepto: 'Preaviso',
      ...(pagaIndemnizacion ? { articulo: base ? `${base} (remite al art. 76)` : 'art. 76', dias: `${preaviso} días` } : noCorresponde('art. 76')),
      monto: preaviso * diario,
    },
    {
      concepto: 'Auxilio de cesantía',
      ...(pagaIndemnizacion ? { articulo: base ? `${base} (remite al art. 80)` : 'art. 80', dias: `${cesantia} días` } : noCorresponde('art. 80')),
      monto: cesantia * diario,
    },
    { concepto: 'Vacaciones no disfrutadas', articulo: 'arts. 177, 180 y 182', dias: `${vacaciones} días`, monto: vacaciones * diario },
    {
      concepto: 'Regalía pascual (salario de Navidad)',
      articulo: 'arts. 219 y 220',
      dias: `${Number(mesesDelAnio.toFixed(1))} de 12 meses`,
      monto: navidad,
    },
  ]
  return {
    mensual,
    diario,
    meses,
    anios,
    resto,
    filas,
    total: filas.reduce((s, f) => s + f.monto, 0),
    sinPreaviso: meses < 3,
    mesesDelAnio,
    vacacionesUltimoAnio: meses >= 12 ? (anios >= 5 ? 18 : 14) : 0,
    motivo,
    notasMotivo,
    posibles,
    pagaIndemnizacion,
  }
}

export const pesos = (x: number) =>
  'RD$ ' + x.toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** "2 años y 3.5 meses" */
export function tiempoBonito(anios: number, resto: number) {
  const m = Number(resto.toFixed(1))
  const meses = `${m} ${m === 1 ? 'mes' : 'meses'}`
  if (!anios) return meses
  return `${anios} ${anios === 1 ? 'año' : 'años'}${m ? ` y ${meses}` : ''}`
}
