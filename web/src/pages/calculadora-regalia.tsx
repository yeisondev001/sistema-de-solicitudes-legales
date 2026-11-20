import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Campo, ENTRADA, SELECT } from '@/components/agenda'
import { Antetitulo, CabeceraPublica, PiePublico } from '@/components/publico'
import { Input } from '@/components/ui/input'
import { pesos, type Periodo } from '@/lib/prestaciones'
import { calcularRegalia } from '@/lib/regalia'
import { NOMBRE_APP } from '@/lib/tema'
import { useTitulo } from '@/lib/titulo'

/**
 * Calculadora pública de regalía pascual (/calculadora-regalia-pascual): gratis y sin cuenta. La buscan muchísimo en
 * noviembre y diciembre. Calcula en el navegador (lib/regalia.ts), con los arts. 219 a 222 del Código de Trabajo.
 * El título y la descripción para Google los pone también el servidor (servidor.PAGINAS_PUBLICAS).
 */

const numero = (texto: string) => Number(texto.replace(/[^\d.]/g, ''))
const ANIO = new Date().getFullYear()

export default function CalculadoraRegalia() {
  useTitulo(`Calculadora de regalía pascual RD · ${NOMBRE_APP}`)
  useEffect(() => window.scrollTo(0, 0), [])

  const [modo, setModo] = useState<'salario' | 'total'>('salario')
  const [salario, setSalario] = useState('')
  const [periodo, setPeriodo] = useState<Periodo>('mes')
  const [entroEsteAnio, setEntroEsteAnio] = useState(false)
  const [entrada, setEntrada] = useState('')
  const [salio, setSalio] = useState(false)
  const [salida, setSalida] = useState('')
  const [total, setTotal] = useState('')

  const r = useMemo(
    () =>
      calcularRegalia({
        modo,
        salario: numero(salario),
        periodo,
        entrada: entroEsteAnio ? entrada : '',
        salida: salio ? salida : '',
        totalAnual: numero(total),
        anio: ANIO,
      }),
    [modo, salario, periodo, entroEsteAnio, entrada, salio, salida, total],
  )

  const opcion = (valor: 'salario' | 'total', texto: string) => (
    <button
      type="button"
      onClick={() => setModo(valor)}
      aria-pressed={modo === valor}
      className={
        modo === valor
          ? 'rounded-lg bg-panel px-4 py-2.5 font-bold text-sobre-panel'
          : 'rounded-lg border border-papel-borde bg-background px-4 py-2.5 font-semibold text-ink hover:border-marca'
      }
    >
      {texto}
    </button>
  )

  return (
    <div className="min-h-dvh bg-background text-ink">
      <CabeceraPublica />
      <main className="mx-auto max-w-[1100px] px-5 py-10 md:px-6 md:py-14">
        <div className="max-w-[760px] space-y-3">
          <Antetitulo>GRATIS · CÓDIGO DE TRABAJO DOMINICANO</Antetitulo>
          <h1 className="font-heading text-[2.3rem] leading-tight font-medium md:text-[2.8rem]">
            Calculadora de regalía pascual
          </h1>
          <p className="text-[1.1rem] leading-relaxed text-ink-soft">
            Calcule su regalía pascual (el salario de Navidad) {ANIO}: la doceava parte de lo que ganó en el año, según el
            Código de Trabajo de la República Dominicana. Se paga a más tardar el 20 de diciembre.
          </p>
        </div>

        <div className="mt-10 grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <form aria-label="Datos para la regalía" onSubmit={(e) => e.preventDefault()} className="space-y-5 rounded-2xl border border-papel-borde bg-card p-6 md:p-7">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Cómo calcular">
              {opcion('salario', 'Con mi salario')}
              {opcion('total', 'Con lo ganado en el año')}
            </div>

            {modo === 'salario' ? (
              <>
                <div className="grid grid-cols-[1fr_auto] items-end gap-3">
                  <Campo id="reg-salario" etiqueta="Salario">
                    <Input id="reg-salario" inputMode="decimal" autoComplete="off" placeholder="Ej.: 35,000" value={salario} onChange={(e) => setSalario(e.target.value)} className={ENTRADA} />
                  </Campo>
                  <label htmlFor="reg-periodo" className="sr-only">Cada cuánto cobra</label>
                  <select id="reg-periodo" value={periodo} onChange={(e) => setPeriodo(e.target.value as Periodo)} className={SELECT}>
                    <option value="mes">al mes</option>
                    <option value="quincena">por quincena</option>
                    <option value="semana">por semana</option>
                  </select>
                </div>
                <label className="flex cursor-pointer items-start gap-3 text-[1rem]">
                  <input type="checkbox" checked={entroEsteAnio} onChange={(e) => setEntroEsteAnio(e.target.checked)} className="mt-1 size-5 shrink-0 accent-[var(--color-marca)]" />
                  Empecé a trabajar en {ANIO}
                </label>
                {entroEsteAnio && (
                  <Campo id="reg-entrada" etiqueta="Fecha en que empezó">
                    <Input id="reg-entrada" type="date" min={`${ANIO}-01-01`} max={`${ANIO}-12-31`} value={entrada} onChange={(e) => setEntrada(e.target.value)} className={ENTRADA} />
                  </Campo>
                )}
                <label className="flex cursor-pointer items-start gap-3 text-[1rem]">
                  <input type="checkbox" checked={salio} onChange={(e) => setSalio(e.target.checked)} className="mt-1 size-5 shrink-0 accent-[var(--color-marca)]" />
                  Ya no trabajo ahí (terminó el contrato este año)
                </label>
                {salio && (
                  <Campo id="reg-salida" etiqueta="Fecha en que terminó">
                    <Input id="reg-salida" type="date" min={`${ANIO}-01-01`} max={`${ANIO}-12-31`} value={salida} onChange={(e) => setSalida(e.target.value)} className={ENTRADA} />
                  </Campo>
                )}
                <p className="text-[0.88rem] leading-relaxed text-ink-soft">
                  Si su salario cambió durante el año, use «Con lo ganado en el año»: es más exacto.
                </p>
              </>
            ) : (
              <>
                <Campo id="reg-total" etiqueta={`Lo que ganó en ${ANIO} (salario ordinario)`}>
                  <Input id="reg-total" inputMode="decimal" autoComplete="off" placeholder="Ej.: 420,000" value={total} onChange={(e) => setTotal(e.target.value)} className={ENTRADA} />
                </Campo>
                <p className="text-[0.88rem] leading-relaxed text-ink-soft">
                  Sume solo el salario ordinario: sin horas extra ni la bonificación (participación en los beneficios),
                  que no cuentan para la regalía (art. 219).
                </p>
              </>
            )}
          </form>

          <section aria-live="polite" aria-label="Resultado" className="rounded-2xl border border-papel-borde bg-papel p-5 md:p-7">
            {!r ? (
              <p className="py-10 text-center text-[1.05rem] text-ink-soft">
                {modo === 'salario' ? 'Ponga su salario para ver su regalía.' : 'Ponga lo que ganó en el año para ver su regalía.'}
              </p>
            ) : (
              <div className="space-y-5">
                <div>
                  <p className="text-ink-soft">Su regalía pascual {ANIO}</p>
                  <p className="font-heading text-[2.4rem] leading-tight font-semibold text-marca-texto tabular-nums">{pesos(r.monto)}</p>
                </div>
                <p className="text-[0.98rem] leading-relaxed">
                  {modo === 'total' ? (
                    <>Lo ganado en el año ÷ 12 = {pesos(r.monto)}.</>
                  ) : r.meses >= 12 ? (
                    <>Trabajó el año completo: la regalía es igual a un salario mensual ({pesos(r.mensual)}).</>
                  ) : (
                    <>
                      {pesos(r.mensual)} × {String(Number(r.meses.toFixed(1)))} meses trabajados ÷ 12 = {pesos(r.monto)}.
                    </>
                  )}
                </p>
                <ul className="list-disc space-y-1.5 pl-5 text-[0.9rem] leading-relaxed text-ink-soft">
                  <li>Se paga a más tardar el 20 de diciembre, aunque el contrato haya terminado antes (art. 220).</li>
                  <li>No paga impuesto sobre la renta ni se puede embargar (art. 222).</li>
                  <li>No puede pasar de cinco salarios mínimos del sector, salvo que la empresa pague más por costumbre o convenio (art. 219).</li>
                  <li>Si terminó el contrato, el empleador debe darle una constancia escrita de lo que le corresponde (art. 221).</li>
                </ul>
                <p className="border-t border-papel-borde pt-4 text-[0.85rem] text-ink-soft">
                  Cálculo orientativo con las reglas del Código de Trabajo. No sustituye la asesoría de un abogado.
                </p>
              </div>
            )}
          </section>
        </div>

        <section className="mt-12 flex flex-col items-start justify-between gap-5 rounded-2xl bg-panel px-7 py-8 text-sobre-panel md:flex-row md:items-center md:px-10">
          <div className="max-w-[620px] space-y-2">
            <h2 className="font-heading text-[1.6rem] leading-tight font-medium">¿Le terminaron el contrato?</h2>
            <p className="text-[1.02rem] text-nav">
              Calcule también el preaviso, la cesantía y las vacaciones con la calculadora de prestaciones laborales.
            </p>
          </div>
          <Link to="/calculadora-prestaciones-laborales" className="shrink-0 rounded-lg bg-card px-6 py-4 text-[1.05rem] font-bold text-marca-texto hover:bg-background">
            Calcular prestaciones
          </Link>
        </section>

        <article className="lectura mt-14 max-w-[760px] text-[1.02rem] [&_h2]:mt-10 [&_h2]:text-[1.45rem] [&_h3]:mt-6 [&_h3]:text-[1.15rem]">
          <h2>Cómo se calcula la regalía pascual en República Dominicana</h2>
          <p>
            La regalía pascual es el nombre común del salario de Navidad. El Código de Trabajo manda pagarla en diciembre y
            la define como la duodécima parte del salario ordinario que el trabajador ganó en el año calendario (art. 219).
            Si trabajó el año completo con el mismo salario, la regalía es igual a un mes de salario.
          </p>
          <h3>Si no trabajó todo el año</h3>
          <p>
            Se paga en proporción al tiempo trabajado en el año (art. 220). Por ejemplo, con un salario de RD$ 30,000 y 6
            meses trabajados, la regalía es RD$ 30,000 × 6 ÷ 12 = RD$ 15,000.
          </p>
          <h3>Qué cuenta y qué no</h3>
          <p>
            Cuenta el salario ordinario. No cuentan las horas extraordinarias ni la participación en los beneficios de la
            empresa (art. 219). Si el salario cambió durante el año, se suma todo lo ganado y se divide entre 12.
          </p>
          <h3>Cuándo se paga</h3>
          <p>
            A más tardar el 20 de diciembre, aunque el contrato haya terminado antes y sin importar la causa (art. 220). Al
            terminar el contrato, el empleador debe entregar una constancia escrita de la suma que corresponde (art. 221).
          </p>
          <h3>Impuestos y límite</h3>
          <p>
            La regalía no está sujeta al impuesto sobre la renta ni se puede embargar, ceder o vender (art. 222). No puede
            ser mayor de cinco salarios mínimos legalmente establecidos, aunque la empresa puede pagar más por costumbre,
            convenio colectivo o por decisión propia (art. 219).
          </p>
        </article>
      </main>
      <PiePublico />
    </div>
  )
}
