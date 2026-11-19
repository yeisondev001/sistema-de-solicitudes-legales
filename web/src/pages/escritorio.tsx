import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileStack, LibraryBig, MessageSquarePlus, Palette, PenLine, type LucideIcon } from 'lucide-react'
import { Apariencia } from '@/components/apariencia'
import { Cargando } from '@/components/cargando'
import { Renglon, Seccion } from '@/components/seccion'
import { api } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Audiencia, Conversacion, Documento, Fecha, Invitacion } from '@/lib/tipos'
import { cuando, cuandoEs, fechaDeHoy, horaBonita, saludo } from '@/lib/fechas'
import { InvitacionesOficina } from '@/pages/mi-oficina'

/** El inicio: el saludo y lo del día. Para preguntar se va directo a Papiniano (no hay caja aquí). */
export default function Escritorio() {
  const { perfil } = useSesion()
  const navegar = useNavigate()
  const [convs, setConvs] = useState<Conversacion[] | null>(null)
  const [audiencias, setAudiencias] = useState<Audiencia[]>([])
  // lo de la agenda en los próximos 7 días (plan Abogado y Despacho)
  const [semana, setSemana] = useState<Fecha[] | null>(null)
  const [docs, setDocs] = useState<{ configurada: boolean; documentos: Documento[] } | null>(null)
  const [apariencia, setApariencia] = useState(false)
  // las oficinas que le piden unirse (plan Despacho)
  const [invitaciones, setInvitaciones] = useState<Invitacion[]>([])

  const contarDocumentos = () => api.get<typeof docs>('/api/documentos').then(setDocs).catch(() => {})
  const buscarInvitaciones = () =>
    api.get<{ invitaciones: Invitacion[] }>('/api/oficina').then((r) => setInvitaciones(r.invitaciones)).catch(() => {})

  useEffect(() => {
    api.get<Conversacion[]>('/api/conversaciones').then(setConvs).catch(() => setConvs([]))
    if (perfil.plantillas) api.get<Audiencia[]>('/api/audiencias').then(setAudiencias).catch(() => {})
    if (perfil.propios) api.get<Fecha[]>('/api/agenda').then(setSemana).catch(() => setSemana([]))
    contarDocumentos()
    if (perfil.email && !perfil.oficina) buscarInvitaciones()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [perfil.plantillas])

  const nombre = perfil.nombre.split(/\s+/)[0] ?? ''
  // lo de la semana: la agenda y, en las cuentas con plantillas, las audiencias del historial de reportes
  const enAgenda = (semana?.length ?? 0) + audiencias.length
  const resumen = perfil.prueba
    ? `Prueba gratis · quedan ${perfil.prueba.dias} día${perfil.prueba.dias === 1 ? '' : 's'}`
    : perfil.propios || perfil.plantillas
      ? enAgenda
        ? `${enAgenda} fecha${enAgenda === 1 ? '' : 's'} esta semana`
        : 'Nada en la agenda esta semana'
      : ''

  const mosaicos: [LucideIcon, string, () => void][] = [
    [MessageSquarePlus, 'Preguntarle a Papiniano', () => navegar('/papiniano')],
    [FileStack, 'Buscar un modelo', () => navegar('/modelos')],
    [LibraryBig, 'Ver la biblioteca', () => navegar('/biblioteca')],
    perfil.plantillas
      ? [PenLine, 'Nueva solicitud', () => navegar('/redaccion')]
      : [Palette, 'Cambiar los colores', () => setApariencia(true)],
  ]

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8 md:py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-2 border-b border-ink pb-5">
        <div className="space-y-1.5">
          <p className="text-[0.85rem] font-bold tracking-wide text-pista uppercase">{fechaDeHoy()}</p>
          <h1 className="font-heading text-[2.1rem] leading-tight font-medium text-ink md:text-[2.6rem]">
            {saludo()}{nombre ? `, ${nombre}` : ''}.
          </h1>
        </div>
        {resumen && <p className="text-[0.95rem] text-ink-soft">{resumen}</p>}
      </header>

      {invitaciones.length > 0 && (
        <div className="mb-5 space-y-5">
          <InvitacionesOficina invitaciones={invitaciones} alCambiar={buscarInvitaciones} />
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        {perfil.propios && (
          <Seccion titulo="Esta semana" accion={{ texto: 'Ver agenda', a: '/agenda' }}>
            {semana === null ? (
              <Cargando renglones={2} que="Cargando su agenda" />
            ) : semana.length ? (
              semana.slice(0, 5).map((f) => (
                <Renglon
                  key={f.id}
                  titulo={f.titulo}
                  detalle={[f.hora ? horaBonita(f.hora) : 'Todo el día', f.expediente?.cliente, f.lugar].filter(Boolean).join(' · ')}
                  etiqueta={cuandoEs(f.fecha)}
                  a={f.expediente ? `/expedientes/${f.expediente.id}` : '/agenda'}
                />
              ))
            ) : (
              <p className="text-ink-soft">
                Nada en los próximos 7 días.{' '}
                <Link to="/agenda" className="text-marca-texto hover:underline">Agregue sus audiencias y plazos</Link>.
              </p>
            )}
          </Seccion>
        )}

        {perfil.plantillas && (
          <Seccion titulo="Audiencias de la semana" accion={{ texto: 'Ver historial', a: '/redaccion/historial' }}>
            {audiencias.length ? (
              audiencias.slice(0, 5).map((a) => (
                <Renglon
                  key={a.id}
                  titulo={a.recurrente || a.expediente || 'Expediente'}
                  detalle={[a.tribunal, a.expediente && `Exp. ${a.expediente}`].filter(Boolean).join(' · ')}
                  etiqueta={a.dias === 0 ? 'Hoy' : a.dias === 1 ? 'Mañana' : `En ${a.dias} días`}
                  a="/redaccion/historial"
                />
              ))
            ) : (
              <p className="text-ink-soft">No hay audiencias en los próximos 7 días.</p>
            )}
          </Seccion>
        )}

        <Seccion titulo="Conversaciones recientes" accion={{ texto: 'Ver todas', a: '/papiniano' }}>
          {convs === null ? (
            <Cargando renglones={2} que="Cargando sus conversaciones" />
          ) : convs.length ? (
            convs.slice(0, 4).map((c) => (
              <Renglon key={c.id} titulo={c.titulo} detalle={cuando(c.actualizada)} a={`/papiniano/${c.id}`} />
            ))
          ) : (
            <p className="text-ink-soft">
              Todavía no ha conversado con Papiniano, su asistente.{' '}
              <Link to="/papiniano" className="text-marca-texto hover:underline">Hágale su primera pregunta</Link>.
            </p>
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

      </div>

      {/* la misma ventana de Mi cuenta → Apariencia, abierta desde el mosaico «Cambiar los colores» */}
      <Apariencia abierta={apariencia} alCambiar={setApariencia} />
    </div>
  )
}
