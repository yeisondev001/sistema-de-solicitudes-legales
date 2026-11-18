import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FolderClosed, Search, X } from 'lucide-react'
import { toast } from 'sonner'
import { Cargando } from '@/components/cargando'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api, type ErrorApi } from '@/lib/api'
import type { ExpedienteResumen } from '@/lib/tipos'

export interface Caso {
  id: number
  cliente: string
}

const normal = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

/**
 * Guardar la conversación (con su escrito) en un expediente, cambiarla de expediente o sacarla.
 * Con una conversación guardada se hace enseguida; en una nueva queda elegido y se guarda con la primera pregunta.
 */
export function ElegirExpediente({ convId, actual, alCerrar, alElegir }: {
  convId: number | null
  actual: Caso | null
  alCerrar: () => void
  alElegir: (caso: Caso | null) => void
}) {
  const [lista, setLista] = useState<ExpedienteResumen[] | null>(null)
  const [buscar, setBuscar] = useState('')
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    api.get<ExpedienteResumen[]>('/api/expedientes').then(setLista).catch((e: ErrorApi) => {
      toast.error(e.message)
      setLista([])
    })
  }, [])

  async function elegir(caso: Caso | null) {
    if (convId === null) {
      alElegir(caso)
      return
    }
    setGuardando(true)
    try {
      const r = await api.put<{ expediente: Caso | null }>(`/api/conversaciones/${convId}/expediente`, {
        expediente_id: caso?.id ?? null,
      })
      toast.success(r.expediente ? `Guardada en el expediente de ${r.expediente.cliente}.` : 'Ya no está en ningún expediente.')
      alElegir(r.expediente)
    } catch (e) {
      toast.error((e as ErrorApi).message)
      setGuardando(false)
    }
  }

  const q = normal(buscar.trim())
  const vistos = (lista ?? []).filter(
    (x) => x.estado === 'activo' && (!q || normal(`${x.cliente} ${x.asunto} ${x.numero}`).includes(q)),
  )
  return (
    <Dialog open onOpenChange={(a) => !a && alCerrar()}>
      <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-medium">Guardar en un expediente</DialogTitle>
          <DialogDescription>
            La conversación y su escrito quedan en la carpeta del caso. Solo usted los ve allí. Papiniano no recibe los
            datos del expediente.
          </DialogDescription>
        </DialogHeader>
        {(lista?.length ?? 0) > 6 && (
          <label className="flex h-11 items-center gap-2.5 rounded-lg border border-regla bg-card px-3.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
            <Search className="size-[1.1rem] shrink-0 text-ink-soft" />
            <span className="sr-only">Buscar expedientes</span>
            <input
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
              placeholder="Buscar por cliente o número…"
              className="min-w-0 flex-1 bg-transparent text-base text-ink outline-none placeholder:text-ink-soft"
            />
          </label>
        )}
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
          {lista === null ? (
            <Cargando renglones={3} que="Cargando sus expedientes" />
          ) : vistos.length ? (
            <ul className="space-y-1.5">
              {vistos.map((x) => (
                <li key={x.id}>
                  <button
                    type="button"
                    disabled={guardando}
                    aria-current={x.id === actual?.id || undefined}
                    onClick={() => elegir({ id: x.id, cliente: x.cliente })}
                    className="flex w-full items-center gap-3 rounded-xl border border-papel-borde bg-card px-3.5 py-3 text-left transition-colors hover:border-marca aria-[current]:border-marca aria-[current]:bg-[#F1E6DE]"
                  >
                    <FolderClosed className="size-5 shrink-0 text-marca-texto" />
                    <span className="min-w-0 flex-1">
                      <span className="block font-bold text-ink">{x.cliente}</span>
                      {(x.asunto || x.numero) && (
                        <span className="block text-[0.88rem] text-ink-soft">{[x.asunto, x.numero && `Núm. ${x.numero}`].filter(Boolean).join(' · ')}</span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-ink-soft">
              {lista.length ? 'Ningún expediente activo coincide.' : 'Todavía no tiene expedientes.'}{' '}
              <Link to="/expedientes" className="text-marca-texto underline">Crear uno en Expedientes</Link>
            </p>
          )}
        </div>
        {actual && (
          <Button variant="ghost" size="grande" className="self-start text-ink-soft" disabled={guardando} onClick={() => elegir(null)}>
            <X /> Sacarla del expediente de {actual.cliente}
          </Button>
        )}
      </DialogContent>
    </Dialog>
  )
}
