import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { History, Loader2, MessageSquarePlus, SendHorizontal, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { NOMBRE_ASISTENTE, Papiniano } from '@/components/papiniano'
import { Burbuja, BurbujaUsuario } from '@/components/respuesta'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { api, ErrorApi, preguntarAlAsistente } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Conversacion, Turno } from '@/lib/tipos'
import { cn } from '@/lib/utils'

const EJEMPLOS = [
  '¿Qué pasa si se aprobó un deslinde sin citar a los colindantes?',
  '¿Cuándo caduca el recurso de casación?',
  'Me despidieron sin pagarme las prestaciones, ¿qué dice la Suprema?',
  'Calcule las prestaciones de un despido sin causa: salario de RD$50,000 al mes, 3 años y 4 meses trabajados.',
]

/**
 * La consulta es una conversación: cada mensaje del abogado y cada respuesta (con las fuentes que usó)
 * se guardan en la base, así las vuelve a abrir desde la lista (/papiniano/:id).
 */
export default function Asistente() {
  const { id } = useParams()
  const convId = id ? Number(id) : null
  const navegar = useNavigate()
  const { refrescar } = useSesion()

  const [mensajes, setMensajes] = useState<Turno[]>([])
  const [pendiente, setPendiente] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)
  const [texto, setTexto] = useState('')
  const [lista, setLista] = useState<Conversacion[]>([])
  const [listaAbierta, setListaAbierta] = useState(false)
  const [porBorrar, setPorBorrar] = useState<Conversacion | null>(null)

  // la conversación abierta (la respuesta puede llegar después de cambiar de dirección)
  const convActual = useRef(convId)
  useEffect(() => {
    convActual.current = convId
  }, [convId])
  // la última conversación que se pintó: así no se vuelve a leer la que se acaba de crear
  const anterior = useRef<number | null | undefined>(undefined)
  const fin = useRef<HTMLDivElement>(null)

  const cargarLista = useCallback(() => {
    api.get<Conversacion[]>('/api/conversaciones').then(setLista).catch(() => {})
  }, [])
  useEffect(cargarLista, [cargarLista])

  useEffect(() => {
    if (anterior.current === convId) return
    anterior.current = convId
    if (convId === null) {
      setMensajes([])
      return
    }
    setCargando(true)
    api
      .get<{ mensajes: Turno[] }>(`/api/conversaciones/${convId}`)
      .then((r) => setMensajes(r.mensajes))
      .catch((e: ErrorApi) => {
        toast.error(e.message)
        navegar('/papiniano', { replace: true })
      })
      .finally(() => setCargando(false))
  }, [convId, navegar])

  useEffect(() => {
    fin.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [mensajes, pendiente])

  async function enviar(q: string) {
    q = q.trim()
    if (q.length < 2 || pendiente) return
    setTexto('')
    setMensajes((m) => [...m, { rol: 'usuario', texto: q }])
    setPendiente('Pensando…')
    try {
      const r = await preguntarAlAsistente(q, convActual.current, setPendiente)
      setMensajes((m) => [...m, r.turno])
      if (r.conv_id && r.conv_id !== convActual.current) {
        anterior.current = r.conv_id
        navegar(`/papiniano/${r.conv_id}`, { replace: true })
      }
      cargarLista()
      refrescar() // el contador de consultas de la prueba
    } catch (e) {
      setMensajes((m) => [...m, { rol: 'asistente', texto: (e as ErrorApi).message }])
    } finally {
      setPendiente(null)
    }
  }

  async function borrar(c: Conversacion) {
    try {
      await api.borrar(`/api/conversaciones/${c.id}`)
      toast.success('Conversación borrada.')
      if (c.id === convId) navegar('/papiniano')
      cargarLista()
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  const listaConversaciones = (
    <div className="flex flex-col gap-0.5">
      {lista.length ? (
        lista.map((c) => (
          <div
            key={c.id}
            className={cn(
              'group flex items-center gap-1 rounded-lg pr-1 transition-colors',
              c.id === convId ? 'bg-muted' : 'hover:bg-muted/60',
            )}
          >
            <button
              type="button"
              disabled={Boolean(pendiente)}
              onClick={() => {
                setListaAbierta(false)
                navegar(`/papiniano/${c.id}`)
              }}
              className={cn('line-clamp-2 flex-1 px-3 py-2.5 text-left text-[0.92rem] text-ink', c.id === convId && 'font-bold')}
            >
              {c.titulo}
            </button>
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-ink-soft opacity-70 group-hover:opacity-100"
              aria-label={`Borrar «${c.titulo}»`}
              onClick={() => setPorBorrar(c)}
            >
              <Trash2 />
            </Button>
          </div>
        ))
      ) : (
        <p className="px-3 py-2 text-[0.9rem] text-ink-soft italic">Aquí aparecerán sus conversaciones.</p>
      )}
    </div>
  )

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-papel-borde bg-card/40 xl:flex">
        <p className="px-5 pt-6 pb-3 text-[0.85rem] font-bold tracking-wide text-ink-soft">CONVERSACIONES</p>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">{listaConversaciones}</div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-3 border-b border-papel-borde px-4 py-3 md:px-8">
          <div className="flex items-center gap-3">
            <Papiniano className="size-11" decorativo />
            <div>
              <h1 className="font-heading text-2xl font-medium text-ink">{NOMBRE_ASISTENTE}</h1>
              <p className="hidden text-[0.88rem] text-ink-soft sm:block">
                Su asistente. Pregúntele como a un colega; cada respuesta cita sus fuentes.
              </p>
            </div>
          </div>
          <div className="flex gap-1">
            <Button variant="ghost" className="h-10 text-ink-soft xl:hidden" onClick={() => setListaAbierta(true)}>
              <History /> <span className="hidden sm:inline">Conversaciones</span>
            </Button>
            <Button
              variant="ghost"
              className="h-10 text-ink-soft"
              disabled={!mensajes.length || Boolean(pendiente)}
              onClick={() => navegar('/papiniano')}
            >
              <MessageSquarePlus /> <span className="hidden sm:inline">Nueva conversación</span>
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6 md:px-8">
            {cargando ? (
              <p className="flex items-center gap-2 text-ink-soft">
                <Loader2 className="size-4 animate-spin" /> Abriendo la conversación…
              </p>
            ) : mensajes.length ? (
              mensajes.map((t, n) =>
                t.rol === 'usuario' ? <BurbujaUsuario key={n} texto={t.texto} /> : <Burbuja key={n} turno={t} />,
              )
            ) : (
              <>
                <Burbuja
                  turno={{
                    rol: 'asistente',
                    texto:
                      `Hola. Soy ${NOMBRE_ASISTENTE}, su asistente de jurisprudencia: busco en las sentencias de la Suprema Corte (Boletín Judicial), ` +
                      'en las leyes y reglamentos y en sus documentos, y le doy mi análisis con las citas para que las verifique.' +
                      '\n\nPuede empezar con una de estas:',
                  }}
                />
                <div className="-mt-2 flex flex-wrap gap-2">
                  {EJEMPLOS.map((e) => (
                    <button
                      key={e}
                      type="button"
                      onClick={() => enviar(e)}
                      className="rounded-2xl border border-regla bg-card px-4 py-2.5 text-left text-[0.92rem] text-ink transition-colors hover:border-marca hover:text-marca-texto"
                    >
                      {e}
                    </button>
                  ))}
                </div>
              </>
            )}
            {pendiente && (
              <p className="flex items-center gap-2.5 text-[0.92rem] text-ink-soft italic" aria-live="polite">
                <Loader2 className="size-4 animate-spin text-marca-texto" /> {pendiente}
              </p>
            )}
            <div ref={fin} />
          </div>
        </div>

        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            enviar(texto)
          }}
          className="border-t border-papel-borde bg-background"
        >
          <div className="mx-auto max-w-3xl px-4 pt-3 pb-2 md:px-8">
            <div className="flex items-end gap-2">
              <Textarea
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={(e) => {
                  // Enter manda; Mayús+Enter baja de renglón
                  if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault()
                    enviar(texto)
                  }
                }}
                placeholder="Escriba su consulta…"
                aria-label="Su consulta"
                rows={1}
                className="max-h-48 min-h-12 resize-none rounded-3xl bg-card px-5 py-3 text-base md:text-base"
              />
              <Button type="submit" size="icon-grande" className="shrink-0 rounded-full" disabled={Boolean(pendiente)} aria-label="Enviar">
                <SendHorizontal />
              </Button>
            </div>
            <p className="mt-2 text-[0.8rem] text-ink-soft italic">
              Herramienta de apoyo: verifique cada cita en la fuente antes de usarla. No escriba datos personales de
              clientes en la consulta.
            </p>
          </div>
        </form>
      </div>

      <Sheet open={listaAbierta} onOpenChange={setListaAbierta}>
        <SheetContent side="right" className="w-[20rem] overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="font-heading text-xl font-medium">Conversaciones</SheetTitle>
            <SheetDescription>Toque una para abrirla.</SheetDescription>
          </SheetHeader>
          <div className="px-2 pb-6">{listaConversaciones}</div>
        </SheetContent>
      </Sheet>

      <AlertDialog open={Boolean(porBorrar)} onOpenChange={(abierto) => !abierto && setPorBorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Borrar la conversación?</AlertDialogTitle>
            <AlertDialogDescription>
              «{porBorrar?.titulo}». Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-10">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="h-10 bg-destructive text-card hover:bg-destructive/90"
              onClick={() => porBorrar && borrar(porBorrar)}
            >
              Borrar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
