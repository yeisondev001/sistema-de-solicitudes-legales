import { useCallback, useEffect, useState } from 'react'
import { CircleCheck, RefreshCw, Trash2, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Cargando } from '@/components/cargando'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import { Button } from '@/components/ui/button'
import { api, ErrorApi } from '@/lib/api'
import { cn } from '@/lib/utils'

interface ErrorServidor {
  id: number
  fecha: number
  metodo: string
  ruta: string
  tipo: string
  mensaje: string
  detalle: string
  usuario?: string
  resuelto?: number | null
}

const DIA = 24 * 3600

function cuando(fecha: number) {
  return new Date(fecha * 1000).toLocaleString('es-DO', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
}

/** Los errores del servidor (solo administradores): qué falló, dónde y cuándo. Nunca el contenido de lo que el abogado subió. */
export default function Errores() {
  const [lista, setLista] = useState<ErrorServidor[] | null>(null)
  const [error, setError] = useState('')

  const cargar = useCallback(() => {
    api.get<ErrorServidor[]>('/api/errores').then(setLista).catch((e: ErrorApi) => setError(e.message))
  }, [])
  useEffect(() => {
    cargar()
    const t = setInterval(cargar, 30000)   // se actualiza solo mientras la tiene abierta
    return () => clearInterval(t)
  }, [cargar])

  async function limpiar() {
    try {
      await api.borrar('/api/errores')
      setLista([])
      toast.success('Lista limpia.')
    } catch (e) {
      toast.error(e instanceof ErrorApi ? e.message : 'No se pudo limpiar.')
    }
  }

  if (error) return <p className="text-ink-soft">{error}</p>
  if (lista === null) return <Cargando />

  const ahora = Date.now() / 1000
  const hoy = lista.filter((e) => ahora - e.fecha < DIA).length

  return (
    <div className="mx-auto max-w-4xl">
      <TituloSala titulo="Errores" sub="Lo que falló, a qué cuenta le pasó y si ya pudo volver a entrar. Nunca lo que el abogado subió.">
        <div className="flex gap-2">
          <Button variant="outline" onClick={cargar}><RefreshCw /> Actualizar</Button>
          {lista.length > 0 && <Button variant="outline" onClick={limpiar}><Trash2 /> Limpiar</Button>}
        </div>
      </TituloSala>

      <div
        className={cn(
          'mb-6 flex items-center gap-3 rounded-xl border p-5 text-[1.05rem] font-bold',
          hoy ? 'border-red-300 bg-red-50 text-red-900' : 'border-emerald-300 bg-emerald-50 text-emerald-900',
        )}
      >
        {hoy ? <TriangleAlert className="size-6" /> : <CircleCheck className="size-6" />}
        {hoy ? `${hoy} ${hoy === 1 ? 'error' : 'errores'} en las últimas 24 horas` : 'Sin errores en las últimas 24 horas'}
      </div>

      <Seccion titulo="Últimos errores">
        {lista.length === 0 ? (
          <p className="text-ink-soft">No hay errores guardados.</p>
        ) : (
          <ul className="divide-y divide-papel-borde">
            {lista.map((e) => (
              <li key={e.id} className="py-3">
                <details>
                  <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                    <p className="font-bold text-ink">
                      {e.tipo} <span className="font-normal text-ink-soft">en {e.metodo} {e.ruta}</span>
                    </p>
                    <p className="text-[0.9rem] text-ink-soft">
                      {cuando(e.fecha)}{e.mensaje ? ` · ${e.mensaje}` : ''}{e.usuario ? ` · a la cuenta de ${e.usuario}` : ''}
                    </p>
                  </summary>
                  {e.resuelto && (
                    <p className="mt-2 flex items-center gap-2 text-[0.88rem] font-bold text-emerald-800">
                      <CircleCheck className="size-4" />
                      Ya volvió a entrar y funcionó ({new Date(e.resuelto * 1000).toLocaleString('es-DO', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })})
                    </p>
                  )}
                  <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-card p-3 text-[0.78rem] whitespace-pre-wrap text-ink">{e.detalle}</pre>
                </details>
              </li>
            ))}
          </ul>
        )}
      </Seccion>
    </div>
  )
}
