import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, BookOpenCheck, ChevronDown, FileSignature, FileUp, Landmark, Loader2, PencilLine, Scale, ShieldCheck,
  Sparkles, type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'
import { guardarDatosDelEscrito } from '@/components/escrito'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, ErrorApi, leerParaRedactar, redactarEscrito, type DocumentoLeido } from '@/lib/api'
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
  const faltan = tipo?.preguntas.filter((p) => p.requerida && (respuestas[p.clave] ?? '').trim().length < 3) ?? []

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
                    Responda unas preguntas de su caso (tribunal, hechos, motivos, qué pide) y Papiniano lo redacta
                    con el modelo y los artículos de la biblioteca.
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

          {/* Hacerlo yo mismo: las preguntas del caso */}
          {modo === 'propio' && (
            <Seccion titulo="Los datos de su caso">
              <div className="space-y-5">
                <p className="text-ink-soft">
                  Conteste lo que sabe; lo marcado con * hace falta. Papiniano busca en la biblioteca los artículos y
                  sentencias que encajan con sus hechos y motivos: no pone ninguno que no esté ahí. No escriba nombres
                  ni cédulas: van como datos por llenar y se ponen al descargar.
                </p>
                {tipo.preguntas.map((p) => (
                  <div key={p.clave} className="space-y-1.5">
                    <label htmlFor={`p-${p.clave}`} className="font-bold text-ink">
                      {p.pregunta}
                      {p.requerida && <span className="text-marca-texto"> *</span>}
                    </label>
                    {p.ayuda && <p className="text-[0.9rem] text-ink-soft">{p.ayuda}</p>}
                    <Textarea
                      id={`p-${p.clave}`}
                      value={respuestas[p.clave] ?? ''}
                      onChange={(e) => setRespuestas((r) => ({ ...r, [p.clave]: e.target.value }))}
                      className={cn('text-base', ['hechos', 'motivos'].includes(p.clave) ? 'min-h-32' : 'min-h-16')}
                      maxLength={4000}
                      disabled={Boolean(avance)}
                    />
                  </div>
                ))}
                <div className="space-y-1.5">
                  <label htmlFor="modelo" className="font-bold text-ink">Modelo</label>
                  <select
                    id="modelo"
                    value={modelo}
                    onChange={(e) => setModelo(e.target.value)}
                    disabled={Boolean(avance)}
                    className="h-12 w-full rounded-lg border border-regla bg-card px-3 text-base text-ink focus:border-marca focus:outline-none"
                  >
                    <option value="">Que Papiniano elija el que mejor encaje</option>
                    {tipo.modelos.map((m) => (
                      <option key={m.clave} value={m.clave}>{m.nombre}</option>
                    ))}
                    <option value="ninguno">Sin modelo</option>
                  </select>
                </div>
                <BotonRedactar
                  nombre={tipo.nombre}
                  avance={avance}
                  desactivado={faltan.length > 0}
                  alRedactar={redactarPropio}
                  aviso={faltan.length ? `Falta: ${faltan.map((p) => p.pregunta).join(' · ')}` : undefined}
                />
              </div>
            </Seccion>
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
