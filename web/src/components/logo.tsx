import { Papiniano } from '@/components/papiniano'
import { cn } from '@/lib/utils'
import { NOMBRE_APP } from '@/lib/tema'

/** El logo: el camafeo de Papiniano y el nombre. Sobre el panel oscuro del menú, el nombre va claro. */
export function Logo({ enPanel = false }: { enPanel?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <Papiniano className="size-10" decorativo />
      <span className={cn('font-heading text-[1.6rem] font-semibold', enPanel ? 'text-sobre-panel' : 'text-panel')}>
        {NOMBRE_APP}
      </span>
    </div>
  )
}
