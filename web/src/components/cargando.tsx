import { Skeleton } from '@/components/ui/skeleton'

/** Mientras llega algo: renglones grises que «respiran», en vez de un «Cargando…» suelto */
export function Cargando({ renglones = 3, que = 'Cargando' }: { renglones?: number; que?: string }) {
  return (
    <div role="status" aria-busy="true" className="space-y-3">
      <span className="sr-only">{que}…</span>
      {Array.from({ length: renglones }, (_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-3/4 bg-papel-borde" />
          <Skeleton className="h-3.5 w-1/2 bg-papel-borde/70" />
        </div>
      ))}
    </div>
  )
}
