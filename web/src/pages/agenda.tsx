import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { DialogoFecha, RenglonFecha, SinExpedientes, aBorrador, fechaNueva, type BorradorFecha } from '@/components/agenda'
import { Cargando } from '@/components/cargando'
import { TituloSala } from '@/components/oficina'
import { Button } from '@/components/ui/button'
import { api, type ErrorApi } from '@/lib/api'
import { cuandoEs, diaLargo, diasPara, hoyIso, mesLargo, sumarDias } from '@/lib/fechas'
import { useSesion } from '@/lib/sesion'
import type { ExpedienteResumen, Fecha } from '@/lib/tipos'
import { cn } from '@/lib/utils'

const PROXIMOS_DIAS = 60
const SEMANA = ['L', 'M', 'M', 'J', 'V', 'S', 'D']

/** El último día del mes de una fecha AAAA-MM-01 */
function finDeMes(primero: string) {
  const [a, m] = primero.split('-').map(Number)
  return `${primero.slice(0, 8)}${String(new Date(Date.UTC(a, m, 0)).getUTCDate()).padStart(2, '0')}`
}

function otroMes(primero: string, cuantos: number) {
  const [a, m] = primero.split('-').map(Number)
  const f = new Date(Date.UTC(a, m - 1 + cuantos, 1))
  return f.toISOString().slice(0, 10)
}

/** «Hoy · miércoles 18 de noviembre», «Mañana · …» o «Viernes 20 de noviembre» */
function encabezado(iso: string) {
  const dia = diaLargo(iso)
  const n = diasPara(iso)
  return n === 0 || n === 1 ? `${cuandoEs(iso)} · ${dia}` : dia.charAt(0).toUpperCase() + dia.slice(1)
}

/**
 * Agenda: audiencias, plazos y reuniones. A la izquierda el mes (con un punto los días que tienen algo); a la
 * derecha las próximas fechas por día, o las del día que toque en el mes. En una oficina es de todos sus abogados.
 */
export default function Agenda() {
  const { perfil } = useSesion()
  const hoy = hoyIso()
  const [mes, setMes] = useState(`${hoy.slice(0, 8)}01`)
  const [dia, setDia] = useState<string | null>(null)
  const [delMes, setDelMes] = useState<Fecha[]>([])
  const [proximas, setProximas] = useState<Fecha[] | null>(null)
  const [mias, setMias] = useState(false)
  const [expedientes, setExpedientes] = useState<ExpedienteResumen[]>([])
  const [editando, setEditando] = useState<BorradorFecha | null>(null)

  const cargar = useCallback(() => {
    if (!perfil.propios) return
    api.get<Fecha[]>(`/api/agenda?desde=${hoy}&hasta=${sumarDias(hoy, PROXIMOS_DIAS)}`).then(setProximas).catch((e: ErrorApi) => {
      toast.error(e.message)
      setProximas([])
    })
    api.get<Fecha[]>(`/api/agenda?desde=${mes}&hasta=${finDeMes(mes)}`).then(setDelMes).catch(() => {})
  }, [hoy, mes, perfil.propios])
  useEffect(cargar, [cargar])
  useEffect(() => {
    if (perfil.propios) api.get<ExpedienteResumen[]>('/api/expedientes').then(setExpedientes).catch(() => {})
  }, [perfil.propios])

  if (!perfil.propios)
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8 md:py-8">
        <TituloSala titulo="Agenda" />
        <SinExpedientes sala="La Agenda" />
      </div>
    )

  const mio = (f: Fecha) => !mias || f.responsable?.id === perfil.id
  const lista = (dia ? delMes.filter((f) => f.fecha === dia) : proximas ?? []).filter(mio)
  const porDia = lista.reduce<Record<string, Fecha[]>>((g, f) => ({ ...g, [f.fecha]: [...(g[f.fecha] ?? []), f] }), {})
  const conAlgo = new Set(delMes.filter(mio).map((f) => f.fecha))

  // el resumen: lo de los próximos 7 días
  const semana = (proximas ?? []).filter((f) => mio(f) && diasPara(f.fecha) <= 7)
  const cuenta = (tipo: Fecha['tipo'], uno: string, varios: string) => {
    const n = semana.filter((f) => f.tipo === tipo).length
    return n ? `${n} ${n === 1 ? uno : varios}` : ''
  }
  const partes = [cuenta('audiencia', 'audiencia', 'audiencias'), cuenta('plazo', 'plazo', 'plazos'),
    cuenta('reunion', 'reunión', 'reuniones'), cuenta('otro', 'pendiente', 'pendientes')].filter(Boolean)
  const resumen = !proximas
    ? undefined
    : partes.length
      ? `${partes.length > 1 ? `${partes.slice(0, -1).join(', ')} y ${partes.at(-1)}` : partes[0]} en los próximos 7 días`
      : 'Nada en los próximos 7 días'

  // el mes: los días en su semana, empezando el lunes
  const [a, m] = mes.split('-').map(Number)
  const vacios = (new Date(Date.UTC(a, m - 1, 1)).getUTCDay() + 6) % 7
  const dias = Number(finDeMes(mes).slice(8))

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala titulo="Agenda" sub={resumen}>
        <div className="flex flex-wrap gap-2">
          {perfil.oficina && (
            <div role="group" aria-label="De quién" className="inline-flex rounded-full border border-regla bg-card p-1">
              {([[false, 'De la oficina'], [true, 'Las mías']] as const).map(([v, texto]) => (
                <button
                  key={texto}
                  type="button"
                  aria-pressed={mias === v}
                  onClick={() => setMias(v)}
                  className={cn('min-h-9 rounded-full px-3.5 text-[0.92rem]', mias === v ? 'bg-panel font-bold text-sobre-panel' : 'text-ink-soft hover:text-ink')}
                >
                  {texto}
                </button>
              ))}
            </div>
          )}
          <Button size="grande" onClick={() => setEditando(fechaNueva(dia && diasPara(dia) >= 0 ? dia : hoy))}>
            <Plus /> Nueva fecha
          </Button>
        </div>
      </TituloSala>

      <div className="grid items-start gap-5 lg:grid-cols-[19rem_1fr]">
        <section aria-label="Calendario" className="rounded-2xl border border-papel-borde bg-card p-4">
          <div className="mb-2 flex items-center justify-between">
            <Button variant="ghost" size="icon-grande" aria-label="Mes anterior" onClick={() => { setMes(otroMes(mes, -1)); setDia(null) }}>
              <ChevronLeft />
            </Button>
            <p className="font-heading text-[1.15rem] font-medium text-ink first-letter:uppercase">{mesLargo(mes)}</p>
            <Button variant="ghost" size="icon-grande" aria-label="Mes siguiente" onClick={() => { setMes(otroMes(mes, 1)); setDia(null) }}>
              <ChevronRight />
            </Button>
          </div>
          <div className="grid grid-cols-7 text-center">
            {SEMANA.map((d, i) => (
              <span key={i} aria-hidden="true" className="py-1 text-[0.72rem] font-bold text-pista">{d}</span>
            ))}
            {Array.from({ length: vacios }, (_, i) => <span key={`v${i}`} />)}
            {Array.from({ length: dias }, (_, i) => {
              const iso = `${mes.slice(0, 8)}${String(i + 1).padStart(2, '0')}`
              const elegido = iso === dia
              return (
                <button
                  key={iso}
                  type="button"
                  aria-pressed={elegido}
                  aria-label={`${diaLargo(iso)}${conAlgo.has(iso) ? ', con fechas' : ''}`}
                  onClick={() => setDia(elegido ? null : iso)}
                  className={cn(
                    'relative flex h-10 items-center justify-center rounded-lg text-[0.92rem] transition-colors',
                    elegido ? 'bg-panel font-bold text-sobre-panel' : iso === hoy ? 'bg-marca font-bold text-sobre-boton' : 'text-ink hover:bg-muted',
                  )}
                >
                  {i + 1}
                  {conAlgo.has(iso) && (
                    <span className={cn('absolute bottom-1 size-1.5 rounded-full', elegido || iso === hoy ? 'bg-sobre-boton' : 'bg-marca')} />
                  )}
                </button>
              )
            })}
          </div>
          {(dia || mes !== `${hoy.slice(0, 8)}01`) && (
            <Button
              variant="ghost"
              className="mt-2 h-11 w-full text-marca-texto"
              onClick={() => { setMes(`${hoy.slice(0, 8)}01`); setDia(null) }}
            >
              Volver a las próximas fechas
            </Button>
          )}
        </section>

        <section aria-label={dia ? `Fechas del ${diaLargo(dia)}` : 'Próximas fechas'} className="space-y-5">
          {proximas === null ? (
            <Cargando renglones={4} que="Cargando la agenda" />
          ) : !lista.length ? (
            <p className="rounded-2xl border border-papel-borde bg-card p-6 text-ink-soft">
              {dia
                ? `No hay nada el ${diaLargo(dia)}.`
                : `No hay fechas en los próximos ${PROXIMOS_DIAS} días. Agregue sus audiencias y plazos con «Nueva fecha», o desde cada expediente.`}
            </p>
          ) : (
            Object.entries(porDia).map(([iso, fechas]) => (
              <div key={iso}>
                <h2 className="mb-2 ml-1 text-[0.8rem] font-bold tracking-wider text-pista uppercase">{encabezado(iso)}</h2>
                <div className="space-y-2">
                  {fechas.map((f) => (
                    <RenglonFecha key={f.id} f={f} alTocar={() => setEditando(aBorrador(f))} />
                  ))}
                </div>
              </div>
            ))
          )}
        </section>
      </div>

      {editando && (
        <DialogoFecha
          inicial={editando}
          expedientes={expedientes}
          alCerrar={() => setEditando(null)}
          alGuardar={() => {
            setEditando(null)
            cargar()
          }}
        />
      )}
    </div>
  )
}
