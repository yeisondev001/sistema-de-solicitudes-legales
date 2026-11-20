import { Check, ChevronDown, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { planes } from '@/pages/inicio'

export type DatosPlan = ReturnType<typeof planes>[number]

/** El interruptor Mensual / Anual de los planes (sobre fondo oscuro, igual en la página pública y en «Mi plan»). */
export function InterruptorCiclo({ anual, setAnual }: { anual: boolean; setAnual: (v: boolean) => void }) {
  return (
    <div role="group" aria-label="Cómo quiere pagar" className="inline-flex items-center gap-3 rounded-full bg-[#4A3527] p-1.5 pr-4">
      <div className="flex rounded-full">
        {([['Mensual', false], ['Anual', true]] as const).map(([texto, valor]) => (
          <button
            key={texto}
            type="button"
            aria-pressed={anual === valor}
            onClick={() => setAnual(valor)}
            className={cn(
              'rounded-full px-5 py-2 font-bold transition-colors',
              anual === valor ? 'bg-[#F1E8DA] text-[#7A1F2B]' : 'text-[#E2C9A8] hover:text-white',
            )}
          >
            {texto}
          </button>
        ))}
      </div>
      <span className="text-[0.9rem] font-bold text-[#E2C29B]">2 meses gratis al año</span>
    </div>
  )
}

/** La clase del botón de abajo de cada tarjeta. */
export const claseBotonPlan = (destacado?: boolean) =>
  cn(
    'mt-auto rounded-lg border border-[#F1E8DA] px-4 py-3.5 text-center font-bold disabled:opacity-60',
    destacado ? 'bg-[#7A1F2B] text-white hover:bg-[#8C2A36]' : 'text-[#F8F4EC] hover:bg-white/10',
  )

/** Una tarjeta de plan: el mismo diseño en la página pública y en «Mi plan»; solo cambia el botón (accion). */
export function TarjetaPlan({ p, anual, accion }: { p: DatosPlan; anual: boolean; accion: ReactNode }) {
  return (
    <div
      className={cn(
        'relative flex flex-col gap-3.5 rounded-2xl p-7',
        p.destacado
          ? 'z-10 border-2 border-[#F1E8DA] bg-[#4A3527] pt-12 shadow-[0_18px_50px_rgba(0,0,0,0.55)] md:-my-5 md:scale-[1.04] md:py-12'
          : 'border border-[#6B5442]',
      )}
    >
      {p.destacado && (
        <div className="absolute inset-x-0 top-0 rounded-t-[0.9rem] bg-[#F1E8DA] py-2 text-center text-[0.85rem] font-bold tracking-[0.12em] text-[#7A1F2B]">
          EL MÁS ELEGIDO
        </div>
      )}
      <div>
        <h3 className="font-heading text-[1.75rem] font-medium">{p.nombre}</h3>
      </div>
      <div>
        <p className="text-[2.1rem] font-bold">
          {anual && p.anual ? `US$${p.anual}` : `US$${p.mensual}`}{' '}
          <span className="text-base font-normal text-[#E2C9A8]">{anual && p.anual ? 'al año' : 'al mes'}</span>
        </p>
        {p.anual ? (
          anual ? (
            <p className="text-[0.92rem] text-[#E2C9A8]">
              <strong className="rounded bg-[#F1E8DA] px-2 py-0.5 text-[#7A1F2B]">Ahorra US${p.mensual * 12 - p.anual}</strong>{' '}
              frente a pagar mes a mes.
            </p>
          ) : (
            <p className="text-[0.92rem] text-[#E2C9A8]">
              Con el plan anual ahorra <strong className="text-[#F1E8DA]">US${p.mensual * 12 - p.anual}</strong>.
            </p>
          )
        ) : (
          <p className="text-[0.92rem] text-[#E2C9A8]">{p.nota}</p>
        )}
      </div>
      <div>
        <p className="text-[0.85rem] font-bold tracking-[0.12em] text-[#E2C29B]">{p.quien}</p>
        <p className="mt-1 text-[1.05rem] text-[#F1E8DA]">{p.para}</p>
      </div>
      {/* la diferencia que más pesa entre el Aspirante y los otros dos, a la vista sin abrir nada */}
      <p className={cn('flex items-center gap-2 font-bold', p.tiene ? 'text-[#F1E8DA]' : 'text-[#E2C9A8] line-through decoration-1')}>
        {p.tiene ? <Check className="size-5 shrink-0 text-[#E2C29B]" /> : <X className="size-5 shrink-0 no-underline" />}
        Expedientes y agenda
      </p>
      <details className="group border-t border-[#6B5442] pt-3.5">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 font-bold text-[#F1E8DA] [&::-webkit-details-marker]:hidden">
          Ver qué incluye
          <ChevronDown className="size-5 shrink-0 transition-transform group-open:rotate-180" />
        </summary>
        <ul className="mt-3 space-y-2 text-[#F1E8DA]">
          {p.puntos.map((x) => (
            <li key={x} className="flex gap-2.5">
              <Check className="mt-1 size-4 shrink-0 text-[#E2C29B]" />
              {x}
            </li>
          ))}
        </ul>
        {p.faltan && (
          <div className="mt-3.5">
            <p className="text-[0.8rem] font-bold tracking-[0.12em] text-[#E2C9A8]">NO INCLUYE</p>
            <ul className="mt-2 space-y-2 text-[#E2C9A8]">
              {p.faltan.map((x) => (
                <li key={x} className="flex gap-2.5">
                  <X className="mt-1 size-4 shrink-0" />
                  {x}
                </li>
              ))}
            </ul>
          </div>
        )}
      </details>
      {accion}
    </div>
  )
}
