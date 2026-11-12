import { Fragment, useEffect, useRef, useState } from 'react'
import { ChevronDown, Download, FileDown, FileText, Loader2, PanelRightClose, PencilLine, Undo2, UserRound } from 'lucide-react'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, descargar, ErrorApi } from '@/lib/api'
import {
  agrupar, espacios, esDelAbogado, etiqueta, FECHA_DE_HOY, llenar, parrafos, piezas, titulo as tituloDe,
  type TipoParrafo,
} from '@/lib/escrito'
import { fechaLarga } from '@/lib/fechas'
import type { Escrito } from '@/lib/tipos'
import { cn } from '@/lib/utils'

/**
 * Los datos por llenar se guardan solo en este equipo y solo se ponen al descargar: el escrito que ve la IA
 * sigue con los espacios en blanco (Ley 172-13). Los del abogado (nombre, matrícula) sirven para todos sus
 * escritos; los demás, solo para el escrito de esa conversación.
 */
const claveDatos = (usuario: number, conv: number) => `papiniano.datos.${usuario}.${conv}`
const claveAbogado = (usuario: number) => `papiniano.abogado.${usuario}`

function leer(clave: string): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(clave) ?? '{}') ?? {}
  } catch {
    return {}
  }
}

function guardar(clave: string, datos: Record<string, string>) {
  try {
    localStorage.setItem(clave, JSON.stringify(datos))
  } catch {
    // sin almacenamiento (ventana privada): los datos quedan mientras la página esté abierta
  }
}

const CLASES: Record<TipoParrafo, string> = {
  titulo: 'mb-[1.6em] text-center text-[1.08em] font-bold',
  centro: 'text-center font-bold',
  firma: 'text-center leading-snug',
  lineas: 'leading-snug',
  normal: 'text-justify',
}

/** El relleno de la hoja según el ancho del panel: angosto en la laptop y el celular, como Word en pantalla ancha */
const RELLENO = 'px-6 py-8 @2xl:px-14 @2xl:py-14'

interface Marcas {
  /** párrafos nuevos o cambiados */
  nuevos: Set<number>
  /** antes de qué párrafo se quitó texto (el largo de la lista: al final) */
  quitados: Set<number>
}
const SIN_MARCAS: Marcas = { nuevos: new Set(), quitados: new Set() }

/** Qué cambió entre dos versiones del escrito, por párrafos */
function comparar(antes: string, ahora: string): Marcas {
  const viejos = parrafos(antes).map((p) => p.lineas.join('\n'))
  const nuevos = parrafos(ahora).map((p) => p.lineas.join('\n'))
  const habia = new Set(viejos)
  const hay = new Set(nuevos)
  const marcas: Marcas = { nuevos: new Set(), quitados: new Set() }
  nuevos.forEach((t, i) => !habia.has(t) && marcas.nuevos.add(i))
  viejos.forEach((t, i) => {
    if (hay.has(t)) return
    // dónde estaba: antes del siguiente párrafo que sigue igual; si en su lugar hay uno nuevo, se cambió, no se quitó
    const siguiente = viejos.slice(i + 1).find((v) => hay.has(v))
    const donde = siguiente === undefined ? nuevos.length : nuevos.indexOf(siguiente)
    if (!marcas.nuevos.has(donde - 1)) marcas.quitados.add(donde)
  })
  return marcas
}

function resumen(m: Marcas) {
  const partes = []
  if (m.nuevos.size) partes.push(m.nuevos.size === 1 ? 'un párrafo nuevo o cambiado' : `${m.nuevos.size} párrafos nuevos o cambiados`)
  if (m.quitados.size) partes.push(m.quitados.size === 1 ? 'se quitó texto en un lugar' : `se quitó texto en ${m.quitados.size} lugares`)
  return partes.length ? `El escrito cambió: ${partes.join(' y ')}.` : 'El escrito cambió.'
}

/** La hoja: el escrito con el formato del Word. Lo que acaba de cambiar se resalta un momento. */
export function Hoja({
  texto, datos = {}, marcas = SIN_MARCAS,
}: {
  texto: string
  datos?: Record<string, string>
  marcas?: Marcas
}) {
  const lista = parrafos(texto)
  const quitado = (i: number) =>
    marcas.quitados.has(i) && (
      <p className="quitado" data-marca aria-hidden>
        Aquí se quitó texto
      </p>
    )
  return (
    <article lang="es" className={cn('hoja', RELLENO)}>
      {lista.map((p, i) => (
        <Fragment key={i}>
          {quitado(i)}
          <p data-marca={marcas.nuevos.has(i) || undefined} className={cn(CLASES[p.tipo], marcas.nuevos.has(i) && 'cambio')}>
            {p.lineas.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {piezas(l, p.tipo === 'titulo' || p.tipo === 'centro').map((pz, k) => {
                  if (pz.espacio) {
                    const dato = pz.texto.slice(1, -1)
                    const valor = datos[dato]?.trim()
                    return valor ? (
                      <span key={k} className="lleno" title={`Dato llenado: ${etiqueta(dato)}`}>{valor}</span>
                    ) : (
                      <span key={k} className="por-llenar">{pz.texto}</span>
                    )
                  }
                  return pz.negrita ? <strong key={k}>{pz.texto}</strong> : <Fragment key={k}>{pz.texto}</Fragment>
                })}
              </Fragment>
            ))}
          </p>
        </Fragment>
      ))}
      {quitado(lista.length)}
    </article>
  )
}

/**
 * El escrito al lado de la conversación: Papiniano lo escribe y lo cambia cuando se le pide;
 * el abogado lo puede corregir a mano, deshacer el último cambio, llenar los datos y descargarlo en Word o PDF.
 * En el celular (compacto) la barra es de una sola fila y «Corregir a mano» queda debajo de la hoja.
 */
export function PanelEscrito({
  escrito, convId, usuarioId, trabajando, borrador, setBorrador, alCambiar, alOcultar, compacto, pulso, pedirDatos = false,
  alPedirDatos,
}: {
  escrito: Escrito | null
  convId: number | null
  usuarioId: number
  /** Papiniano está escribiendo o cambiando el escrito */
  trabajando: boolean
  /** lo que está corrigiendo a mano (null: no está corrigiendo) */
  borrador: string | null
  setBorrador: (texto: string | null) => void
  alCambiar: (e: Escrito) => void
  alOcultar?: () => void
  compacto: boolean
  /** cambia cada vez que piden ver el escrito desde la conversación: se vuelve a mostrar el último cambio */
  pulso: number
  /** acaba de poner un modelo: se abren los datos por llenar (y se avisa con alPedirDatos que ya se pidieron) */
  pedirDatos?: boolean
  alPedirDatos?: () => void
}) {
  const [delEscrito, setDelEscrito] = useState(() => (convId ? leer(claveDatos(usuarioId, convId)) : {}))
  const [delAbogado, setDelAbogado] = useState(() => leer(claveAbogado(usuarioId)))
  const [verDatos, setVerDatos] = useState(false)
  // faltan datos y pidió descargar: se le avisa antes, con lo que falta
  const [porBajar, setPorBajar] = useState<'docx' | 'pdf' | null>(null)
  const [descartar, setDescartar] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [bajando, setBajando] = useState<'docx' | 'pdf' | null>(null)
  const [marcas, setMarcas] = useState<Marcas>(SIN_MARCAS)
  const [aviso, setAviso] = useState('')
  const anterior = useRef(escrito?.texto ?? '')
  const ultimas = useRef<Marcas | null>(null)
  const hoja = useRef<HTMLDivElement>(null)

  const texto = escrito?.texto ?? ''
  const titulo = tituloDe(texto)
  const datos: Record<string, string> = { [FECHA_DE_HOY]: fechaLarga(), ...delEscrito, ...delAbogado }
  // la fecha de hoy la pone la app: no se pide
  const todos = espacios(texto).filter((e) => e !== FECHA_DE_HOY)
  const faltan = todos.filter((e) => !datos[e]?.trim())
  const editando = borrador !== null

  // al cambiar el escrito (Papiniano, Deshacer o a mano) se marca lo que cambió y se avisa a los lectores de pantalla
  useEffect(() => {
    const antes = anterior.current
    anterior.current = texto
    if (!texto || antes === texto) return
    if (!antes) {
      setAviso('Papiniano terminó el escrito.')
      return
    }
    const m = comparar(antes, texto)
    ultimas.current = m
    setMarcas(m)
    setAviso(resumen(m))
  }, [texto])

  // los datos se abren si los pide el abogado o si acaba de poner un modelo
  const datosAbiertos = verDatos || pedirDatos
  function cerrarDatos() {
    setVerDatos(false)
    if (pedirDatos) alPedirDatos?.()
  }

  // «Ver el cambio en el escrito» desde la conversación: se vuelve a marcar el último cambio
  useEffect(() => {
    if (!pulso) return
    // se quitan y se vuelven a poner un momento después, para que el resaltado arranque otra vez
    let t = setTimeout(() => {
      setMarcas(SIN_MARCAS)
      t = setTimeout(() => {
        if (ultimas.current) setMarcas({ ...ultimas.current })
        else hoja.current?.scrollTo({ top: 0, behavior: 'smooth' })
      }, 50)
    })
    return () => clearTimeout(t)
  }, [pulso])

  // la hoja va a la primera marca; las marcas se van solas
  useEffect(() => {
    if (!marcas.nuevos.size && !marcas.quitados.size) return
    hoja.current?.querySelector('[data-marca]')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const t = setTimeout(() => setMarcas(SIN_MARCAS), 4500)
    return () => clearTimeout(t)
  }, [marcas])

  function ponerDato(espacio: string, valor: string) {
    if (esDelAbogado(espacio)) {
      const nuevos = { ...delAbogado, [espacio]: valor }
      setDelAbogado(nuevos)
      guardar(claveAbogado(usuarioId), nuevos)
    } else {
      const nuevos = { ...delEscrito, [espacio]: valor }
      setDelEscrito(nuevos)
      if (convId) guardar(claveDatos(usuarioId, convId), nuevos)
    }
  }

  /** Si faltan datos, primero se avisa cuáles; «Descargar así» lo baja igual (con confirmar) */
  async function bajar(formato: 'docx' | 'pdf', confirmar = false) {
    if (faltan.length && !confirmar) {
      setPorBajar(formato)
      return
    }
    setPorBajar(null)
    setBajando(formato)
    try {
      await descargar(`/api/escrito/${formato}`, { texto: llenar(texto, datos) })
      toast.success(
        faltan.length
          ? `Descargado con ${faltan.length === 1 ? '1 dato' : `${faltan.length} datos`} sin llenar: ` +
              (formato === 'docx' ? 'salen marcados en amarillo.' : 'salen entre corchetes.')
          : 'Escrito descargado.',
      )
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setBajando(null)
    }
  }

  async function deshacer() {
    if (!convId) return
    try {
      alCambiar(await api.post<Escrito>(`/api/conversaciones/${convId}/escrito/deshacer`))
      toast.success('Se deshizo el último cambio.')
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  async function guardarCorreccion() {
    if (!convId || borrador === null) return
    setGuardando(true)
    try {
      alCambiar(await api.put<Escrito>(`/api/conversaciones/${convId}/escrito`, { texto: borrador }))
      setBorrador(null)
      toast.success('Cambios guardados.')
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setGuardando(false)
    }
  }

  function cancelar() {
    if (borrador !== null && borrador.trim() !== texto.trim()) setDescartar(true)
    else setBorrador(null)
  }

  const ocupado = trabajando || Boolean(bajando)
  const corregir = () => setBorrador(texto)
  const marcaFaltan = faltan.length > 0 && (
    <span className="rounded-full bg-aviso px-2 text-[0.8rem] font-bold text-aviso-texto">{faltan.length}</span>
  )
  const botonDescargar = (formato: 'docx' | 'pdf', principal: boolean) => (
    <Button
      variant={principal ? 'default' : 'outline'}
      className={cn('h-11', !principal && 'border-regla')}
      disabled={!texto || ocupado}
      onClick={() => bajar(formato)}
    >
      {bajando === formato ? <Loader2 className="animate-spin" /> : formato === 'docx' ? <FileText /> : <FileDown />}
      {formato === 'docx' ? 'Generar en Word' : 'Generar en PDF'}
    </Button>
  )

  return (
    <section aria-label={`Escrito: ${titulo}`} className="flex min-h-0 flex-1 flex-col bg-muted/60">
      <div className="space-y-2 border-b border-papel-borde bg-background px-4 py-3 md:px-5">
        {compacto ? (
          <h2 className="sr-only">{titulo}</h2>
        ) : (
          <div className="flex items-center gap-2">
            <FileText className="size-5 shrink-0 text-marca-texto" />
            <h2 className="min-w-0 flex-1 truncate font-heading text-lg font-medium text-ink" title={titulo}>{titulo}</h2>
            {alOcultar && (
              <Button variant="ghost" className="h-11 text-ink-soft" onClick={alOcultar}>
                <PanelRightClose /> Ocultar
              </Button>
            )}
          </div>
        )}

        {editando ? (
          <div className="space-y-2">
            <p className="text-[0.9rem] text-ink">
              Está corrigiendo a mano. Deje una línea en blanco entre párrafos; al guardar vuelve el formato.
              {!compacto && ' Los nombres y cédulas van en «Datos por llenar», no aquí: así no se le envían a la IA.'}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" className="h-11 border-regla" disabled={guardando} onClick={cancelar}>
                Cancelar
              </Button>
              <Button className="h-11" disabled={guardando || !borrador.trim()} onClick={guardarCorreccion}>
                {guardando && <Loader2 className="animate-spin" />} Guardar cambios
              </Button>
            </div>
          </div>
        ) : compacto ? (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon-grande"
              className="border-regla"
              disabled={!escrito?.deshacer || ocupado}
              onClick={deshacer}
              aria-label="Deshacer el último cambio"
              title="Deshacer el último cambio"
            >
              <Undo2 />
            </Button>
            <Button variant="outline" className="h-11 min-w-0 flex-1 border-regla" disabled={!texto} onClick={() => setVerDatos(true)}>
              <span className="truncate">Por llenar</span> {marcaFaltan}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button className="h-11" disabled={!texto || ocupado}>
                  {bajando ? <Loader2 className="animate-spin" /> : <Download />} Descargar <ChevronDown />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem className="h-11 text-[0.95rem]" onSelect={() => bajar('docx')}>
                  <FileText /> Generar en Word
                </DropdownMenuItem>
                <DropdownMenuItem className="h-11 text-[0.95rem]" onSelect={() => bajar('pdf')}>
                  <FileDown /> Generar en PDF
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="h-11 border-regla" disabled={!escrito?.deshacer || ocupado} onClick={deshacer}>
              <Undo2 /> Deshacer
            </Button>
            <Button variant="outline" className="h-11 border-regla" disabled={!texto || ocupado} onClick={corregir}>
              <PencilLine /> Corregir a mano
            </Button>
            <Button variant="outline" className="h-11 border-regla" disabled={!texto} onClick={() => setVerDatos(true)}>
              <UserRound /> Datos por llenar {marcaFaltan}
            </Button>
          </div>
        )}
      </div>

      <div ref={hoja} className="@container relative min-h-0 flex-1 overflow-y-auto px-3 py-5 md:px-6 md:py-8">
        <p role="status" className="sr-only">{aviso}</p>
        {trabajando && (
          <p className="sticky top-0 z-10 mx-auto mb-4 flex w-fit items-center gap-2 rounded-full border border-regla bg-background px-4 py-2 text-[0.9rem] text-ink shadow-sm">
            <Loader2 className="size-4 animate-spin text-marca-texto" />
            {texto ? 'Papiniano está cambiando el escrito…' : 'Papiniano está escribiendo el escrito…'}
          </p>
        )}
        {editando ? (
          <textarea
            value={borrador}
            onChange={(e) => setBorrador(e.target.value)}
            aria-label="Texto del escrito"
            autoFocus
            className={cn(
              'hoja block min-h-[70dvh] resize-none outline-none field-sizing-content focus-visible:ring-3 focus-visible:ring-ring/50',
              RELLENO,
            )}
          />
        ) : texto ? (
          <>
            <div className={cn('transition-opacity', trabajando && 'opacity-60')}>
              <Hoja texto={texto} datos={datos} marcas={marcas} />
            </div>
            {compacto && (
              <div className="mt-4 text-center">
                <Button variant="ghost" className="h-11 text-ink-soft" disabled={ocupado} onClick={corregir}>
                  <PencilLine /> Corregir a mano
                </Button>
              </div>
            )}
          </>
        ) : (
          <div className={cn('hoja space-y-4', RELLENO)} aria-hidden>
            {[40, 100, 92, 97, 60, 100, 88].map((w, i) => (
              <div key={i} className="h-3.5 animate-pulse rounded bg-neutral-200" style={{ width: `${w}%` }} />
            ))}
          </div>
        )}
      </div>

      {!compacto && !editando && (
        <div className="@container space-y-2 border-t border-papel-borde bg-background px-4 py-3 md:px-5">
          <p className="text-[0.9rem] text-ink-soft">
            {!texto
              ? 'Cuando esté listo, descárguelo aquí.'
              : faltan.length
                ? `${faltan.length === 1 ? 'Falta 1 dato' : `Faltan ${faltan.length} datos`} por llenar: salen en amarillo en el Word.`
                : 'Todos los datos están llenos. Revíselo antes de presentarlo.'}
          </p>
          <div className="grid grid-cols-2 gap-2 @lg:flex @lg:justify-end">
            {botonDescargar('docx', true)}
            {botonDescargar('pdf', false)}
          </div>
        </div>
      )}

      <Dialog open={datosAbiertos} onOpenChange={(a) => (a ? setVerDatos(true) : cerrarDatos())}>
        <DialogContent className="flex max-h-[88dvh] flex-col sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl font-medium">Datos por llenar</DialogTitle>
            <DialogDescription>
              Se ponen en el Word y el PDF al descargarlos. No se le envían a Papiniano ni a la IA, y se guardan solo en
              este equipo. Lo que deje en blanco sale marcado para llenarlo después.
            </DialogDescription>
          </DialogHeader>
          <div className="-mx-1 min-h-0 flex-1 space-y-6 overflow-y-auto px-1 pb-1">
            {todos.length ? (
              [
                ...agrupar(todos.filter((e) => !esDelAbogado(e))).map(([grupo, lista]) => [grupo, '', lista] as const),
                ['Suyos', 'Se guardan para todos sus escritos.', todos.filter(esDelAbogado)] as const,
              ].map(([grupo, nota, lista]) => {
                const vacios = lista.filter((e) => !datos[e]?.trim()).length
                return (
                  lista.length > 0 && (
                    <fieldset key={grupo} className="space-y-3">
                      <legend className="mb-1 font-bold text-ink">
                        {grupo}
                        {vacios > 0 && <span className="ml-2 font-normal text-ink-soft">(faltan {vacios})</span>}
                      </legend>
                      {nota && <p className="-mt-2 text-[0.88rem] text-ink-soft">{nota}</p>}
                      {lista.map((e) => (
                        <div key={e} className="space-y-1.5">
                          <Label htmlFor={`dato-${e}`} className="text-[0.9rem] text-ink-soft">{etiqueta(e)}</Label>
                          <Input
                            id={`dato-${e}`}
                            value={datos[e] ?? ''}
                            onChange={(ev) => ponerDato(e, ev.target.value)}
                            autoComplete="off"
                            className="h-11 bg-background text-base md:text-base"
                          />
                        </div>
                      ))}
                    </fieldset>
                  )
                )
              })
            ) : (
              <p className="text-ink">El escrito no tiene datos por llenar.</p>
            )}
          </div>
          <DialogFooter>
            <Button size="grande" onClick={cerrarDatos}>Listo</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(porBajar)} onOpenChange={(abierto) => !abierto && setPorBajar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">
              {faltan.length === 1 ? 'Falta 1 dato' : `Faltan ${faltan.length} datos`} por llenar
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>Si lo descarga así, {porBajar === 'pdf' ? 'salen entre corchetes' : 'salen marcados en amarillo'}:</p>
                <ul className="list-disc space-y-0.5 pl-5 text-ink">
                  {faltan.slice(0, 6).map((e) => <li key={e}>{etiqueta(e)}</li>)}
                  {faltan.length > 6 && <li>y {faltan.length - 6} más</li>}
                </ul>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande" onClick={() => porBajar && bajar(porBajar, true)}>
              Descargar así
            </AlertDialogCancel>
            <AlertDialogAction
              size="grande"
              onClick={() => {
                setPorBajar(null)
                setVerDatos(true)
              }}
            >
              <UserRound /> Llenar los datos
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={descartar} onOpenChange={setDescartar}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Descartar su corrección?</AlertDialogTitle>
            <AlertDialogDescription>Lo que cambió a mano se pierde y el escrito queda como estaba.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande">Seguir corrigiendo</AlertDialogCancel>
            <AlertDialogAction variant="peligro" size="grande" onClick={() => setBorrador(null)}>
              Descartar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
