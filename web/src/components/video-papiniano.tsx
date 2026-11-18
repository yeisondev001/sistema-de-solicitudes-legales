import { useEffect, useRef, useState } from 'react'
import {
  CalendarDays, Check, ChevronLeft, ChevronRight, ExternalLink, FileDown, FileText, FolderClosed, History, House, LibraryBig, Loader2,
  MessageSquarePlus, MousePointer2, PencilLine, PenLine, Play, SendHorizontal, Undo2, UserRound, X,
} from 'lucide-react'
import { Papiniano } from '@/components/papiniano'
import { cn } from '@/lib/utils'

const PREGUNTA = '¿Qué pasa si se aprobó un deslinde sin citar a los colindantes?'
const RESPUESTA =
  'La falta de citación de los colindantes puede llevar a anular el deslinde, porque afecta su derecho de defensa.'
const PALABRAS = RESPUESTA.split(' ')
const PEDIDO = 'Redácteme la instancia para pedir que anulen ese deslinde.'
// la instancia que sale en la hoja: [tipo, lo que va en negrita, el resto]; lo que está entre corchetes son los datos por llenar
const INSTANCIA: ['titulo' | 'centro' | '', string, string][] = [
  ['titulo', 'INSTANCIA EN LITIS SOBRE DERECHOS REGISTRADOS EN NULIDAD DE DESLINDE', ''],
  ['', 'AL:', ' Juez Presidente del Tribunal de Tierras de Jurisdicción Original de [DISTRITO]'],
  ['', 'REFERENCIA:', ' Parcela núm. [NÚMERO DE PARCELA]'],
  ['centro', 'HONORABLE MAGISTRADO:', ''],
  ['', '', 'El señor [NOMBRE DEL CLIENTE], dominicano, mayor de edad, portador de la cédula núm. [CÉDULA], tiene a bien exponer lo siguiente:'],
  ['', 'ATENDIDO:', ' A que los trabajos de deslinde de la Parcela núm. [NÚMERO DE PARCELA] fueron aprobados sin citar a los colindantes;'],
  ['', 'ATENDIDO:', ' A que esa falta de citación viola su derecho de defensa, y por eso los trabajos pueden ser anulados;'],
]
// la página del Boletín que abre el visor (texto de ejemplo); el tercer párrafo es el citado
const BOLETIN = [
  'Considerando, que en su memorial de casación la parte recurrente invoca el medio siguiente: Único medio: Violación al derecho de defensa;',
  'Considerando, que la parte recurrente alega, en síntesis, que el tribunal a quo aprobó los trabajos de deslinde sin que fueran citados los colindantes de la parcela, quienes por esa razón no pudieron presentar sus reparos;',
  'Considerando, que la citación de los colindantes es una formalidad sustancial del procedimiento de deslinde, pues tiene por finalidad garantizar su derecho de defensa; que su omisión afecta la validez de los trabajos así aprobados;',
  'Considerando, que al no ponderar esa omisión, el tribunal a quo incurrió en el vicio denunciado, por lo que procede casar la sentencia impugnada;',
  'Por tales motivos, Primero: Casa la sentencia dictada por el Tribunal Superior de Tierras, y envía el asunto por ante el mismo tribunal, integrado por otros jueces;',
]
// el menú de la app
const SALAS: [React.ComponentType<{ className?: string }>, string][] = [
  [House, 'Escritorio'], [Papiniano, 'Papiniano'], [LibraryBig, 'Biblioteca'], [FolderClosed, 'Expedientes'],
  [PenLine, 'Redacción'], [CalendarDays, 'Agenda'],
]

// cuándo pasa cada cosa, en milisegundos desde que empieza; al llegar a «fin» vuelve a empezar.
// El escrito sale apenas lo pide (esperar ahí se hacía largo) y la página del Boletín queda abierta lo justo para leerla.
const T = {
  pregunta: 600, enviada: 2900, busca: 3200, leyo: 4500, responde: 5000, cita: 7200,
  tocaCita: 8100, pagina: 8700, cierraPagina: 12900,
  pedido: 13500, pedidoEnviado: 15500, hoja: 15900, texto: 16900,
  word: 20000, descargado: 20800, fin: 24500,
}
const MS_LETRA = 32
const MS_PALABRA = 85
const MS_PARRAFO = 300
const LISTO = T.texto + INSTANCIA.length * MS_PARRAFO
// la pantalla se dibuja al tamaño de una laptop, como se ve la app de verdad, y se achica para que quepa
const ANCHO = 1200
const ALTO = 780
const quieto = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const tecleado = (texto: string, desde: number, t: number) =>
  texto.slice(0, Math.max(0, Math.floor((t - desde) / MS_LETRA)))

/**
 * El «video» de la página pública: Papiniano por dentro, con la misma cara de la app. El abogado escribe la pregunta,
 * Papiniano busca y responde con citas, el abogado toca la cita y se abre el visor con la página del Boletín Judicial
 * (así se ve que es real), y después Papiniano le redacta la instancia en el panel de al lado, que se baja en Word.
 * No es un archivo de video sino una animación (pesa casi nada). Es una ilustración, no una consulta real.
 * Arranca sola cuando se ve en pantalla y se repite, sin barra ni botones; tocándola se pausa.
 * Sin movimiento (preferencia del sistema) queda quieta en la respuesta hasta que la toquen.
 */
export function VideoPapiniano() {
  const [t, setT] = useState(() => (quieto() ? T.cita + 600 : 0))
  const [pausado, setPausado] = useState(quieto)
  const [visible, setVisible] = useState(false)
  const [escala, setEscala] = useState(0.8)
  const caja = useRef<HTMLDivElement>(null)
  const andando = visible && !pausado

  useEffect(() => {
    if (!caja.current) return
    const mirador = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.3 })
    const medidor = new ResizeObserver(([e]) => setEscala(e.contentRect.width / ANCHO))
    mirador.observe(caja.current)
    medidor.observe(caja.current)
    return () => {
      mirador.disconnect()
      medidor.disconnect()
    }
  }, [])

  useEffect(() => {
    if (!andando) return
    let antes = performance.now()
    let id = requestAnimationFrame(function cuadro(ahora) {
      // tope por cuadro: si el celular se traba un momento, sigue sin saltarse media escena
      const paso = Math.min(ahora - antes, 250)
      antes = ahora
      setT((x) => (x + paso >= T.fin ? 0 : x + paso))
      id = requestAnimationFrame(cuadro)
    })
    return () => cancelAnimationFrame(id)
  }, [andando])

  return (
    <div
      ref={caja}
      className="relative overflow-hidden rounded-xl border border-papel-borde bg-background shadow-[0_40px_80px_-30px_rgb(40_25_15/0.45)]"
      style={{ height: ALTO * escala }}
    >
      <p className="sr-only">
        Demostración animada de Papiniano: el abogado escribe una pregunta, Papiniano busca en las sentencias y las leyes
        y le responde con la cita; el abogado toca la cita y se abre la página del Boletín Judicial; después le pide la
        instancia y Papiniano la redacta en el panel de al lado, lista para bajar en Word.
      </p>
      <div aria-hidden="true" className="absolute top-0 left-0 origin-top-left" style={{ width: ANCHO, height: ALTO, transform: `scale(${escala})` }}>
        <PantallaApp t={t} />
      </div>
      {/* corre sola como un video, sin barra; tocándola se pausa (para quien le molesta el movimiento) */}
      <button
        type="button"
        onClick={() => setPausado((p) => !p)}
        aria-label={pausado ? 'Reproducir la demostración' : 'Pausar la demostración'}
        className="absolute inset-0 cursor-default focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-marca"
      >
        {pausado && (
          <span className="absolute right-4 bottom-4 flex size-12 items-center justify-center rounded-full bg-boton text-sobre-boton shadow-lg">
            <Play className="size-5 translate-x-px fill-current" />
          </span>
        )}
      </button>
    </div>
  )
}

/** La pantalla de la app en el momento t: el menú, la conversación, el panel del escrito al lado y el visor encima */
function PantallaApp({ t }: { t: number }) {
  const conPanel = t >= T.hoja
  return (
    <div className="relative flex size-full text-ink">
      <aside className="flex w-[200px] shrink-0 flex-col bg-panel px-3 pt-5 pb-4 text-[#F1E8DA]">
        <div className="flex items-center gap-2.5 px-2 pb-6">
          <Papiniano className="size-10" decorativo />
          <span className="font-heading text-[1.35rem] font-medium">Papiniano</span>
        </div>
        <div className="space-y-1">
          {SALAS.map(([Icono, nombre], i) => (
            <div
              key={nombre}
              className={cn('flex h-11 items-center gap-3 rounded-lg px-3 text-[1rem]', i === 1 && 'bg-[#F1E8DA] font-bold text-panel')}
            >
              <Icono className={i === 1 ? 'size-6' : 'size-[1.15rem]'} />
              {nombre}
            </div>
          ))}
        </div>
        <div className="mt-auto flex items-center gap-3 px-2">
          <span className="flex size-10 items-center justify-center rounded-full bg-[#F1E8DA] font-bold text-panel">M</span>
          <span className="leading-tight">
            <b className="block text-[0.95rem]">Lic. Martínez</b>
            <span className="text-[0.82rem] text-[#E2C9A8]">Plan Abogado</span>
          </span>
        </div>
      </aside>
      <div className="relative min-w-0 flex-1">
        <Conversacion t={t} angosta={conPanel} />
        {conPanel && <PanelEscrito t={t} />}
      </div>
      {t >= T.pagina && t < T.cierraPagina && <Visor />}
    </div>
  )
}

function Conversacion({ t, angosta }: { t: number; angosta: boolean }) {
  const palabras = Math.min(PALABRAS.length, Math.floor((t - T.responde) / MS_PALABRA) + 1)
  const pregunta = t >= T.pregunta && t < T.enviada
  const pedido = t >= T.pedido && t < T.pedidoEnviado
  const escribiendo = pregunta || pedido
  const texto = pregunta ? tecleado(PREGUNTA, T.pregunta, t) : pedido ? tecleado(PEDIDO, T.pedido, t) : ''
  const envia = (t >= T.enviada - 220 && t < T.enviada) || (t >= T.pedidoEnviado - 220 && t < T.pedidoEnviado)
  return (
    <section
      className="flex h-full flex-col bg-background transition-[width] duration-500 ease-out"
      style={{ width: angosta ? '50%' : '100%' }}
    >
      <div className="flex h-[66px] shrink-0 items-center gap-3 border-b border-papel-borde px-6">
        <Papiniano className="size-10" decorativo />
        <span className="font-heading text-[1.5rem] font-medium">Papiniano</span>
        <span className="ml-auto flex gap-5 text-ink-soft">
          <History className="size-5" />
          <MessageSquarePlus className="size-5" />
        </span>
      </div>
      {/* antes de la primera pregunta, el saludo de una conversación nueva */}
      {t < T.enviada && (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 pb-10 text-center">
          <Papiniano className="size-20" decorativo />
          <p className="font-heading text-[2rem] font-medium">Buenos días, licenciado.</p>
          <p className="text-[1.05rem] text-ink-soft">Pregúnteme por una sentencia o una ley, o pídame un escrito.</p>
        </div>
      )}
      {/* como en la app, lo nuevo sale abajo y empuja lo anterior hacia arriba */}
      <div
        className={cn(
          'flex min-h-0 flex-1 flex-col justify-end overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,black_3rem)]',
          t < T.enviada && 'hidden',
        )}
      >
        <div className="mx-auto flex w-full max-w-[46rem] shrink-0 flex-col gap-4 px-7 pb-5">
          {t >= T.enviada && <Burbuja>{PREGUNTA}</Burbuja>}
          {t >= T.busca && (
            <div className="demo-aparece flex flex-wrap gap-2 text-[0.85rem] text-ink-soft">
              {t < T.leyo ? (
                <span className="inline-flex items-center gap-2 rounded-full bg-[#F1E6DE] px-3 py-1">
                  Buscando en las sentencias y las leyes
                  <span className="escribiendo-puntos inline-flex gap-1"><i /><i /><i /></span>
                </span>
              ) : (
                ['Buscó en las sentencias y las leyes', 'Leyó 3 sentencias', '1 reglamento'].map((c) => (
                  <span key={c} className="rounded-full bg-[#F1E6DE] px-3 py-1">{c}</span>
                ))
              )}
            </div>
          )}
          {t >= T.responde && (
            <Respuesta>
              <p className="font-heading text-[1.12rem] leading-relaxed">
                {PALABRAS.slice(0, palabras).join(' ')}
                {palabras === PALABRAS.length &&
                  [1, 2].map((n) => (
                    <span key={n} className="ml-1.5 rounded bg-[#F1E6DE] px-1.5 py-px font-sans text-[0.82rem] font-bold text-roble">{n}</span>
                  ))}
              </p>
              {t >= T.cita && (
                <div className="demo-aparece space-y-1.5 rounded-lg border border-papel-borde bg-background p-3.5">
                  <p className="flex gap-2 text-[0.92rem] font-bold">
                    <span className="text-marca-texto">[1]</span> Sentencia de la Tercera Sala — Boletín Judicial
                  </p>
                  <p className="text-[0.9rem] text-ink-soft italic">«…la citación de los colindantes es una formalidad sustancial del procedimiento de deslinde…»</p>
                  <div className="flex flex-wrap gap-1 text-[0.9rem]">
                    <span className="relative inline-flex">
                      <span
                        className={cn(
                          'inline-flex h-10 items-center gap-2 rounded-md px-3 whitespace-nowrap text-ink transition-colors',
                          t >= T.pagina - 250 && 'bg-[#F1E6DE]',
                        )}
                      >
                        <FileText className="size-4" /> Ver la página aquí
                      </span>
                      {t >= T.tocaCita && t < T.pagina + 200 && <Puntero clic={t >= T.pagina - 250} />}
                    </span>
                    <span className="inline-flex h-10 items-center gap-2 px-3 whitespace-nowrap text-ink-soft">
                      <ExternalLink className="size-4" /> Abrir en el Boletín Judicial
                    </span>
                  </div>
                </div>
              )}
            </Respuesta>
          )}
          {t >= T.pedidoEnviado && <Burbuja>{PEDIDO}</Burbuja>}
          {t >= T.pedidoEnviado + 200 && (
            <Respuesta>
              {t < LISTO ? (
                <p className="inline-flex items-center gap-2 text-ink-soft">
                  Redactando el escrito <span className="escribiendo-puntos inline-flex gap-1"><i /><i /><i /></span>
                </p>
              ) : (
                <div className="demo-aparece space-y-3">
                  <p className="font-heading text-[1.12rem] leading-relaxed">
                    Listo, redacté la instancia. Faltan 4 datos del caso: llénelos en «Datos por llenar».
                  </p>
                  <span className="inline-flex items-center gap-2 rounded-lg border border-papel-borde bg-background px-3.5 py-2 text-[0.95rem]">
                    <FileText className="size-[18px] text-marca-texto" /> Ver el escrito
                  </span>
                </div>
              )}
            </Respuesta>
          )}
        </div>
      </div>
      <div className="shrink-0 border-t border-papel-borde px-7 pt-3.5 pb-3">
        <div className="mx-auto max-w-[46rem] space-y-2">
          <div className="flex items-center gap-3 rounded-2xl border border-papel-borde bg-card py-2.5 pr-2.5 pl-4">
            <p className="min-h-[1.6rem] flex-1 text-[1rem] leading-snug">
              {texto || (!escribiendo && <span className="text-ink-soft">Pregúntele a Papiniano o pídale un escrito…</span>)}
              {escribiendo && <span className="demo-cursor ml-px inline-block h-[1.05em] w-px translate-y-[0.15em] bg-ink" />}
            </p>
            <span
              className={cn(
                'flex size-10 shrink-0 items-center justify-center rounded-full bg-boton text-sobre-boton transition-transform',
                envia && 'scale-90',
              )}
            >
              <SendHorizontal className="size-[18px]" />
            </span>
          </div>
          <p className="text-[0.75rem] text-ink-soft">
            Herramienta de apoyo: verifique cada cita en la fuente antes de usarla. No escriba datos personales de clientes en la consulta.
          </p>
        </div>
      </div>
    </section>
  )
}

/** El visor de la app: la página del Boletín Judicial que se abre al tocar la cita, con el párrafo citado resaltado */
function Visor() {
  return (
    <div className="demo-aparece absolute inset-0 z-10 flex items-center justify-center bg-[rgb(20_14_10/0.55)]">
      <div className="flex h-[710px] w-[880px] flex-col gap-3 rounded-xl bg-background p-5 shadow-2xl">
        <div className="flex items-center gap-3">
          <p className="font-heading text-[1.1rem] font-medium">Sentencia de la Tercera Sala — Boletín Judicial</p>
          <X className="ml-auto size-5 text-ink-soft" />
        </div>
        <div className="min-h-0 flex-1 overflow-hidden rounded-md border border-papel-borde bg-white px-16 pt-10 font-['Times_New_Roman',Times,serif] text-[#1a1a1a]">
          <div className="flex justify-between border-b border-[#bbb] pb-1.5 text-[0.85rem] italic">
            <span>Boletín Judicial</span>
            <span>412</span>
          </div>
          <p className="mt-6 text-center text-[1rem] font-bold tracking-[0.08em]">TERCERA SALA</p>
          <div className="mt-5 space-y-3.5 text-justify text-[1.12rem] leading-[1.6]">
            {BOLETIN.map((p, i) => (
              <p key={i} className={cn(i === 2 && 'demo-resalte -mx-2 rounded-sm px-2 py-1')}>{p}</p>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between text-[0.92rem] text-ink-soft">
          <span className="flex items-center gap-2">
            <ChevronLeft className="size-5" /> <span className="min-w-28 text-center">Página 412 de 1.236</span> <ChevronRight className="size-5" />
          </span>
          <span className="inline-flex h-10 items-center gap-2 rounded-lg border border-regla px-3.5 font-bold text-ink">
            <ExternalLink className="size-4" /> Abrir el PDF oficial
          </span>
        </div>
      </div>
    </div>
  )
}

/** El panel del escrito, al lado de la conversación, como en la app: primero «escribiendo», después la hoja y el Word */
function PanelEscrito({ t }: { t: number }) {
  const conTexto = t >= T.texto
  const parrafos = Math.max(1, Math.floor((t - T.texto) / MS_PARRAFO) + 1)
  const clic = t >= T.word + 550
  return (
    <section className="demo-panel absolute inset-y-0 right-0 flex w-1/2 flex-col border-l border-papel-borde bg-[#EFE9DF]">
      <div className="space-y-3 border-b border-papel-borde bg-background px-5 py-3">
        <div className="flex items-center gap-2.5">
          <FileText className="size-5 shrink-0 text-marca-texto" />
          <span className="truncate font-heading text-[1.15rem] font-medium">Instancia en litis sobre derechos registrados</span>
          <span className="ml-auto shrink-0 text-[0.85rem] text-ink-soft">Ocultar</span>
        </div>
        <div className={cn('flex gap-2 text-[0.88rem] whitespace-nowrap', !conTexto && 'opacity-50')}>
          <span className="inline-flex h-10 items-center gap-2 rounded-md border border-regla px-3 opacity-50"><Undo2 className="size-4" /> Deshacer</span>
          <span className="inline-flex h-10 items-center gap-2 rounded-md border border-regla bg-card px-3"><PencilLine className="size-4" /> Corregir a mano</span>
          <span className="inline-flex h-10 items-center gap-2 rounded-md border border-regla bg-card px-3">
            <UserRound className="size-4" /> Datos por llenar {conTexto && <b className="rounded bg-[#fff1a3] px-1.5 text-[#4a3b00]">4</b>}
          </span>
        </div>
      </div>
      <div className="relative min-h-0 flex-1 overflow-hidden px-6 py-6 [mask-image:linear-gradient(to_top,transparent,black_3rem)]">
        {t < LISTO && (
          <p className="absolute top-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-full border border-regla bg-background px-4 py-2 text-[0.9rem] whitespace-nowrap shadow-sm">
            <Loader2 className="size-4 animate-spin text-marca-texto" /> Papiniano está escribiendo el escrito…
          </p>
        )}
        {conTexto ? (
          <article className="hoja px-10 py-10 text-[0.92rem]">
            {INSTANCIA.slice(0, parrafos).map(([tipo, negrita, resto], i) => (
              <p
                key={i}
                className={cn('demo-aparece', tipo === 'titulo' && 'mb-[1.6em] text-center text-[1.08em] font-bold', tipo === 'centro' && 'text-center font-bold')}
              >
                {negrita && <strong>{negrita}</strong>}
                <ConDatos texto={resto} />
              </p>
            ))}
          </article>
        ) : (
          <div className="hoja space-y-4 px-10 py-12">
            {[40, 100, 92, 97, 60, 100, 88].map((w, i) => (
              <div key={i} className="h-3.5 animate-pulse rounded bg-neutral-200" style={{ width: `${w}%` }} />
            ))}
          </div>
        )}
      </div>
      <div className="space-y-2 border-t border-papel-borde bg-background px-5 py-3">
        <p className="text-[0.9rem] text-ink-soft">
          {conTexto ? 'Faltan 4 datos por llenar: salen en amarillo en el Word.' : 'Cuando esté listo, descárguelo aquí.'}
        </p>
        <div className="flex justify-end gap-2 text-[0.92rem] font-bold whitespace-nowrap">
          <span className="relative">
            <span
              className={cn(
                'inline-flex h-10 items-center gap-2 rounded-md bg-boton px-4 text-sobre-boton transition-transform',
                !conTexto && 'opacity-50',
                clic && t < T.descargado + 300 && 'scale-95',
              )}
            >
              <FileText className="size-[18px]" /> Generar en Word
            </span>
            {t >= T.word && t < T.descargado + 900 && <Puntero clic={clic} />}
          </span>
          <span className={cn('inline-flex h-10 items-center gap-2 rounded-md border border-regla bg-card px-4', !conTexto && 'opacity-50')}>
            <FileDown className="size-[18px]" /> Generar en PDF
          </span>
        </div>
      </div>
      {t >= T.descargado && (
        <p className="demo-aparece absolute inset-x-0 bottom-28 mx-auto flex w-max items-center gap-2.5 rounded-lg bg-panel px-4 py-3 text-[0.95rem] text-sobre-panel shadow-lg">
          <Check className="size-5 text-[#E2C29B]" /> Se bajó «Instancia nulidad de deslinde.docx»
        </p>
      )}
    </section>
  )
}

function Burbuja({ children }: { children: React.ReactNode }) {
  return (
    <p className="demo-aparece ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-panel px-4 py-3 text-[1rem] leading-snug text-sobre-panel">
      {children}
    </p>
  )
}

function Respuesta({ children }: { children: React.ReactNode }) {
  return (
    <div className="demo-aparece space-y-2">
      <p className="flex items-center gap-2 text-[0.92rem] font-bold">
        <Papiniano className="size-7" decorativo /> Papiniano
      </p>
      <div className="space-y-3 rounded-2xl rounded-tl-sm border border-papel-borde bg-card p-5">{children}</div>
    </div>
  )
}

/** Los datos por llenar, en amarillo como en la hoja de la app */
function ConDatos({ texto }: { texto: string }) {
  return (
    <>
      {texto.split(/(\[[^\]]+\])/).map((pieza, i) =>
        pieza.startsWith('[') ? <span key={i} className="por-llenar">{pieza}</span> : pieza,
      )}
    </>
  )
}

/** La flecha del ratón que toca el botón */
function Puntero({ clic }: { clic: boolean }) {
  return (
    <MousePointer2
      className={cn(
        'demo-puntero pointer-events-none absolute -right-3 -bottom-5 z-10 size-8 fill-white text-ink drop-shadow-md transition-transform',
        clic && 'scale-90',
      )}
    />
  )
}
