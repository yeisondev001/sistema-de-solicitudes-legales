import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api, ErrorApi } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Perfil, Tema } from '@/lib/tipos'
import { cn } from '@/lib/utils'

/** Mi cuenta → Apariencia: los 4 temas cerrados de temas.py. El cambio se ve al instante. */
export function Apariencia({ abierta, alCambiar }: { abierta: boolean; alCambiar: (abierta: boolean) => void }) {
  const { perfil, cambiarPerfil } = useSesion()
  const [lista, setLista] = useState<Tema[]>([])

  useEffect(() => {
    if (abierta && !lista.length) api.get<Tema[]>('/api/temas').then(setLista).catch(() => {})
  }, [abierta, lista.length])

  async function elegir(clave: string) {
    if (clave === perfil.tema) return
    try {
      cambiarPerfil(await api.post<Perfil>('/api/tema', { tema: clave }))
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  return (
    <Dialog open={abierta} onOpenChange={alCambiar}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-medium">Apariencia</DialogTitle>
          <DialogDescription className="text-[0.95rem]">
            Elija los colores de su despacho. Todos se leen bien; se guarda en su cuenta.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          {lista.map((t) => {
            const elegido = t.clave === perfil.tema
            const c = t.colores
            return (
              <button
                key={t.clave}
                type="button"
                onClick={() => elegir(t.clave)}
                aria-pressed={elegido}
                className={cn(
                  'overflow-hidden rounded-xl border text-left transition-shadow outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                  elegido ? 'border-2 border-marca' : 'border-papel-borde hover:shadow-md',
                )}
              >
                {/* una oficina en miniatura con los colores del tema */}
                <div className="flex h-20" style={{ background: c.SURFACE }}>
                  <div className="flex w-1/4 flex-col gap-1.5 p-2" style={{ background: c.PANEL_INK }}>
                    <span className="h-2 rounded-full" style={{ background: c.BAR_BTN }} />
                    <span className="h-1.5 w-3/4 rounded-full opacity-60" style={{ background: c.NAV_TEXT }} />
                    <span className="h-1.5 w-2/3 rounded-full opacity-60" style={{ background: c.NAV_TEXT }} />
                  </div>
                  <div className="flex flex-1 flex-col gap-1.5 p-2.5">
                    <span className="h-2 w-1/2 rounded-full" style={{ background: c.INK }} />
                    <div className="flex flex-1 items-end gap-2 rounded-md p-2" style={{ background: c.PAPER, border: `1px solid ${c.PAPER_EDGE}` }}>
                      <span className="h-1.5 flex-1 rounded-full" style={{ background: c.INK_SOFT, opacity: 0.5 }} />
                      <span className="h-3 w-8 rounded" style={{ background: c.BOTON }} />
                    </div>
                  </div>
                </div>
                <div className="flex items-start gap-2 bg-card p-3">
                  <div className="flex-1">
                    <p className="font-bold text-ink">{t.nombre}</p>
                    <p className="text-[0.85rem] text-ink-soft">{t.descripcion}</p>
                  </div>
                  {elegido && <Check className="mt-0.5 size-5 text-marca-texto" aria-label="Elegido" />}
                </div>
              </button>
            )
          })}
        </div>
      </DialogContent>
    </Dialog>
  )
}
