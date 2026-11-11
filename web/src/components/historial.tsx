import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Copy, FileText, Loader2, Pencil, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, descargar, ErrorApi } from '@/lib/api'
import type { EntradaHistorial } from '@/lib/tipos'
import { cn } from '@/lib/utils'

const dos = (n: number) => String(n).padStart(2, '0')

/** «Hoy» / «Mañana» / «En N días» si la próxima audiencia es esta semana */
function proxima(fecha: string) {
  const m = fecha.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (!m) return null
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  const dias = Math.round((new Date(+m[3], +m[2] - 1, +m[1]).getTime() - hoy.getTime()) / 86400000)
  return dias === 0 ? 'Hoy' : dias === 1 ? 'Mañana' : dias > 1 && dias <= 7 ? `En ${dias} días` : null
}

/** El historial de expedientes: cada Reporte de Audiencia generado, para buscarlo, editarlo o copiarlo. */
export function Historial({
  alAbrir, alCambiar,
}: {
  alAbrir: (e: EntradaHistorial, editar: boolean) => void
  alCambiar: () => void
}) {
  const [lista, setLista] = useState<EntradaHistorial[] | null>(null)
  const [error, setError] = useState('')
  const [filtro, setFiltro] = useState('')
  const [abiertos, setAbiertos] = useState<Set<number>>(new Set())
  const [porBorrar, setPorBorrar] = useState<EntradaHistorial | null>(null)
  const [bajando, setBajando] = useState(false)

  const cargar = useCallback(() => {
    api.get<EntradaHistorial[]>('/api/historial').then(setLista).catch((e: ErrorApi) => setError(e.message))
  }, [])
  useEffect(cargar, [cargar])

  async function borrar(e: EntradaHistorial) {
    try {
      await api.borrar(`/api/historial/${e.id}`)
      toast.success(`No.${dos(e.numero)} borrado del historial.`)
      cargar()
      alCambiar()
    } catch (ex) {
      toast.error((ex as ErrorApi).message)
    }
  }

  async function bajarTodo() {
    setBajando(true)
    try {
      await descargar('/api/historial/word')
    } catch (ex) {
      toast.error((ex as ErrorApi).message)
    } finally {
      setBajando(false)
    }
  }

  if (error) return <p className="text-destructive">{error}</p>
  if (!lista)
    return (
      <p className="flex items-center gap-2 text-ink-soft">
        <Loader2 className="size-4 animate-spin" /> Cargando el historial…
      </p>
    )
  if (!lista.length)
    return (
      <section className="rounded-2xl border border-papel-borde bg-card p-6">
        <h2 className="mb-2 font-heading text-xl font-medium text-ink">Empiece su historial</h2>
        <p className="mb-4 text-ink-soft">
          Cada Reporte de Audiencia que genere en Word o PDF aparecerá aquí, listo para buscarlo, editarlo o descargarlo
          con el formato de EXPEDIENTES.
        </p>
        <Button size="grande" asChild>
          <Link to="/redaccion/reporte">Crear un Reporte de Audiencia</Link>
        </Button>
      </section>
    )

  const q = filtro.trim().toLowerCase()
  const visibles = [...lista]
    .reverse()
    .filter((e) => !q || [e.expediente, e.recurrente, e.recurrido, e.tribunal, e.parcela, e.objeto].some((x) => (x ?? '').toLowerCase().includes(q)))

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-soft" />
          <Input
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            placeholder="Buscar por expediente, recurrente, tribunal o parcela"
            aria-label="Buscar en el historial"
            className="h-11 bg-card pl-9 text-base md:text-base"
          />
        </div>
        <Button size="grande" onClick={bajarTodo} disabled={bajando}>
          {bajando ? <Loader2 className="animate-spin" /> : <FileText />} Descargar todo en Word
        </Button>
      </div>
      <p className="text-[0.85rem] text-ink-soft">
        {lista.length} expediente{lista.length === 1 ? '' : 's'} · el más reciente primero · toque uno para verlo completo
      </p>

      <div className="overflow-hidden rounded-2xl border border-papel-borde bg-card">
        <div className="hidden grid-cols-[3rem_7rem_10rem_1fr_7.5rem_1.5rem] gap-3 border-b border-regla px-4 py-2.5 text-[0.78rem] font-bold tracking-wide text-ink-soft md:grid">
          <span>NO.</span><span>AUDIENCIA</span><span>EXP.</span><span>RECURRENTE</span><span>PRÓXIMA</span><span />
        </div>
        {visibles.length ? (
          visibles.map((e) => {
            const abierto = abiertos.has(e.id)
            const etiqueta = proxima(e.fecha_proxima ?? '')
            const d = e.datos ?? {}
            return (
              <div key={e.id} className="border-b border-papel-borde last:border-b-0">
                <button
                  type="button"
                  aria-expanded={abierto}
                  onClick={() => {
                    const otros = new Set(abiertos)
                    if (abierto) otros.delete(e.id)
                    else otros.add(e.id)
                    setAbiertos(otros)
                  }}
                  className="grid w-full grid-cols-[2.5rem_1fr_auto_1.5rem] items-center gap-3 px-4 py-3 text-left hover:bg-muted/50 md:grid-cols-[3rem_7rem_10rem_1fr_7.5rem_1.5rem]"
                >
                  <span className="font-heading text-lg text-marca-texto">{dos(e.numero)}</span>
                  <span className="hidden truncate text-[0.92rem] text-ink md:block">{e.fecha_audiencia || '—'}</span>
                  <span className="min-w-0 md:contents">
                    <span className="block truncate text-[0.92rem] text-ink">{e.expediente || '—'}</span>
                    <span className="block truncate text-[0.88rem] text-ink-soft md:text-[0.92rem] md:text-ink">{e.recurrente || '—'}</span>
                  </span>
                  {etiqueta ? (
                    <span className="justify-self-start rounded-full bg-aviso px-2.5 py-0.5 text-[0.8rem] font-bold text-aviso-texto">{etiqueta}</span>
                  ) : (
                    <span className="truncate text-[0.92rem] text-ink">{e.fecha_proxima || '—'}</span>
                  )}
                  <ChevronDown className={cn('size-5 text-ink-soft transition-transform', abierto && 'rotate-180')} />
                </button>
                {abierto && (
                  <div className="space-y-2 px-4 pb-5 md:pl-[4.75rem]">
                    <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[11rem_1fr]">
                      {(
                        [
                          ['Tribunal', e.tribunal], ['Fecha audiencia', e.fecha_audiencia], ['No. Exp.', e.expediente],
                          ['Recurrente', e.recurrente], ['Recurrido', e.recurrido], ['Agrimensor', e.agrimensor],
                          ['Objeto', e.objeto], ['Parcela', e.parcela], ['Fallo', e.fallo], ['Próxima audiencia', e.fecha_proxima],
                          ...(d.abogados ? [['Abogado(s)', String(d.abogados)]] : []),
                          ...(d.caja_no || d.rol ? [['Caja / Rol', `${d.caja_no || '—'} / ${d.rol || '—'}`]] : []),
                        ] as [string, string][]
                      ).map(([k, v]) => (
                        <div key={k} className="contents">
                          <dt className="text-[0.8rem] font-bold tracking-wide text-ink-soft uppercase sm:pt-0.5">{k}</dt>
                          <dd className="mb-1 text-[0.95rem] text-ink sm:mb-0">{v || '—'}</dd>
                        </div>
                      ))}
                    </dl>
                    <div className="flex flex-wrap gap-2 pt-2">
                      <Button variant="outline" className="h-10 border-regla" onClick={() => alAbrir(e, true)}>
                        <Pencil /> Editar
                      </Button>
                      <Button variant="outline" className="h-10 border-regla" onClick={() => alAbrir(e, false)}>
                        <Copy /> Usar como base
                      </Button>
                      <Button variant="outline" className="h-10 border-regla text-destructive" onClick={() => setPorBorrar(e)}>
                        <Trash2 /> Borrar
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        ) : (
          <p className="p-4 text-ink-soft">Ningún expediente coincide con «{filtro}».</p>
        )}
      </div>

      <AlertDialog open={Boolean(porBorrar)} onOpenChange={(a) => !a && setPorBorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Borrar del historial?</AlertDialogTitle>
            <AlertDialogDescription>
              No.{porBorrar && dos(porBorrar.numero)} · Exp. {porBorrar?.expediente} · {porBorrar?.recurrente}. Esta acción
              no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-10">Cancelar</AlertDialogCancel>
            <AlertDialogAction className="h-10 bg-destructive text-card hover:bg-destructive/90" onClick={() => porBorrar && borrar(porBorrar)}>
              Borrar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
