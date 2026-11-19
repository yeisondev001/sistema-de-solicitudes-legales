import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, BookOpenCheck, ChevronDown, FileSignature, FileUp, Landmark, Loader2, Mic, MicOff, PencilLine, Volume2, VolumeX, Scale, SendHorizontal,
  ShieldCheck, Sparkles, type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'
import { guardarDatosDelEscrito } from '@/components/escrito'
import { TituloSala } from '@/components/oficina'
import { NOMBRE_ASISTENTE, Papiniano } from '@/components/papiniano'
import { Seccion } from '@/components/seccion'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, ErrorApi, leerParaRedactar, redactarEscrito, type DocumentoLeido } from '@/lib/api'
import { hablar, hayVoz, useDictado, useVozAutomatica } from '@/lib/dictado'
import { useSesion } from '@/lib/sesion'
import { cn } from '@/lib/utils'

interface Pregunta {
  clave: string
  pregunta: string
  ayuda: string
  requerida: boolean
}

interface Tipo {
  clave: string
  nombre: string
  /** qué documento tiene que subir */
  documento: string
  /** lo que se le pregunta al abogado para «Hacerlo yo mismo» */
  preguntas: Pregunta[]
  /** los modelos de ese tipo, por si quiere elegir uno */
  modelos: { clave: string; nombre: string; materia: string }[]
}

const ICONOS: Record<string, LucideIcon> = {
  demanda: FileSignature,
  defensa: ShieldCheck,
  apelacion: Scale,
  casacion: Landmark,
  constitucional: BookOpenCheck,
}

const MAX_MB = 20

/** «PERSONA 3» → «nombres»: para decir cuántos datos se quitaron */
const NOMBRES: Record<string, [string, string]> = {
  PERSONA: ['nombre', 'nombres'],
  CÉDULA: ['cédula', 'cédulas'],
  RNC: ['RNC', 'RNC'],
  PASAPORTE: ['pasaporte', 'pasaportes'],
  TELÉFONO: ['teléfono', 'teléfonos'],
  CORREO: ['correo', 'correos'],
  DOMICILIO: ['domicilio', 'domicilios'],
}

/**
 * Sala «Redacción». El abogado elige qué quiere redactar y cómo:
 *  - «A partir de un documento»: sube el de la otra parte (la demanda que recibió, la sentencia que va a
 *    recurrir…), revisa que no quede ningún dato de las personas y Papiniano redacta la respuesta.
 *  - «Hacerlo yo mismo»: contesta lo que es único de su caso (tribunal, hechos, motivos, qué pide…) y
 *    Papiniano redacta con el modelo de ese tipo y los artículos que encuentre en la biblioteca.
 * El escrito se abre en la hoja de Papiniano, con los datos de las personas ya puestos en este equipo
 * (Ley 172-13: nunca van a la IA).
 */
export default function Redactar() {
  const navegar = useNavigate()
  const { perfil } = useSesion()
  const [tipos, setTipos] = useState<Tipo[] | null>(null)
  const [tipo, setTipo] = useState<Tipo | null>(null)
  const [modo, setModo] = useState<'documento' | 'propio' | null>(null)
  // a partir de un documento
  const [indicaciones, setIndicaciones] = useState('')
  const [leyendo, setLeyendo] = useState(false)
  const [documento, setDocumento] = useState<DocumentoLeido | null>(null)
  const [texto, setTexto] = useState('')
  const [verDatos, setVerDatos] = useState(false)
  // hacerlo yo mismo
  const [respuestas, setRespuestas] = useState<Record<string, string>>({})
  const [modelo, setModelo] = useState('')   // '' = que elija Papiniano
  const [avance, setAvance] = useState<string | null>(null)
  const campo = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.get<Tipo[]>('/api/redactar').then(setTipos).catch((e: ErrorApi) => toast.error(e.message))
  }, [])

  async function leer(archivo: File) {
    if (archivo.size > MAX_MB * 1024 * 1024) {
      toast.error(`«${archivo.name}» pesa más de ${MAX_MB} MB.`)
      return
    }
    setLeyendo(true)
    try {
      const d = await leerParaRedactar(archivo)
      setDocumento(d)
      setTexto(d.texto)
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setLeyendo(false)
    }
  }

  /** Termina igual en los dos caminos: los datos quedan llenos en este equipo y se abre la hoja */
  async function terminar(pedido: Parameters<typeof redactarEscrito>[0], mapa: Record<string, string>) {
    setAvance('Pensando…')
    try {
      const r = await redactarEscrito(pedido, setAvance)
      guardarDatosDelEscrito(perfil.id, r.conv_id, { ...mapa, ...(r.mapa ?? {}) })
      navegar(`/papiniano/${r.conv_id}`)
    } catch (e) {
      toast.error((e as ErrorApi).message)
      setAvance(null)
    }
  }

  function redactarDocumento() {
    if (!tipo || !documento) return
    terminar({ tipo: tipo.clave, modo: 'documento', texto, nombre: documento.nombre, indicaciones }, documento.mapa)
  }

  function redactarPropio() {
    if (!tipo) return
    terminar({ tipo: tipo.clave, modo: 'propio', respuestas, modelo: modelo || null }, {})
  }

  function volver() {
    if (documento) {
      setDocumento(null)
      setTexto('')
    } else if (modo) {
      setModo(null)
    } else {
      setTipo(null)
      setRespuestas({})
      setModelo('')
    }
  }

  const quitados = documento
    ? Object.entries(documento.cuenta).map(([k, n]) => `${n} ${(NOMBRES[k] ?? [k.toLowerCase(), k.toLowerCase()])[n === 1 ? 0 : 1]}`)
    : []

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala
        titulo="Redacción"
        sub="Papiniano le redacta el escrito a partir del documento de la otra parte o con los datos de su caso."
      />

      {/* 1. qué quiere redactar */}
      {!tipo ? (
        <Seccion titulo="¿Qué quiere redactar?">
          {tipos ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {tipos.map((t) => {
                const Icono = ICONOS[t.clave] ?? FileSignature
                return (
                  <button
                    key={t.clave}
                    type="button"
                    onClick={() => setTipo(t)}
                    className="flex min-h-24 flex-col items-start gap-2 rounded-xl border border-papel-borde bg-background p-4 text-left transition-colors hover:border-marca focus-visible:border-marca focus-visible:outline-none"
                  >
                    <Icono className="size-6 text-marca-texto" aria-hidden />
                    <span className="font-bold text-ink">{t.nombre}</span>
                  </button>
                )
              })}
            </div>
          ) : (
            <p className="flex items-center gap-2 text-ink-soft">
              <Loader2 className="size-4 animate-spin" /> Cargando…
            </p>
          )}
        </Seccion>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="ghost" className="h-11 text-ink-soft" onClick={volver} disabled={Boolean(avance)}>
              <ArrowLeft /> Atrás
            </Button>
            <p className="text-ink">
              Va a redactar: <strong>{tipo.nombre}</strong>
            </p>
          </div>

          {/* 2. cómo */}
          {!modo && (
            <Seccion titulo="¿Cómo lo quiere hacer?">
              <div className="grid gap-3 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setModo('documento')}
                  className="flex flex-col items-start gap-2 rounded-xl border border-papel-borde bg-background p-5 text-left transition-colors hover:border-marca"
                >
                  <FileUp className="size-7 text-marca-texto" aria-hidden />
                  <span className="text-lg font-bold text-ink">A partir de un documento</span>
                  <span className="text-[0.95rem] text-ink-soft">
                    Suba {tipo.documento.charAt(0).toLowerCase() + tipo.documento.slice(1)} Papiniano lo analiza y
                    redacta la respuesta.
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setModo('propio')}
                  className="flex flex-col items-start gap-2 rounded-xl border border-papel-borde bg-background p-5 text-left transition-colors hover:border-marca"
                >
                  <PencilLine className="size-7 text-marca-texto" aria-hidden />
                  <span className="text-lg font-bold text-ink">Hacerlo yo mismo</span>
                  <span className="text-[0.95rem] text-ink-soft">
                    Papiniano le pregunta lo de su caso (tribunal, hechos, motivos, qué pide) y lo redacta con el
                    modelo y los artículos de la biblioteca.
                  </span>
                </button>
              </div>
            </Seccion>
          )}

          {/* A partir de un documento: subirlo */}
          {modo === 'documento' && !documento && (
            <Seccion titulo="Suba el documento">
              <div className="space-y-4">
                <p className="text-ink-soft">{tipo.documento} En PDF digital o Word, hasta {MAX_MB} MB.</p>
                <input
                  ref={campo}
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="hidden"
                  onChange={(e) => {
                    const archivo = e.target.files?.[0]
                    e.target.value = ''
                    if (archivo) leer(archivo)
                  }}
                />
                <button
                  type="button"
                  disabled={leyendo}
                  onClick={() => campo.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    const archivo = e.dataTransfer.files?.[0]
                    if (archivo) leer(archivo)
                  }}
                  className="flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed border-regla bg-background px-4 py-10 text-center transition-colors hover:border-marca"
                >
                  {leyendo ? (
                    <Loader2 className="size-8 animate-spin text-marca-texto" aria-hidden />
                  ) : (
                    <FileUp className="size-8 text-marca-texto" aria-hidden />
                  )}
                  <span className="font-bold text-ink">{leyendo ? 'Leyendo el documento…' : 'Elegir el documento'}</span>
                  <span className="text-[0.9rem] text-ink-soft">o arrástrelo aquí</span>
                </button>
                <div className="flex flex-wrap items-center gap-3 rounded-xl border border-papel-borde bg-background p-4">
                  <PencilLine className="size-6 shrink-0 text-marca-texto" aria-hidden />
                  <p className="flex-1 text-[0.95rem] text-ink-soft">
                    <strong className="text-ink">¿No tiene documento?</strong> Hágalo usted mismo: Papiniano le pregunta
                    lo de su caso y lo redacta.
                  </p>
                  <Button variant="outline" className="h-11 border-regla" onClick={() => setModo('propio')} disabled={leyendo}>
                    Que Papiniano me pregunte
                  </Button>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="indicaciones" className="font-bold text-ink">
                    Indicaciones para Papiniano <span className="font-normal text-ink-soft">(opcional)</span>
                  </label>
                  <Textarea
                    id="indicaciones"
                    value={indicaciones}
                    onChange={(e) => setIndicaciones(e.target.value)}
                    placeholder="Qué quiere lograr o qué argumento quiere usar. Por ejemplo: «pedir que se declare inadmisible por prescripción». No escriba nombres ni cédulas."
                    className="min-h-24 text-base"
                    maxLength={1500}
                  />
                </div>
              </div>
            </Seccion>
          )}

          {/* A partir de un documento: revisar lo que se le manda a la IA */}
          {modo === 'documento' && documento && (
            <Seccion titulo="Revise lo que se le manda a Papiniano">
              <div className="space-y-4">
                <div className="rounded-xl border border-papel-borde bg-background p-4">
                  <p className="flex items-center gap-2 font-bold text-ink">
                    <ShieldCheck className="size-5 text-marca-texto" aria-hidden /> Los datos de las personas no salen de aquí
                  </p>
                  <p className="mt-1 text-[0.95rem] text-ink-soft">
                    {quitados.length
                      ? `De «${documento.nombre}» se quitaron ${quitados.join(', ')}. `
                      : `En «${documento.nombre}» no se encontraron nombres ni cédulas. `}
                    Van como [PERSONA 1], [CÉDULA 1]… y en el escrito se llenan solos en su equipo, solo al descargar.
                    Revise el texto: si ve algún nombre, cédula o dirección que se haya escapado, bórrelo o cámbielo
                    por algo como [PERSONA].
                  </p>
                  {Object.keys(documento.mapa).length > 0 && (
                    <div className="mt-2">
                      <Button variant="ghost" className="h-10 px-2 text-ink-soft" onClick={() => setVerDatos((v) => !v)} aria-expanded={verDatos}>
                        <ChevronDown className={cn('transition-transform', verDatos && 'rotate-180')} />
                        {verDatos ? 'Ocultar qué es cada dato' : 'Ver qué es cada dato (solo en su equipo)'}
                      </Button>
                      {verDatos && (
                        <dl className="mt-2 grid gap-x-4 gap-y-1 text-[0.92rem] sm:grid-cols-[auto_1fr]">
                          {Object.entries(documento.mapa).map(([clave, valor]) => (
                            <div key={clave} className="contents">
                              <dt className="font-bold text-ink">[{clave}]</dt>
                              <dd className="text-ink-soft">{valor}</dd>
                            </div>
                          ))}
                        </dl>
                      )}
                    </div>
                  )}
                </div>
                <Textarea
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  aria-label="Texto del documento que se le manda a Papiniano"
                  className="h-[22rem] text-[0.95rem] leading-relaxed"
                  disabled={Boolean(avance)}
                />
                <BotonRedactar
                  nombre={tipo.nombre}
                  avance={avance}
                  desactivado={texto.trim().length < 200}
                  alRedactar={redactarDocumento}
                />
              </div>
            </Seccion>
          )}

          {/* Hacerlo yo mismo: Papiniano pregunta */}
          {modo === 'propio' && (
            <Entrevista
              tipo={tipo}
              respuestas={respuestas}
              setRespuestas={setRespuestas}
              modelo={modelo}
              setModelo={setModelo}
              avance={avance}
              alRedactar={redactarPropio}
            />
          )}
        </div>
      )}
    </div>
  )
}

function BotonRedactar({
  nombre, avance, desactivado, alRedactar, aviso,
}: {
  nombre: string
  avance: string | null
  desactivado: boolean
  alRedactar: () => void
  aviso?: string
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="grande" onClick={alRedactar} disabled={Boolean(avance) || desactivado}>
        {avance ? <Loader2 className="animate-spin" /> : <Sparkles />}
        {avance ? 'Redactando…' : `Redactar ${nombre.toLowerCase()}`}
      </Button>
      {avance ? (
        <p className="text-ink-soft" role="status" aria-live="polite">
          {avance} Puede tardar un minuto.
        </p>
      ) : (
        aviso && <p className="text-[0.9rem] text-ink-soft">{aviso}</p>
      )}
    </div>
  )
}

/**
 * «Hacerlo yo mismo» como conversación: Papiniano hace las preguntas del caso una por una, como un colega,
 * y al final pregunta con qué modelo lo hace. Las preguntas son fijas por tipo de escrito (redactar.py):
 * no gastan IA y no se le olvida ninguna. Se puede volver a cualquier respuesta para cambiarla.
 */
function Entrevista({
  tipo, respuestas, setRespuestas, modelo, setModelo, avance, alRedactar,
}: {
  tipo: Tipo
  respuestas: Record<string, string>
  setRespuestas: (r: Record<string, string>) => void
  modelo: string
  setModelo: (m: string) => void
  avance: string | null
  alRedactar: () => void
}) {
  const preguntas = tipo.preguntas
  const [paso, setPaso] = useState(0)
  const [texto, setTexto] = useState('')
  const fin = useRef<HTMLDivElement>(null)
  const entrada = useRef<HTMLTextAreaElement>(null)
  const actual = preguntas[paso]
  const listo = paso >= preguntas.length
  // hablarlo en vez de escribirlo: cada frase dictada se suma a la respuesta
  const dictado = useDictado(
    (frase) => setTexto((t) => (t.trim() ? `${t.trimEnd()} ${frase}` : frase)),
    (mensaje) => toast.error(mensaje),
  )

  // que Papiniano lea cada pregunta en voz alta (el mismo ajuste que en el chat)
  const voz = useVozAutomatica()
  const conVoz = voz.encendida

  useEffect(() => {
    fin.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    entrada.current?.focus()
    if (!conVoz) return
    const p = preguntas[paso]
    hablar(p ? `${p.pregunta}. ${p.ayuda}` : 'Tengo todo lo que necesito. ¿Con qué modelo lo hago?')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paso, conVoz])
  function responder(valor: string) {
    if (!actual) return
    if (dictado.escuchando) dictado.alternar()
    const limpio = valor.trim()
    if (actual.requerida && limpio.length < 3) {
      toast.error('Esta respuesta hace falta para el escrito.')
      return
    }
    const nuevas = { ...respuestas, [actual.clave]: limpio }
    setRespuestas(nuevas)
    // la siguiente que falta (si volvió a cambiar una, sigue donde iba)
    const siguiente = preguntas.findIndex((p, i) => i > paso && !(p.clave in nuevas))
    setPaso(siguiente === -1 ? preguntas.length : siguiente)
    setTexto('')
  }

  function cambiar(i: number) {
    setPaso(i)
    setTexto(respuestas[preguntas[i].clave] ?? '')
  }

  const articulo = /^(demanda)/i.test(tipo.nombre) ? 'la' : 'el'
  return (
    <section className="space-y-4 rounded-2xl border border-papel-borde bg-background p-4 md:p-6">
      {hayVoz() && (
        <div className="flex justify-end">
          <Button variant="ghost" className="h-11 text-ink-soft" onClick={voz.alternar} aria-pressed={conVoz}>
            {conVoz ? <><VolumeX /> Que no me hable</> : <><Volume2 /> Que Papiniano me lea las preguntas</>}
          </Button>
        </div>
      )}
      <BurbujaPapiniano>
        Vamos a preparar {articulo} {tipo.nombre.toLowerCase()}. Le hago unas preguntas de su caso y con eso busco en la
        biblioteca los artículos y sentencias que encajan; no pongo ninguno que no esté ahí. Los nombres y cédulas no
        me los dé: van como datos por llenar y se ponen al descargar.
        {dictado.disponible && ' Si prefiere, toque el micrófono y dígame la respuesta en voz alta.'}
      </BurbujaPapiniano>

      {preguntas.map((p, i) => {
        const respondida = p.clave in respuestas && i !== paso
        if (i > paso && !respondida) return null
        return (
          <div key={p.clave} className="space-y-3">
            <BurbujaPapiniano>
              <span className="font-bold">{p.pregunta}</span>
              {p.ayuda && <span className="mt-1 block text-[0.9rem] text-ink-soft">{p.ayuda}</span>}
              {!p.requerida && <span className="mt-1 block text-[0.85rem] italic text-ink-soft">Si no aplica, sáltela.</span>}
            </BurbujaPapiniano>
            {respondida && (
              <div className="flex flex-col items-end gap-1">
                <div className="ml-12 rounded-2xl rounded-br-sm bg-panel px-4 py-3 whitespace-pre-wrap text-sobre-panel">
                  {respuestas[p.clave] || <span className="italic opacity-80">(la saltó)</span>}
                </div>
                {!avance && (
                  <button type="button" onClick={() => cambiar(i)} className="text-[0.85rem] text-ink-soft underline underline-offset-2 hover:text-ink">
                    Cambiar
                  </button>
                )}
              </div>
            )}
          </div>
        )
      })}

      {listo && (
        <BurbujaPapiniano>
          <span className="font-bold">Tengo todo lo que necesito. ¿Con qué modelo lo hago?</span>
          <span className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Modelo">
            {[{ clave: '', nombre: 'Que Papiniano elija' }, ...tipo.modelos, { clave: 'ninguno', nombre: 'Sin modelo' }].map((m) => (
              <button
                key={m.clave || 'elige'}
                type="button"
                aria-pressed={modelo === m.clave}
                disabled={Boolean(avance)}
                onClick={() => setModelo(m.clave)}
                className={cn(
                  'min-h-10 rounded-full border px-4 py-1.5 text-left text-[0.9rem] transition-colors',
                  modelo === m.clave ? 'border-marca bg-marca font-bold text-sobre-boton' : 'border-regla bg-card text-ink hover:border-marca',
                )}
              >
                {m.nombre}
              </button>
            ))}
          </span>
        </BurbujaPapiniano>
      )}
      <div ref={fin} />

      {listo ? (
        <BotonRedactar nombre={tipo.nombre} avance={avance} desactivado={false} alRedactar={alRedactar} />
      ) : (
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            responder(texto)
          }}
        >
          <Textarea
            ref={entrada}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                responder(texto)
              }
            }}
            placeholder={dictado.escuchando ? 'Lo escucho… hable con calma; vuelva a tocar el micrófono al terminar.' : 'Escriba su respuesta o toque el micrófono para hablarla…'}
            aria-label={actual?.pregunta}
            className="min-h-12 flex-1 rounded-2xl text-base"
            maxLength={4000}
          />
          {dictado.disponible && (
            <Button
              type="button"
              variant={dictado.escuchando ? 'default' : 'outline'}
              size="icon-grande"
              className={cn(dictado.escuchando ? 'animate-pulse' : 'border-regla')}
              onClick={dictado.alternar}
              aria-pressed={dictado.escuchando}
              aria-label={dictado.escuchando ? 'Dejar de escuchar' : 'Dictar la respuesta con el micrófono'}
              title={dictado.escuchando ? 'Dejar de escuchar' : 'Hablar en vez de escribir'}
            >
              {dictado.escuchando ? <MicOff /> : <Mic />}
            </Button>
          )}
          {actual && !actual.requerida && (
            <Button type="button" variant="ghost" className="h-12 text-ink-soft" onClick={() => responder('')}>
              Saltar
            </Button>
          )}
          <Button type="submit" size="icon-grande" aria-label="Enviar respuesta">
            <SendHorizontal />
          </Button>
        </form>
      )}
    </section>
  )
}

function BurbujaPapiniano({ children }: { children: React.ReactNode }) {
  return (
    <div className="mr-12 space-y-2">
      <div className="flex items-center gap-2">
        <Papiniano className="size-7" decorativo />
        <span className="text-[0.9rem] font-bold text-ink">{NOMBRE_ASISTENTE}</span>
      </div>
      <div className="rounded-2xl rounded-tl-sm border border-papel-borde bg-card px-5 py-4 text-ink">{children}</div>
    </div>
  )
}
