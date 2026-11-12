import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Tabs as TabsPrimitive } from 'radix-ui'
import { FilePen, History, Loader2, MessageSquarePlus, SendHorizontal, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { PanelEscrito } from '@/components/escrito'
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
import { useAncho } from '@/lib/pantalla'
import { useSesion } from '@/lib/sesion'
import type { Conversacion, Escrito, Turno } from '@/lib/tipos'
import { cn } from '@/lib/utils'

const EJEMPLOS = [
  '¿Qué pasa si se aprobó un deslinde sin citar a los colindantes?',
  '¿Cuándo caduca el recurso de casación?',
  'Me despidieron sin pagarme las prestaciones, ¿qué dice la Suprema?',
  'Calcule las prestaciones de un despido sin causa: salario de RD$50,000 al mes, 3 años y 4 meses trabajados.',
  'Redácteme una instancia en solicitud de aprobación de trabajos de deslinde.',
]

/** Desde este ancho el escrito va al lado de la conversación; más angosto, en su propia pestaña */
const ANCHO_LADO_A_LADO = 1200

/**
 * Lo que el abogado corrige a mano en el escrito se guarda en este equipo mientras no lo guarde: si cambia
 * de pestaña, de conversación o de sala, al volver lo encuentra como lo dejó.
 */
const claveCorreccion = (usuario: number, conv: number) => `papiniano.correccion.${usuario}.${conv}`

function leerCorreccion(usuario: number, conv: number): string | null {
  try {
    return localStorage.getItem(claveCorreccion(usuario, conv))
  } catch {
    return null
  }
}

function guardarCorreccion(usuario: number, conv: number, texto: string | null) {
  try {
    if (texto === null) localStorage.removeItem(claveCorreccion(usuario, conv))
    else localStorage.setItem(claveCorreccion(usuario, conv), texto)
  } catch {
    // sin almacenamiento: la corrección queda mientras la página esté abierta
  }
}

const PESTANAS = [
  ['conversacion', 'Conversación'],
  ['escrito', 'Escrito'],
] as const

/**
 * La consulta es una conversación: cada mensaje del abogado y cada respuesta (con las fuentes que usó)
 * se guardan en la base, así las vuelve a abrir desde la lista (/papiniano/:id).
 * Si le pide un escrito, Papiniano lo escribe en una hoja al lado y lo va cambiando según se le pida.
 */
export default function Asistente() {
  const { id } = useParams()
  const convId = id ? Number(id) : null
  const navegar = useNavigate()
  const { perfil, refrescar } = useSesion()

  const [mensajes, setMensajes] = useState<Turno[]>([])
  const [pendiente, setPendiente] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)
  const [texto, setTexto] = useState('')
  const [lista, setLista] = useState<Conversacion[]>([])
  const [listaAbierta, setListaAbierta] = useState(false)
  const [porBorrar, setPorBorrar] = useState<Conversacion | null>(null)
  const [escrito, setEscrito] = useState<Escrito | null>(null)
  const [escribiendo, setEscribiendo] = useState(false)
  const [correccion, setCorreccionEstado] = useState<string | null>(null)
  // en pantalla angosta se ve la conversación o el escrito; en ancha, el escrito se puede ocultar
  const [vista, setVista] = useState<'conversacion' | 'escrito'>('conversacion')
  const [oculto, setOculto] = useState(false)
  const [pulso, setPulso] = useState(0)
  const ancha = useAncho(ANCHO_LADO_A_LADO)

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

  function setCorreccion(t: string | null) {
    setCorreccionEstado(t)
    if (convId) guardarCorreccion(perfil.id, convId, t)
  }

  useEffect(() => {
    if (anterior.current === convId) return
    anterior.current = convId
    setVista('conversacion')
    if (convId === null) {
      setMensajes([])
      setEscrito(null)
      setCorreccionEstado(null)
      return
    }
    setCargando(true)
    api
      .get<{ mensajes: Turno[]; escrito: Escrito | null }>(`/api/conversaciones/${convId}`)
      .then((r) => {
        setMensajes(r.mensajes)
        setEscrito(r.escrito)
        setCorreccionEstado(r.escrito ? leerCorreccion(perfil.id, convId) : null)
      })
      .catch((e: ErrorApi) => {
        toast.error(e.message)
        navegar('/papiniano', { replace: true })
      })
      .finally(() => setCargando(false))
  }, [convId, navegar, perfil.id])

  useEffect(() => {
    fin.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [mensajes, pendiente])

  function verEscrito(mostrarCambio = false) {
    setOculto(false)
    setVista('escrito')
    if (mostrarCambio) setPulso((n) => n + 1)
  }

  async function enviar(q: string) {
    q = q.trim()
    if (q.length < 2 || pendiente || correccion !== null) return
    const desde = convActual.current
    setTexto('')
    setMensajes((m) => [...m, { rol: 'usuario', texto: q }])
    setPendiente('Pensando…')
    try {
      const r = await preguntarAlAsistente(q, desde, (avance, enEscrito) => {
        setPendiente(avance)
        if (enEscrito && convActual.current === desde) {
          setEscribiendo(true)
          verEscrito()
        }
      })
      setMensajes((m) => [...m, r.turno])
      if (convActual.current === desde) {
        if (r.escrito) setEscrito(r.escrito)
        // en el celular se muestra donde quedó la respuesta: el escrito si lo cambió; si no, la conversación
        if (!ancha) setVista(r.escrito ? 'escrito' : 'conversacion')
      }
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
      setEscribiendo(false)
    }
  }

  async function borrar(c: Conversacion) {
    try {
      await api.borrar(`/api/conversaciones/${c.id}`)
      guardarCorreccion(perfil.id, c.id, null)
      toast.success('Conversación borrada.')
      if (c.id === convId) navegar('/papiniano')
      cargarLista()
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  const hayEscrito = Boolean(escrito) || escribiendo
  const alLado = hayEscrito && ancha && !oculto
  const conPestanas = hayEscrito && !ancha
  const enEscrito = conPestanas && vista === 'escrito'
  // la respuesta que hizo el último cambio al escrito: su botón lleva a ese cambio
  const ultimoCambio = mensajes.findLastIndex((t) => t.escrito)

  const panel = (
    <PanelEscrito
      key={convId ?? 'nueva'}
      escrito={escrito}
      convId={convId}
      usuarioId={perfil.id}
      trabajando={escribiendo}
      borrador={correccion}
      setBorrador={setCorreccion}
      alCambiar={setEscrito}
      alOcultar={ancha ? () => setOculto(true) : undefined}
      compacto={!ancha}
      pulso={pulso}
    />
  )

  const conversacion = (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6 md:px-8">
        {cargando ? (
          <p className="flex items-center gap-2 text-ink-soft">
            <Loader2 className="size-4 animate-spin" /> Abriendo la conversación…
          </p>
        ) : mensajes.length ? (
          mensajes.map((t, n) =>
            t.rol === 'usuario' ? (
              <BurbujaUsuario key={n} texto={t.texto} />
            ) : (
              <Burbuja
                key={n}
                turno={t}
                esUltimoCambio={n === ultimoCambio}
                alVerEscrito={escrito && (!alLado || n === ultimoCambio) ? () => verEscrito(n === ultimoCambio) : undefined}
              />
            ),
          )
        ) : (
          <>
            <Burbuja
              turno={{
                rol: 'asistente',
                texto:
                  `Hola. Soy ${NOMBRE_ASISTENTE}, su asistente de jurisprudencia: busco en las sentencias de la Suprema Corte (Boletín Judicial), ` +
                  'en las leyes y reglamentos y en sus documentos, y le doy mi análisis con las citas para que las verifique. ' +
                  'También le redacto instancias y otros escritos aquí al lado: usted me dice qué cambiar y lo descarga en Word o PDF.' +
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
  )

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
              size="icon-grande"
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

  // con el escrito al lado la columna de la conversación es angosta: los botones quedan solo con su ícono
  const etiqueta = alLado ? 'sr-only' : 'sr-only sm:not-sr-only'

  return (
    <div className="flex min-h-0 flex-1">
      <aside className={cn('hidden w-72 shrink-0 flex-col border-r border-papel-borde bg-card/40', !alLado && 'xl:flex')}>
        <p className="px-5 pt-6 pb-3 text-[0.85rem] font-bold tracking-wide text-ink-soft">CONVERSACIONES</p>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">{listaConversaciones}</div>
      </aside>

      <div className={cn('flex min-w-0 flex-1 flex-col', alLado && 'max-w-[34rem] min-w-[22rem] basis-[38%]')}>
        {/* en el celular, mirando el escrito, el encabezado se esconde para que la hoja tenga lugar */}
        {!enEscrito && (
          <div className="flex items-center justify-between gap-3 border-b border-papel-borde px-4 py-3 md:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <Papiniano className="size-11" decorativo />
              <div className="min-w-0">
                <h1 className="font-heading text-2xl font-medium text-ink">{NOMBRE_ASISTENTE}</h1>
                {!alLado && (
                  <p className="hidden text-[0.88rem] text-ink-soft sm:block">
                    Su asistente. Pregúntele como a un colega; cada respuesta cita sus fuentes.
                  </p>
                )}
              </div>
            </div>
            <div className="flex gap-1">
              {hayEscrito && ancha && oculto && (
                <Button variant="ghost" className="h-11 min-w-11 text-ink-soft" onClick={() => verEscrito()} title="Ver el escrito">
                  <FilePen /> <span className={etiqueta}>Ver el escrito</span>
                </Button>
              )}
              <Button
                variant="ghost"
                className={cn('h-11 min-w-11 text-ink-soft', !alLado && 'xl:hidden')}
                onClick={() => setListaAbierta(true)}
                title="Conversaciones"
              >
                <History /> <span className={etiqueta}>Conversaciones</span>
              </Button>
              <Button
                variant="ghost"
                className="h-11 min-w-11 text-ink-soft"
                disabled={!mensajes.length || Boolean(pendiente)}
                onClick={() => navegar('/papiniano')}
                title="Nueva conversación"
              >
                <MessageSquarePlus /> <span className={etiqueta}>Nueva conversación</span>
              </Button>
            </div>
          </div>
        )}

        {conPestanas ? (
          <TabsPrimitive.Root
            value={vista}
            onValueChange={(v) => setVista(v as typeof vista)}
            className="flex min-h-0 flex-1 flex-col"
          >
            <TabsPrimitive.List aria-label="Qué ver" className="flex gap-2 border-b border-papel-borde px-4 py-2">
              {PESTANAS.map(([v, nombre]) => (
                <TabsPrimitive.Trigger
                  key={v}
                  value={v}
                  className="flex h-11 flex-1 items-center justify-center gap-2 rounded-full border border-regla bg-card text-[0.95rem] text-ink transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 data-[state=active]:border-marca data-[state=active]:bg-marca data-[state=active]:font-bold data-[state=active]:text-sobre-boton"
                >
                  {nombre}
                  {v === 'escrito' && escribiendo && <Loader2 className="size-4 animate-spin" />}
                </TabsPrimitive.Trigger>
              ))}
            </TabsPrimitive.List>
            <TabsPrimitive.Content value="conversacion" className="flex min-h-0 flex-1 flex-col outline-none">
              {conversacion}
            </TabsPrimitive.Content>
            <TabsPrimitive.Content value="escrito" className="flex min-h-0 flex-1 flex-col outline-none">
              {panel}
            </TabsPrimitive.Content>
          </TabsPrimitive.Root>
        ) : (
          conversacion
        )}

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
                placeholder={escrito ? 'Pídale un cambio al escrito o haga una consulta…' : 'Escriba su consulta…'}
                aria-label="Su consulta"
                rows={1}
                className="max-h-48 min-h-12 resize-none rounded-3xl bg-card px-5 py-3 text-base md:text-base"
              />
              <Button
                type="submit"
                size="icon-grande"
                className="shrink-0 rounded-full"
                disabled={Boolean(pendiente) || correccion !== null}
                aria-label="Enviar"
              >
                <SendHorizontal />
              </Button>
            </div>
            <p className="mt-2 text-[0.8rem] text-ink-soft italic">
              {correccion !== null
                ? 'Guarde o cancele la corrección a mano para pedirle cambios a Papiniano.'
                : enEscrito
                  ? 'No escriba aquí nombres ni cédulas del cliente: van en «Por llenar».'
                  : 'Herramienta de apoyo: verifique cada cita en la fuente antes de usarla. No escriba datos personales de clientes en la consulta.'}
            </p>
          </div>
        </form>
      </div>

      {alLado && <div className="flex min-w-0 flex-1 flex-col border-l border-papel-borde">{panel}</div>}

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
              «{porBorrar?.titulo}»{porBorrar && porBorrar.id === convId && escrito ? ', con su escrito' : ''}. Esta
              acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="peligro"
              size="grande"
              onClick={() => porBorrar && borrar(porBorrar)}
            >
              <Trash2 /> Sí, borrar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
