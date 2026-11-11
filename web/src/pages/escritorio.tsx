import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, LibraryBig, MessageSquarePlus, Palette, PenLine, Upload, type LucideIcon } from 'lucide-react'
import { Apariencia } from '@/components/apariencia'
import { Renglon, Seccion } from '@/components/seccion'
import { useSubida } from '@/components/subida'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Audiencia, Conversacion, Documento } from '@/lib/tipos'
import { cuando, fechaDeHoy, saludo } from '@/lib/fechas'

const EJEMPLO_PRESTACIONES =
  'Calcule las prestaciones de un despido sin causa: salario de RD$50,000 al mes, 3 años y 4 meses trabajados.'

/** El inicio: el saludo, la caja para preguntarle al asistente y lo del día. */
export default function Escritorio() {
  const { perfil } = useSesion()
  const navegar = useNavigate()
  const [pregunta, setPregunta] = useState('')
  const campo = useRef<HTMLInputElement>(null)
  const [convs, setConvs] = useState<Conversacion[] | null>(null)
  const [audiencias, setAudiencias] = useState<Audiencia[]>([])
  const [docs, setDocs] = useState<{ configurada: boolean; documentos: Documento[] } | null>(null)
  const [apariencia, setApariencia] = useState(false)

  const contarDocumentos = () => api.get<typeof docs>('/api/documentos').then(setDocs).catch(() => {})
  const subida = useSubida(contarDocumentos)

  useEffect(() => {
    api.get<Conversacion[]>('/api/conversaciones').then(setConvs).catch(() => setConvs([]))
    if (perfil.plantillas) api.get<Audiencia[]>('/api/audiencias').then(setAudiencias).catch(() => {})
    contarDocumentos()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [perfil.plantillas])

  // abre el asistente con una conversación nueva y le manda la pregunta
  function preguntar(q: string) {
    if (q.trim().length >= 2) navegar('/asistente', { state: { pregunta: q.trim() } })
  }

  const nombre = perfil.nombre.split(/\s+/)[0] ?? ''
  const resumen = perfil.plantillas
    ? audiencias.length
      ? `${audiencias.length} audiencia${audiencias.length === 1 ? '' : 's'} esta semana`
      : 'Sin audiencias esta semana'
    : perfil.prueba
      ? `Prueba gratis · quedan ${perfil.prueba.dias} día${perfil.prueba.dias === 1 ? '' : 's'}`
      : ''

  const atajos: [string, () => void][] = [
    ['Plazo para recurrir en casación', () => preguntar('¿Cuál es el plazo para recurrir en casación?')],
    [
      'Calcular prestaciones',
      // deja una pregunta de ejemplo para cambiarle los datos; los montos los saca el asistente
      // con las reglas fijas de jurisprudencia/prestaciones.py
      () => {
        setPregunta(EJEMPLO_PRESTACIONES)
        setTimeout(() => campo.current?.focus(), 0)
      },
    ],
    ['Subir un documento', subida.abrir],
    ...(perfil.plantillas ? [['Redactar una solicitud', () => navegar('/redaccion')] as [string, () => void]] : []),
  ]

  const mosaicos: [LucideIcon, string, () => void][] = [
    [MessageSquarePlus, 'Nueva conversación', () => navegar('/asistente')],
    [Upload, 'Subir un documento', subida.abrir],
    [LibraryBig, 'Ver la biblioteca', () => navegar('/biblioteca')],
    perfil.plantillas
      ? [PenLine, 'Nueva solicitud', () => navegar('/redaccion')]
      : [Palette, 'Cambiar los colores', () => setApariencia(true)],
  ]

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8 md:py-8">
      {subida.entrada}
      <header className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-2 border-b border-ink pb-5">
        <div className="space-y-1.5">
          <p className="text-[0.85rem] font-bold tracking-wide text-pista uppercase">{fechaDeHoy()}</p>
          <h1 className="font-heading text-[2.1rem] leading-tight font-medium text-ink md:text-[2.6rem]">
            {saludo()}{nombre ? `, ${nombre}` : ''}.
          </h1>
        </div>
        {resumen && <p className="text-[0.95rem] text-ink-soft">{resumen}</p>}
      </header>

      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          preguntar(pregunta)
        }}
        className="mb-6 space-y-4 rounded-2xl border border-regla bg-card p-5 shadow-[0_10px_28px_-14px_color-mix(in_oklab,var(--t-ink)_18%,transparent)] md:p-6"
      >
        <label htmlFor="pregunta" className="block text-[0.85rem] font-bold tracking-wide text-marca-texto">
          PREGÚNTELE A SU ASISTENTE
        </label>
        <div className="flex gap-2.5">
          <Input
            id="pregunta"
            ref={campo}
            value={pregunta}
            onChange={(e) => setPregunta(e.target.value)}
            placeholder="Una duda, un número de sentencia, un artículo…"
            className="h-[3.25rem] flex-1 rounded-xl bg-background px-4 text-[1.05rem] md:text-[1.05rem]"
          />
          <Button type="submit" size="grande" className="h-[3.25rem] rounded-xl px-4 sm:px-6" aria-label="Preguntar">
            <ArrowRight />
            <span className="hidden sm:inline">Preguntar</span>
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {atajos.map(([texto, accion]) => (
            <button
              key={texto}
              type="button"
              onClick={accion}
              className="rounded-full border border-regla bg-card px-4 py-2 text-[0.9rem] text-ink transition-colors hover:border-marca hover:text-marca-texto"
            >
              {texto}
            </button>
          ))}
        </div>
      </form>

      <div className="grid gap-5 md:grid-cols-2">
        {perfil.plantillas && (
          <Seccion titulo="Audiencias de la semana" accion={{ texto: 'Ver historial', a: '/redaccion' }}>
            {audiencias.length ? (
              audiencias.slice(0, 5).map((a) => (
                <Renglon
                  key={a.id}
                  titulo={a.recurrente || a.expediente || 'Expediente'}
                  detalle={[a.tribunal, a.expediente && `Exp. ${a.expediente}`].filter(Boolean).join(' · ')}
                  etiqueta={a.dias === 0 ? 'Hoy' : a.dias === 1 ? 'Mañana' : `En ${a.dias} días`}
                />
              ))
            ) : (
              <p className="text-ink-soft">No hay audiencias en los próximos 7 días.</p>
            )}
          </Seccion>
        )}

        <Seccion titulo="Conversaciones recientes" accion={{ texto: 'Ver todas', a: '/asistente' }}>
          {convs === null ? (
            <p className="text-ink-soft">Cargando…</p>
          ) : convs.length ? (
            convs.slice(0, 4).map((c) => (
              <Renglon key={c.id} titulo={c.titulo} detalle={cuando(c.actualizada)} a={`/asistente/${c.id}`} />
            ))
          ) : (
            <p className="text-ink-soft">Todavía no ha conversado con su asistente. Escriba arriba su primera pregunta.</p>
          )}
        </Seccion>

        <Seccion titulo="A la mano">
          <div className="grid grid-cols-2 gap-2.5">
            {mosaicos.map(([Icono, texto, accion]) => (
              <button
                key={texto}
                type="button"
                onClick={accion}
                className="flex flex-col items-start gap-2.5 rounded-xl border border-papel-borde bg-background p-4 text-left font-bold text-ink transition-colors hover:border-marca"
              >
                <Icono className="size-6 text-marca-texto" />
                {texto}
              </button>
            ))}
          </div>
        </Seccion>

        <Seccion titulo="Su biblioteca" accion={{ texto: 'Abrir', a: '/biblioteca' }}>
          <p className="text-ink">
            Sentencias de la Suprema Corte, leyes y reglamentos, y los documentos que usted sube.
          </p>
          {docs?.configurada && (
            <p className="mt-2 text-[0.95rem] text-ink-soft">
              {docs.documentos.length
                ? `Ha subido ${docs.documentos.length} documento${docs.documentos.length === 1 ? '' : 's'}.`
                : 'Todavía no ha subido documentos propios.'}
            </p>
          )}
        </Seccion>

        <Seccion titulo="Pronto en su despacho">
          <Renglon titulo="Expedientes" detalle="Una carpeta por cliente con sus documentos, conversaciones y plazos." />
          <Renglon titulo="Agenda" detalle="Audiencias y vencimientos; el escritorio le avisará lo de la semana." />
        </Seccion>
      </div>

      {/* la misma ventana de Mi cuenta → Apariencia, abierta desde el mosaico «Cambiar los colores» */}
      <Apariencia abierta={apariencia} alCambiar={setApariencia} />
    </div>
  )
}
