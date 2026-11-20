import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Seccion } from '@/components/seccion'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { api, type ErrorApi } from '@/lib/api'
import { cuandoEs, diaYMes, diasPara, hoyIso, horaBonita } from '@/lib/fechas'
import { useSesion } from '@/lib/sesion'
import type { ExpedienteResumen, Fecha, Responsable, TipoFecha } from '@/lib/tipos'
import { cn } from '@/lib/utils'

// Lo que comparten Expedientes y Agenda: los campos de los formularios, las fechas y quién lleva cada cosa

export const ENTRADA = 'h-11 border-pista/80 bg-papel text-base md:text-base'
export const SELECT =
  'h-11 w-full rounded-lg border border-pista/80 bg-papel px-3 text-base text-ink outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'

/** Un campo de formulario con su nombre arriba */
export function Campo({ id, etiqueta, className, children }: {
  id: string
  etiqueta: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <Label htmlFor={id} className="text-[0.9rem] text-ink-soft">{etiqueta}</Label>
      {children}
    </div>
  )
}

/** Los abogados de su oficina, para elegir quién lleva el caso (vacío si no está en una oficina) */
export function useAbogados() {
  const { perfil } = useSesion()
  const [abogados, setAbogados] = useState<Responsable[]>([])
  const oficina = perfil.oficina?.id
  useEffect(() => {
    if (!oficina) return
    api
      .get<{ oficina: { abogados: Responsable[] } | null }>('/api/oficina')
      .then((r) => setAbogados((r.oficina?.abogados ?? []).map(({ id, nombre }) => ({ id, nombre }))))
      .catch(() => {})
  }, [oficina])
  return abogados
}

/** Elegir quién lo lleva: solo en una oficina con más de un abogado */
export function CampoResponsable({ id, valor, cambiar }: { id: string; valor: number | null; cambiar: (v: number) => void }) {
  const { perfil } = useSesion()
  const abogados = useAbogados()
  if (abogados.length < 2) return null
  return (
    <Campo id={id} etiqueta="Lo lleva">
      <select id={id} value={valor ?? perfil.id} onChange={(e) => cambiar(Number(e.target.value))} className={SELECT}>
        {abogados.map((a) => (
          <option key={a.id} value={a.id}>{a.id === perfil.id ? `${a.nombre} (usted)` : a.nombre}</option>
        ))}
      </select>
    </Campo>
  )
}

export const TIPOS: Record<TipoFecha, { nombre: string; ejemplo: string; clase: string }> = {
  audiencia: { nombre: 'Audiencia', ejemplo: 'Audiencia de fondo', clase: 'bg-[#F1E6DE] text-marca-texto' },
  plazo: { nombre: 'Plazo', ejemplo: 'Vence: recurso de apelación', clase: 'bg-aviso text-aviso-texto' },
  reunion: { nombre: 'Reunión', ejemplo: 'Reunión con el cliente', clase: 'bg-muted text-ink-soft' },
  otro: { nombre: 'Otro', ejemplo: 'Buscar la certificación en el tribunal', clase: 'bg-muted text-ink-soft' },
}

export function EtiquetaTipo({ tipo, texto }: { tipo: TipoFecha; texto?: string }) {
  return (
    <span className={cn('shrink-0 rounded-full px-2.5 py-0.5 text-[0.8rem] font-bold', TIPOS[tipo].clase)}>
      {texto ?? TIPOS[tipo].nombre}
    </span>
  )
}

/** La cajita con el día y el mes, como una hoja de calendario */
export function CajaDia({ iso }: { iso: string }) {
  const [dia, mes] = diaYMes(iso)
  return (
    <span className="flex w-[3.25rem] shrink-0 flex-col items-center rounded-lg border border-papel-borde bg-background py-1 leading-tight">
      <span className="text-[0.7rem] font-bold tracking-wide text-marca-texto uppercase">{mes}</span>
      <span className="font-heading text-[1.3rem] font-semibold text-ink">{dia}</span>
    </span>
  )
}

/** Un plazo que vence hoy, mañana o pasado: sale marcado */
export const urge = (f: Pick<Fecha, 'tipo' | 'fecha'>) => f.tipo === 'plazo' && diasPara(f.fecha) >= 0 && diasPara(f.fecha) <= 2

/** Una fecha en una lista: el día, qué es, la hora, el caso y quién la lleva; al tocarla se edita */
export function RenglonFecha({ f, conCaso = true, alTocar }: { f: Fecha; conCaso?: boolean; alTocar: () => void }) {
  const { perfil } = useSesion()
  const detalle = [
    f.hora ? horaBonita(f.hora) : 'Todo el día',
    conCaso && f.expediente?.cliente,
    f.lugar,
    perfil.oficina && f.responsable && f.responsable.id !== perfil.id && f.responsable.nombre,
  ].filter(Boolean)
  return (
    <button
      type="button"
      onClick={alTocar}
      className={cn(
        'flex w-full items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition-colors hover:border-marca',
        urge(f) ? 'border-aviso-texto/30 bg-aviso/50' : 'border-papel-borde bg-card',
      )}
    >
      <CajaDia iso={f.fecha} />
      <span className="min-w-0 flex-1">
        <span className="block font-bold text-ink">{f.titulo}</span>
        <span className="block text-[0.88rem] text-ink-soft">{detalle.join(' · ')}</span>
      </span>
      <EtiquetaTipo tipo={f.tipo} texto={urge(f) ? cuandoEs(f.fecha) : undefined} />
    </button>
  )
}

/** Lo que se está editando: una fecha nueva (sin id) o una que ya está */
export interface BorradorFecha {
  id?: number
  tipo: TipoFecha
  titulo: string
  fecha: string
  hora: string
  lugar: string
  notas: string
  expediente_id: number | null
  responsable_id: number | null
}

export function fechaNueva(fecha = hoyIso(), expediente_id: number | null = null): BorradorFecha {
  return { tipo: 'audiencia', titulo: '', fecha, hora: '', lugar: '', notas: '', expediente_id, responsable_id: null }
}

export function aBorrador(f: Fecha, expediente_id: number | null = f.expediente?.id ?? null): BorradorFecha {
  const { id, tipo, titulo, fecha, hora, lugar, notas } = f
  return { id, tipo, titulo, fecha, hora, lugar, notas, expediente_id, responsable_id: f.responsable?.id ?? null }
}

/**
 * Agregar o cambiar una fecha. Desde un expediente, la fecha ya es de ese caso (fijo); desde la Agenda se elige
 * el caso, o ninguno. Al guardar, la pantalla vuelve a leer lo suyo.
 */
export function DialogoFecha({ inicial, expedientes = [], fijo = false, alCerrar, alGuardar }: {
  inicial: BorradorFecha
  expedientes?: ExpedienteResumen[]
  fijo?: boolean
  alCerrar: () => void
  alGuardar: () => void
}) {
  const [f, setF] = useState(inicial)
  const [guardando, setGuardando] = useState(false)
  const [porBorrar, setPorBorrar] = useState(false)
  const poner = (cambio: Partial<BorradorFecha>) => setF((x) => ({ ...x, ...cambio }))

  async function guardar() {
    setGuardando(true)
    try {
      if (f.id) await api.put(`/api/agenda/${f.id}`, f)
      else await api.post('/api/agenda', f)
      toast.success(f.id ? 'Fecha guardada.' : 'Fecha agregada a la agenda.')
      alGuardar()
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setGuardando(false)
    }
  }

  async function borrar() {
    setGuardando(true)
    try {
      await api.borrar(`/api/agenda/${f.id}`)
      toast.success('Fecha borrada de la agenda.')
      alGuardar()
    } catch (e) {
      toast.error((e as ErrorApi).message)
      setGuardando(false)
    }
  }

  const activos = expedientes.filter((x) => x.estado === 'activo' || x.id === f.expediente_id)
  return (
    <Dialog open onOpenChange={(a) => !a && alCerrar()}>
      <DialogContent className="flex max-h-[92dvh] flex-col sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-medium">{f.id ? 'Cambiar la fecha' : 'Nueva fecha'}</DialogTitle>
          <DialogDescription>Una audiencia, un plazo que vence o una reunión.</DialogDescription>
        </DialogHeader>
        <div className="-mx-1 min-h-0 flex-1 space-y-4 overflow-y-auto px-1 pb-1">
          <fieldset>
            <legend className="mb-1.5 text-[0.9rem] text-ink-soft">Qué tipo de fecha es</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(Object.keys(TIPOS) as TipoFecha[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={f.tipo === t}
                  onClick={() => poner({ tipo: t })}
                  className={cn(
                    'h-11 rounded-lg border text-[0.95rem] transition-colors',
                    f.tipo === t ? 'border-marca bg-marca font-bold text-sobre-boton' : 'border-regla bg-card text-ink hover:border-marca',
                  )}
                >
                  {TIPOS[t].nombre}
                </button>
              ))}
            </div>
          </fieldset>
          <Campo id="fecha-titulo" etiqueta="Qué es">
            <Input
              id="fecha-titulo"
              value={f.titulo}
              onChange={(e) => poner({ titulo: e.target.value })}
              placeholder={`Por ejemplo: ${TIPOS[f.tipo].ejemplo}`}
              className={ENTRADA}
            />
          </Campo>
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo id="fecha-dia" etiqueta="Día">
              <Input id="fecha-dia" type="date" value={f.fecha} onChange={(e) => poner({ fecha: e.target.value })} className={ENTRADA} />
            </Campo>
            <Campo id="fecha-hora" etiqueta="Hora (vacía si es todo el día)">
              <Input id="fecha-hora" type="time" value={f.hora} onChange={(e) => poner({ hora: e.target.value })} className={ENTRADA} />
            </Campo>
          </div>
          <Campo id="fecha-lugar" etiqueta="Lugar (opcional)">
            <Input
              id="fecha-lugar"
              value={f.lugar}
              onChange={(e) => poner({ lugar: e.target.value })}
              placeholder="Por ejemplo: Sala 3"
              className={ENTRADA}
            />
          </Campo>
          {!fijo && (
            <Campo id="fecha-caso" etiqueta="Expediente (opcional)">
              <select
                id="fecha-caso"
                value={f.expediente_id ?? ''}
                onChange={(e) => poner({ expediente_id: e.target.value ? Number(e.target.value) : null })}
                className={SELECT}
              >
                <option value="">Sin expediente</option>
                {activos.map((x) => (
                  <option key={x.id} value={x.id}>{x.asunto ? `${x.cliente} · ${x.asunto}` : x.cliente}</option>
                ))}
              </select>
            </Campo>
          )}
          <CampoResponsable id="fecha-lleva" valor={f.responsable_id} cambiar={(v) => poner({ responsable_id: v })} />
          <Campo id="fecha-notas" etiqueta="Notas (opcional)">
            <Textarea
              id="fecha-notas"
              value={f.notas}
              onChange={(e) => poner({ notas: e.target.value })}
              className="min-h-20 border-pista/80 bg-papel text-base md:text-base"
            />
          </Campo>
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          {f.id ? (
            <Button
              variant={porBorrar ? 'peligro' : 'ghost'}
              size="grande"
              className={cn(!porBorrar && 'text-destructive')}
              disabled={guardando}
              onClick={() => (porBorrar ? borrar() : setPorBorrar(true))}
            >
              <Trash2 /> {porBorrar ? '¿Seguro? Sí, borrar' : 'Borrar'}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="outline" size="grande" className="border-regla" onClick={alCerrar}>Cancelar</Button>
            <Button size="grande" disabled={guardando || !f.titulo.trim() || !f.fecha} onClick={guardar}>
              {guardando && <Loader2 className="animate-spin" />} Guardar
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Para el plan Aspirante: Expedientes y Agenda vienen con el plan Abogado */
export function SinExpedientes({ sala }: { sala: string }) {
  return (
    <Seccion titulo={`${sala} viene con el plan Abogado`}>
      <p className="text-ink-soft">
        Con el plan Abogado tiene sus expedientes (una carpeta por caso, con sus fechas, escritos y documentos) y la
        agenda de audiencias y plazos, y el Escritorio le avisa lo que vence en la semana. Para pasar al plan Abogado,{' '}
        <Link to="/contacto" className="text-marca-texto underline">escríbanos</Link>.
      </p>
    </Seccion>
  )
}
