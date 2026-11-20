import { useEffect, useMemo, useState } from 'react'
import { Campo, ENTRADA, SELECT } from '@/components/agenda'
import { Antetitulo, CabeceraPublica, PiePublico } from '@/components/publico'
import { Input } from '@/components/ui/input'
import { hoyIso } from '@/lib/fechas'
import { calcular, pesos, tiempoBonito, type Periodo } from '@/lib/prestaciones'
import { NOMBRE_APP } from '@/lib/tema'
import { useTitulo } from '@/lib/titulo'

/**
 * Calculadora pública de prestaciones laborales (/calculadora-prestaciones-laborales): gratis y sin cuenta, para traer
 * visitas desde Google. Calcula en el navegador con las mismas reglas que Papiniano por dentro (lib/prestaciones.ts).
 * El título y la descripción para Google los pone también el servidor (servidor.PAGINAS_PUBLICAS).
 */

const numero = (texto: string) => Number(texto.replace(/[^\d.]/g, ''))

export default function Calculadora() {
  useTitulo(`Calculadora de prestaciones laborales RD · ${NOMBRE_APP}`)
  useEffect(() => window.scrollTo(0, 0), [])

  const [salario, setSalario] = useState('')
  const [periodo, setPeriodo] = useState<Periodo>('mes')
  const [entrada, setEntrada] = useState('')
  const [salida, setSalida] = useState(hoyIso())
  const [tomoVacaciones, setTomoVacaciones] = useState(false)

  const calculo = useMemo(
    () => calcular({ salario: numero(salario), periodo, entrada, salida, tomoVacaciones }),
    [salario, periodo, entrada, salida, tomoVacaciones],
  )
  const fechasAlReves = Boolean(entrada && salida && salida <= entrada)

  return (
    <div className="min-h-dvh bg-background text-ink">
      <CabeceraPublica />
      <main className="mx-auto max-w-[1100px] px-5 py-10 md:px-6 md:py-14">
        <div className="max-w-[760px] space-y-3">
          <Antetitulo>GRATIS · CÓDIGO DE TRABAJO DOMINICANO</Antetitulo>
          <h1 className="font-heading text-[2.3rem] leading-tight font-medium md:text-[2.8rem]">
            Calculadora de prestaciones laborales
          </h1>
          <p className="text-[1.1rem] leading-relaxed text-ink-soft">
            Calcule el preaviso, la cesantía, las vacaciones y la regalía pascual (salario de Navidad) de un trabajador al
            que le hicieron desahucio o lo despidieron sin causa justificada, con las fórmulas del Código de Trabajo de la
            República Dominicana.
          </p>
        </div>

        <div className="mt-10 grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          {/* los datos */}
          <form
            aria-label="Datos del trabajador"
            onSubmit={(e) => e.preventDefault()}
            className="space-y-5 rounded-2xl border border-papel-borde bg-card p-6 md:p-7"
          >
            <div className="grid grid-cols-[1fr_auto] items-end gap-3">
              <Campo id="calc-salario" etiqueta="Salario">
                <Input
                  id="calc-salario"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="Ej.: 45,000"
                  value={salario}
                  onChange={(e) => setSalario(e.target.value)}
                  className={ENTRADA}
                />
              </Campo>
              <label htmlFor="calc-periodo" className="sr-only">Cada cuánto cobra</label>
              <select id="calc-periodo" value={periodo} onChange={(e) => setPeriodo(e.target.value as Periodo)} className={SELECT}>
                <option value="mes">al mes</option>
                <option value="quincena">por quincena</option>
                <option value="semana">por semana</option>
              </select>
            </div>
            <Campo id="calc-entrada" etiqueta="Fecha en que empezó a trabajar">
              <Input id="calc-entrada" type="date" value={entrada} max={salida || undefined} onChange={(e) => setEntrada(e.target.value)} className={ENTRADA} />
            </Campo>
            <Campo id="calc-salida" etiqueta="Fecha en que terminó el contrato">
              <Input id="calc-salida" type="date" value={salida} onChange={(e) => setSalida(e.target.value)} className={ENTRADA} />
            </Campo>
            <label className="flex cursor-pointer items-start gap-3 text-[1rem]">
              <input
                type="checkbox"
                checked={tomoVacaciones}
                onChange={(e) => setTomoVacaciones(e.target.checked)}
                className="mt-1 size-5 shrink-0 accent-[var(--color-marca)]"
              />
              Ya disfrutó sus vacaciones de este año
            </label>
            <p className="text-[0.88rem] leading-relaxed text-ink-soft">
              Si el salario variaba (comisiones, horas extra), ponga el promedio mensual del último año.
            </p>
          </form>

          {/* el resultado */}
          <section aria-live="polite" aria-label="Resultado" className="rounded-2xl border border-papel-borde bg-papel p-5 md:p-7">
            {!calculo ? (
              <p className="py-10 text-center text-[1.05rem] text-ink-soft">
                {fechasAlReves
                  ? 'La fecha en que terminó debe ser después de la fecha en que empezó.'
                  : 'Ponga el salario y las dos fechas para ver el cálculo.'}
              </p>
            ) : (
              <div className="space-y-5">
                <dl className="grid gap-x-6 gap-y-1 text-[0.98rem] sm:grid-cols-2">
                  <div>
                    <dt className="text-ink-soft">Tiempo trabajado</dt>
                    <dd className="font-bold">{tiempoBonito(calculo.anios, calculo.resto)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-soft">Salario diario ({pesos(calculo.mensual)} ÷ 23.83)</dt>
                    <dd className="font-bold">{pesos(calculo.diario)}</dd>
                  </div>
                </dl>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[0.98rem]">
                    <thead>
                      <tr className="border-b border-regla text-[0.85rem] text-ink-soft">
                        <th className="py-2 pr-3 font-semibold">Concepto</th>
                        <th className="py-2 text-right font-semibold">Monto</th>
                      </tr>
                    </thead>
                    <tbody>
                      {calculo.filas.map((f) => (
                        <tr key={f.concepto} className="border-b border-papel-borde">
                          <td className="py-2.5 pr-3">
                            {f.concepto}
                            {/* los días van debajo y no en otra columna: así la tabla cabe en el celular */}
                            <span className="block text-[0.85rem] text-ink-soft">
                              {f.dias} · {f.articulo}
                            </span>
                          </td>
                          <td className="py-2.5 text-right align-top whitespace-nowrap tabular-nums">{pesos(f.monto)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr>
                        <td className="pt-4 text-[1.1rem] font-bold">Total</td>
                        <td className="pt-4 text-right font-heading text-[1.3rem] font-semibold sm:text-[1.6rem] whitespace-nowrap text-marca-texto tabular-nums">
                          {pesos(calculo.total)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
                <ul className="list-disc space-y-1.5 pl-5 text-[0.9rem] leading-relaxed text-ink-soft">
                  {calculo.sinPreaviso && <li>Con menos de 3 meses de trabajo no corresponden preaviso ni cesantía (arts. 76 y 80).</li>}
                  <li>
                    El preaviso y la cesantía se pagan dentro de 10 días. Si no, el empleador debe además un día de salario
                    ({pesos(calculo.diario)}) por cada día de retraso (art. 86).
                  </li>
                  {calculo.vacacionesUltimoAnio > 0 && (
                    <li>
                      Si tampoco disfrutó las vacaciones del último año completo, se suman {calculo.vacacionesUltimoAnio} días
                      más ({pesos(calculo.vacacionesUltimoAnio * calculo.diario)}) (arts. 177 y 182).
                    </li>
                  )}
                  <li>
                    La regalía pascual (salario de Navidad) no puede pasar de cinco salarios mínimos (art. 219). ¿Solo la
                    regalía? Use la{' '}
                    <a href="/calculadora-regalia-pascual" className="font-semibold text-marca-texto underline">calculadora de regalía pascual</a>.
                  </li>
                  <li>
                    No incluye la indemnización del art. 95 (hasta 6 meses de salario, solo si un tribunal declara
                    injustificado el despido) ni la participación en los beneficios de la empresa.
                  </li>
                </ul>
                <p className="border-t border-papel-borde pt-4 text-[0.85rem] text-ink-soft">
                  Cálculo orientativo con las fórmulas del Código de Trabajo. No sustituye la asesoría de un abogado.
                </p>
              </div>
            )}
          </section>
        </div>

        {/* para el abogado que llega buscando la calculadora */}
        <section className="mt-12 flex flex-col items-start justify-between gap-5 rounded-2xl bg-panel px-7 py-8 text-sobre-panel md:flex-row md:items-center md:px-10">
          <div className="max-w-[620px] space-y-2">
            <h2 className="font-heading text-[1.6rem] leading-tight font-medium">¿Es abogado?</h2>
            <p className="text-[1.02rem] text-nav">
              {NOMBRE_APP} hace este cálculo dentro de la conversación, le busca las sentencias de la Suprema Corte sobre el
              caso y le redacta el escrito en Word.
            </p>
          </div>
          <a href="/#planes" className="shrink-0 rounded-lg bg-card px-6 py-4 text-[1.05rem] font-bold text-marca-texto hover:bg-background">
            Pruébelo 5 días gratis
          </a>
        </section>

        {/* la explicación: para quien quiere entender el cálculo, y para que Google sepa de qué trata la página */}
        <article className="lectura mt-14 max-w-[760px] text-[1.02rem] [&_h2]:mt-10 [&_h2]:text-[1.45rem] [&_h3]:mt-6 [&_h3]:text-[1.15rem]">
          <h2>Cómo se calculan las prestaciones laborales en República Dominicana</h2>
          <p>
            Cuando el empleador termina un contrato por tiempo indefinido sin una causa justificada (desahucio o despido
            injustificado), el trabajador tiene derecho al preaviso y al auxilio de cesantía, además de las vacaciones que
            no disfrutó y la parte que le toca de la regalía pascual. Todo se calcula a partir del salario diario.
          </p>
          <h3>Salario diario</h3>
          <p>
            Es el salario mensual dividido entre 23.83, el promedio de días laborables del mes que usa el Ministerio de
            Trabajo. Si el salario es por quincena, se multiplica por 2 para llevarlo al mes; si es por semana, por 4.33.
          </p>
          <h3>Preaviso (art. 76)</h3>
          <p>
            De 3 a 6 meses de trabajo, 7 días de salario; de más de 6 meses hasta un año, 14 días; de más de un año, 28 días.
          </p>
          <h3>Auxilio de cesantía (art. 80)</h3>
          <p>
            De 3 a 6 meses, 6 días; de 6 meses a un año, 13 días; de uno a cinco años, 21 días por cada año; de cinco años
            en adelante, 23 días por cada año. La fracción de año de más de 3 meses suma 6 días si es de hasta 6 meses y 13
            días si pasa de 6.
          </p>
          <h3>Vacaciones no disfrutadas (arts. 177, 180 y 182)</h3>
          <p>
            Si el trabajador no las tomó, se pagan. Para el año en curso se usa la escala del art. 180: con más de 5 meses,
            6 días; con más de 6, 7 días; y así hasta 12 días con más de 11 meses.
          </p>
          <h3>Regalía pascual o salario de Navidad (arts. 219 y 220)</h3>
          <p>
            La regalía pascual, que el Código llama salario de Navidad, es la duodécima parte de lo ganado en el año calendario. Si el contrato termina antes de diciembre, se paga la
            parte proporcional a los meses trabajados en el año.
          </p>
          <h3>Cuándo cambia el cálculo</h3>
          <p>
            Este cálculo es para contratos por tiempo indefinido que terminan por desahucio o despido sin causa. Si el
            contrato era por cierto tiempo o para una obra, o si el caso está en un tribunal, el monto puede ser otro:
            consulte a un abogado.
          </p>
        </article>
      </main>
      <PiePublico />
    </div>
  )
}
