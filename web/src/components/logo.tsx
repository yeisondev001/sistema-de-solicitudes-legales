import { Scale } from 'lucide-react'
import { cn } from '@/lib/utils'
import { NOMBRE_APP } from '@/lib/tema'

/** La balanza y el nombre. Sobre el panel oscuro del menú, el nombre va claro. */
export function Logo({ enPanel = false }: { enPanel?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={cn(
          'flex size-10 items-center justify-center rounded-[9px]',
          enPanel ? 'bg-sobre-panel text-panel' : 'bg-boton text-sobre-boton',
        )}
      >
        <Scale className="size-[22px]" />
      </span>
      <span className={cn('font-heading text-[1.6rem] font-semibold', enPanel ? 'text-sobre-panel' : 'text-panel')}>
        {NOMBRE_APP}
      </span>
    </div>
  )
}
