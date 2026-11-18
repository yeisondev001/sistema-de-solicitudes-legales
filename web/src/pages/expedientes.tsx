import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, FileText, Lock, MessageSquare, PencilLine, Plus, Search, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  Campo, CampoResponsable, DialogoFecha, ENTRADA, RenglonFecha, SinExpedientes, aBorrador, fechaNueva,
  type BorradorFecha,
} from '@/components/agenda'
import { Cargando } from '@/components/cargando'
import { TituloSala } from '@/components/oficina'
import { Papiniano } from '@/components/papiniano'
import { Renglon, Seccion } from '@/components/seccion'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api, type ErrorApi } from '@/lib/api'
import { cuando, cuandoEs, diaYMes, horaBonita } from '@/lib/fechas'
import { useSesion } from '@/lib/sesion'
import { iniciales } from '@/lib/tema'
import type { Documento, Expediente, ExpedienteResumen } from '@/lib/tipos'
import { cn } from '@/lib/utils'

/** Sin tildes ni mayúsculas, para buscar «perez» y encontrar «Pérez» */
const normal = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

/**
 * Expedientes: una carpeta por caso. En una oficina son de todos sus abogados; cada uno dice quién lo lleva.
 * /expedientes es la lista; /expedientes/:id, un expediente por dentro.
 */
export default function Expedientes() {
  const { id } = useParams()
  const { perfil } = useSesion()
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8 md:py-8">
      {!perfil.propios ? (
        <>
          <TituloSala titulo="Expedientes" />
          <SinExpedientes sala="Expedientes" />
        </>
      ) : id ? (
        <Detalle key={id} id={Number(id)} />
      ) : (
        <Lista />
      )}
    </div>
  )
}

const ESTADOS = [['activo', 'Activos'], ['cerrado', 'Cerrados'], ['todos', 'Todos']] as const

/** Unos botones juntos para elegir una opción (como pestañas) */
function Opciones<T extends string>({ opciones, valor, cambiar, nombre }: {
  opciones: readonly (readonly [T, string])[]
  valor: T
  cambiar: (v: T) => void
  nombre: string
}) {
  return (
    <div role="group" aria-label={nombre} className="inline-flex rounded-full border border-regla bg-card p-1">
      {opciones.map(([v, texto]) => (
        <button
          key={v}
          type="button"
          aria-pressed={valor === v}
          onClick={() => cambiar(v)}
          className={cn(
            'min-h-9 rounded-full px-3.5 text-[0.92rem] transition-colors',
            valor === v ? 'bg-panel font-bold text-sobre-panel' : 'text-ink-soft hover:text-ink',
          )}
        >
          {texto}
        </button>
      ))}
    </div>
  )
}

function Lista() {
  const { perfil } = useSesion()
  const navegar = useNavigate()
  const [lista, setLista] = useState<ExpedienteResumen[] | null>(null)
  const [buscar, setBuscar] = useState('')
  const [estado, setEstado] = useState<(typeof ESTADOS)[number][0]>('activo')
  const [de, setDe] = useState<'oficina' | 'mios'>('oficina')
  const [nuevo, setNuevo] = useState(false)

  useEffect(() => {
    api.get<ExpedienteResumen[]>('/api/expedientes').then(setLista).catch((e: ErrorApi) => {
      toast.error(e.message)
      setLista([])
    })
  }, [])

  const q = normal(buscar.trim())
  const vistos = (lista ?? []).filter(
    (x) =>
      (estado === 'todos' || x.estado === estado) &&
      (de === 'oficina' || x.responsable?.id === perfil.id) &&
      (!q || normal([x.cliente, x.asunto, x.numero, x.tribunal, x.contraparte].join(' ')).includes(q)),
  )
  const activos = (lista ?? []).filter((x) => x.estado === 'activo').length

  return (
    <>
      <TituloSala
        titulo="Expedientes"
        sub={lista ? `${activos} activo${activos === 1 ? '' : 's'}${perfil.oficina ? ' en la oficina' : ''}` : undefined}
      >
        <Button size="grande" onClick={() => setNuevo(true)}>
          <Plus /> Nuevo expediente
        </Button>
      </TituloSala>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex h-11 min-w-[16rem] flex-1 items-center gap-2.5 rounded-lg border border-regla bg-card px-3.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
          <Search className="size-[1.1rem] shrink-0 text-ink-soft" />
          <span className="sr-only">Buscar expedientes</span>
          <input
            value={buscar}
            onChange={(e) => setBuscar(e.target.value)}
            placeholder="Buscar por cliente, número o tribunal…"
            className="min-w-0 flex-1 bg-transparent text-base text-ink outline-none placeholder:text-ink-soft"
          />
        </label>
        <Opciones nombre="Estado" opciones={ESTADOS} valor={estado} cambiar={setEstado} />
        {perfil.oficina && (
          <Opciones nombre="De quién" opciones={[['oficina', 'De la oficina'], ['mios', 'Los que llevo']] as const} valor={de} cambiar={setDe} />
        )}
      </div>

      {lista === null ? (
        <Cargando renglones={4} que="Cargando sus expedientes" />
      ) : !lista.length ? (
        <Seccion titulo="Todavía no hay expedientes">
          <p className="text-ink-soft">
            Cree uno por cada caso: el cliente, el número, el tribunal y sus fechas. Después puede guardar en él sus
            conversaciones con Papiniano, sus escritos y sus documentos.
          </p>
          <Button size="grande" className="mt-4" onClick={() => setNuevo(true)}>
            <Plus /> Crear el primero
          </Button>
        </Seccion>
      ) : !vistos.length ? (
        <p className="rounded-2xl border border-papel-borde bg-card p-6 text-ink-soft">Ningún expediente coincide con lo que busca.</p>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-papel-borde bg-card">
          <div className="hidden grid-cols-[1.5fr_1fr_1.1fr_1.05fr_3rem] gap-4 bg-muted/60 px-5 py-2.5 text-[0.78rem] font-bold tracking-wider text-pista uppercase md:grid">
            <span>Cliente y asunto</span>
            <span>Expediente</span>
            <span>Tribunal</span>
            <span>Próxima fecha</span>
            <span>{perfil.oficina ? 'Lleva' : ''}</span>
          </div>
          {vistos.map((x) => (
            <Link
              key={x.id}
              to={`/expedientes/${x.id}`}
              className="grid gap-1 border-t border-papel-borde px-5 py-4 hover:bg-muted/40 md:grid-cols-[1.5fr_1fr_1.1fr_1.05fr_3rem] md:items-center md:gap-4 [&:nth-child(2)]:border-t-0 md:[&:nth-child(2)]:border-t"
            >
              <span className="min-w-0">
                <span className="block font-bold text-ink">{x.cliente}</span>
                {x.asunto && <span className="block text-[0.9rem] text-ink-soft">{x.asunto}</span>}
                {x.estado === 'cerrado' && (
                  <span className="mt-1 inline-block rounded-full bg-muted px-2.5 py-0.5 text-[0.78rem] font-bold text-ink-soft">Cerrado</span>
                )}
              </span>
              <span className="text-[0.92rem] text-ink">{x.numero && `Núm. ${x.numero}`}</span>
              <span className="text-[0.9rem] text-ink-soft">{x.tribunal}</span>
              <span className="text-[0.92rem]">
                {x.proxima ? (
                  <>
                    <span className="block font-bold text-marca-texto">
                      {x.proxima.tipo === 'plazo' ? 'Vence plazo' : x.proxima.titulo} · {cuandoEs(x.proxima.fecha)}
                    </span>
                    <span className="block text-ink-soft">
                      {diaYMes(x.proxima.fecha).join(' ')}
                      {x.proxima.hora && `, ${horaBonita(x.proxima.hora)}`}
                      {x.proxima.tipo === 'plazo' && ` · ${x.proxima.titulo}`}
                    </span>
                  </>
                ) : (
                  <span className="text-ink-soft">Sin fechas próximas</span>
                )}
              </span>
              <span>
                {perfil.oficina && x.responsable && (
                  <span
                    title={`Lo lleva ${x.responsable.nombre}`}
                    className="inline-flex size-9 items-center justify-center rounded-full bg-[#F1E8DA] text-[0.8rem] font-bold text-panel"
                  >
                    {iniciales(x.responsable.nombre)}
                  </span>
                )}
              </span>
            </Link>
          ))}
        </div>
      )}

      {nuevo && (
        <DialogoExpediente
          inicial={null}
          alCerrar={() => setNuevo(false)}
          alGuardar={(x) => navegar(`/expedientes/${x.id}`)}
        />
      )}
    </>
  )
}

function Detalle({ id }: { id: number }) {
  const navegar = useNavigate()
  const { perfil } = useSesion()
  const [x, setX] = useState<Expediente | null>(null)
  const [editando, setEditando] = useState(false)
  const [fecha, setFecha] = useState<BorradorFecha | null>(null)
  const [agregarDoc, setAgregarDoc] = useState(false)

  const cargar = useCallback(() => {
    api.get<Expediente>(`/api/expedientes/${id}`).then(setX).catch((e: ErrorApi) => {
      toast.error(e.message)
      navegar('/expedientes', { replace: true })
    })
  }, [id, navegar])
  useEffect(cargar, [cargar])

  async function quitarDocumento(doc: number) {
    try {
      setX(await api.borrar<Expediente>(`/api/expedientes/${id}/documentos/${doc}`))
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  if (!x) return <Cargando renglones={5} que="Abriendo el expediente" />

  const ficha: [string, string][] = [
    ['Expediente', x.numero ? `Núm. ${x.numero}` : '—'],
    ['Tribunal', x.tribunal || '—'],
    ['Contraparte', x.contraparte || '—'],
    ...(perfil.oficina ? [['Lo lleva', x.responsable?.nombre ?? '—'] as [string, string]] : []),
  ]

  return (
    <>
      <Link to="/expedientes" className="-ml-1 mb-2 inline-flex min-h-11 items-center gap-1 text-[0.95rem] text-marca-texto hover:underline">
        <ChevronLeft className="size-4" /> Expedientes
      </Link>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-ink pb-5">
        <div className="min-w-0 space-y-1">
          <h1 className="font-heading text-[2rem] leading-tight font-medium text-ink md:text-[2.4rem]">{x.cliente}</h1>
          <p className="text-[0.98rem] text-ink-soft">
            {x.asunto}
            <span
              className={cn(
                'ml-2 inline-block rounded-full px-2.5 py-0.5 text-[0.78rem] font-bold',
                x.estado === 'activo' ? 'bg-[#E4F0E6] text-[#2F6B3E]' : 'bg-muted text-ink-soft',
              )}
            >
              {x.estado === 'activo' ? 'Activo' : 'Cerrado'}
            </span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="grande" className="border-regla" onClick={() => setEditando(true)}>
            <PencilLine /> Editar
          </Button>
          <Button size="grande" onClick={() => navegar(`/papiniano?expediente=${x.id}`)}>
            <Papiniano className="size-6" decorativo /> Consultar a Papiniano sobre este caso
          </Button>
        </div>
      </header>

      <dl className={cn('mb-5 grid gap-px overflow-hidden rounded-2xl border border-papel-borde bg-papel-borde sm:grid-cols-2', ficha.length === 4 ? 'lg:grid-cols-4' : 'lg:grid-cols-3')}>
        {ficha.map(([nombre, valor]) => (
          <div key={nombre} className="bg-card px-4 py-3">
            <dt className="text-[0.75rem] font-bold tracking-wider text-pista uppercase">{nombre}</dt>
            <dd className="text-ink">{valor}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-5 lg:grid-cols-[1.15fr_1fr]">
        <div className="space-y-5">
          <section className="rounded-2xl border border-papel-borde bg-card p-5 md:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="font-heading text-[1.35rem] font-medium text-ink">Fechas</h2>
              <Button variant="ghost" className="-my-2 h-11 text-marca-texto" onClick={() => setFecha(fechaNueva(undefined, x.id))}>
                <Plus /> Agregar fecha
              </Button>
            </div>
            {x.fechas.length ? (
              <div className="space-y-2">
                {x.fechas.map((f) => (
                  <RenglonFecha key={f.id} f={f} conCaso={false} alTocar={() => setFecha(aBorrador(f, x.id))} />
                ))}
              </div>
            ) : (
              <p className="text-ink-soft">Sin fechas. Agregue las audiencias y los plazos de este caso.</p>
            )}
          </section>

          <section className="rounded-2xl border border-papel-borde bg-card p-5 md:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="font-heading text-[1.35rem] font-medium text-ink">Escritos y conversaciones</h2>
              <Button variant="ghost" className="-my-2 h-11 text-marca-texto" onClick={() => navegar(`/papiniano?expediente=${x.id}`)}>
                <MessageSquare /> Nueva consulta
              </Button>
            </div>
            {x.conversaciones.length ? (
              x.conversaciones.map((c) => (
                <Renglon
                  key={c.id}
                  titulo={c.titulo}
                  detalle={`${c.con_escrito ? 'Con escrito · ' : ''}${cuando(c.actualizada)}`}
                  a={`/papiniano/${c.id}`}
                />
              ))
            ) : (
              <p className="text-ink-soft">
                Consulte a Papiniano desde aquí, o en una conversación toque «Expediente» para guardarla en este caso.
                {perfil.oficina && ' Cada abogado ve solo las suyas.'}
              </p>
            )}
          </section>
        </div>

        <div className="space-y-5">
          <section className="rounded-2xl border border-papel-borde bg-card p-5 md:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="font-heading text-[1.35rem] font-medium text-ink">Documentos</h2>
              <Button variant="ghost" className="-my-2 h-11 text-marca-texto" onClick={() => setAgregarDoc(true)}>
                <Plus /> Agregar
              </Button>
            </div>
            {x.documentos.length ? (
              <ul>
                {x.documentos.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 border-b border-papel-borde py-2 last:border-b-0">
                    <FileText className="size-5 shrink-0 text-marca-texto" />
                    <span className="min-w-0 flex-1 font-bold text-ink">{d.nombre}</span>
                    <Button
                      variant="ghost"
                      size="icon-grande"
                      className="text-ink-soft"
                      aria-label={`Quitar «${d.nombre}» del expediente`}
                      title="Quitar del expediente (sigue en su Biblioteca)"
                      onClick={() => quitarDocumento(d.id)}
                    >
                      <X />
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ink-soft">Guarde aquí los documentos de este caso que subió a su Biblioteca.</p>
            )}
          </section>

          <Seccion titulo="Notas">
            {x.notas ? <p className="whitespace-pre-line text-ink">{x.notas}</p> : <p className="text-ink-soft">Sin notas. Se agregan con «Editar».</p>}
          </Seccion>

          <p className="flex gap-3 rounded-2xl border border-dashed border-regla bg-muted/40 px-4 py-3.5 text-[0.92rem] text-ink-soft">
            <Lock className="mt-0.5 size-[1.1rem] shrink-0" />
            <span>
              Los datos del cliente y del caso se guardan en {perfil.oficina ? 'su oficina de ' : 'su cuenta de '}Papiniano y{' '}
              <strong className="text-ink">no se le mandan a la IA</strong> (Ley 172-13). Al consultar sobre este caso,
              Papiniano solo recibe su pregunta.
            </span>
          </p>
        </div>
      </div>

      {editando && (
        <DialogoExpediente
          inicial={x}
          alCerrar={() => setEditando(false)}
          alGuardar={(nuevo) => {
            setX(nuevo)
            setEditando(false)
          }}
          alBorrar={() => navegar('/expedientes', { replace: true })}
        />
      )}
      {fecha && (
        <DialogoFecha
          inicial={fecha}
          fijo
          alCerrar={() => setFecha(null)}
          alGuardar={() => {
            setFecha(null)
            cargar()
          }}
        />
      )}
      {agregarDoc && (
        <DialogoDocumento
          expediente={x}
          alCerrar={() => setAgregarDoc(false)}
          alGuardar={(nuevo) => {
            setX(nuevo)
            setAgregarDoc(false)
          }}
        />
      )}
    </>
  )
}

const CAMPOS: [keyof Expediente & string, string, string][] = [
  ['asunto', 'Asunto', 'Por ejemplo: Litis sobre derechos registrados'],
  ['numero', 'Número de expediente', 'Por ejemplo: 0312-2025-01458'],
  ['tribunal', 'Tribunal', 'Por ejemplo: Tierras de Jurisdicción Original, Santiago'],
  ['contraparte', 'Contraparte', ''],
]

/** Crear o editar un expediente; al editar también se cierra o se borra */
function DialogoExpediente({ inicial, alCerrar, alGuardar, alBorrar }: {
  inicial: Expediente | null
  alCerrar: () => void
  alGuardar: (x: Expediente) => void
  alBorrar?: () => void
}) {
  const [d, setD] = useState({
    cliente: inicial?.cliente ?? '',
    asunto: inicial?.asunto ?? '',
    numero: inicial?.numero ?? '',
    tribunal: inicial?.tribunal ?? '',
    contraparte: inicial?.contraparte ?? '',
    notas: inicial?.notas ?? '',
    estado: inicial?.estado ?? 'activo',
    responsable_id: inicial?.responsable?.id ?? null,
  })
  const [guardando, setGuardando] = useState(false)
  const [porBorrar, setPorBorrar] = useState(false)

  async function guardar() {
    setGuardando(true)
    try {
      const x = inicial
        ? await api.put<Expediente>(`/api/expedientes/${inicial.id}`, d)
        : await api.post<Expediente>('/api/expedientes', d)
      toast.success(inicial ? 'Expediente guardado.' : 'Expediente creado.')
      alGuardar(x)
    } catch (e) {
      toast.error((e as ErrorApi).message)
      setGuardando(false)
    }
  }

  async function borrar() {
    if (!inicial) return
    setGuardando(true)
    try {
      await api.borrar(`/api/expedientes/${inicial.id}`)
      toast.success('Expediente borrado.')
      alBorrar?.()
    } catch (e) {
      toast.error((e as ErrorApi).message)
      setGuardando(false)
    }
  }

  return (
    <Dialog open onOpenChange={(a) => !a && alCerrar()}>
      <DialogContent className="flex max-h-[92dvh] flex-col sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-medium">{inicial ? 'Editar el expediente' : 'Nuevo expediente'}</DialogTitle>
          <DialogDescription>
            Los datos del caso se guardan en Papiniano y no se le mandan a la IA. No ponga la cédula: no hace falta.
          </DialogDescription>
        </DialogHeader>
        <div className="-mx-1 min-h-0 flex-1 space-y-4 overflow-y-auto px-1 pb-1">
          <Campo id="exp-cliente" etiqueta="Cliente">
            <Input
              id="exp-cliente"
              value={d.cliente}
              onChange={(e) => setD({ ...d, cliente: e.target.value })}
              placeholder="Nombre de la persona o de la empresa"
              className={ENTRADA}
            />
          </Campo>
          <div className="grid gap-4 sm:grid-cols-2">
            {CAMPOS.map(([clave, etiqueta, ejemplo]) => (
              <Campo key={clave} id={`exp-${clave}`} etiqueta={`${etiqueta} (opcional)`}>
                <Input
                  id={`exp-${clave}`}
                  value={d[clave as keyof typeof d] as string}
                  onChange={(e) => setD({ ...d, [clave]: e.target.value })}
                  placeholder={ejemplo}
                  className={ENTRADA}
                />
              </Campo>
            ))}
          </div>
          <CampoResponsable id="exp-lleva" valor={d.responsable_id} cambiar={(v) => setD({ ...d, responsable_id: v })} />
          <Campo id="exp-notas" etiqueta="Notas (opcional)">
            <Textarea
              id="exp-notas"
              value={d.notas}
              onChange={(e) => setD({ ...d, notas: e.target.value })}
              className="min-h-24 border-pista/80 bg-papel text-base md:text-base"
            />
          </Campo>
          {inicial && (
            <label className="flex items-start gap-3 rounded-xl border border-regla bg-card px-4 py-3 text-ink">
              <input
                type="checkbox"
                className="mt-1 size-[1.15rem] accent-[var(--t-accent)]"
                checked={d.estado === 'cerrado'}
                onChange={(e) => setD({ ...d, estado: e.target.checked ? 'cerrado' : 'activo' })}
              />
              <span>
                <span className="block font-bold">Caso cerrado</span>
                <span className="block text-[0.9rem] text-ink-soft">Sale en «Cerrados» y deja de aparecer al agendar fechas.</span>
              </span>
            </label>
          )}
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          {inicial ? (
            <Button
              variant={porBorrar ? 'peligro' : 'ghost'}
              size="grande"
              className={cn(!porBorrar && 'text-destructive')}
              disabled={guardando}
              onClick={() => (porBorrar ? borrar() : setPorBorrar(true))}
            >
              <Trash2 /> {porBorrar ? '¿Seguro? Se borran también sus fechas' : 'Borrar expediente'}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="outline" size="grande" className="border-regla" onClick={alCerrar}>Cancelar</Button>
            <Button size="grande" disabled={guardando || !d.cliente.trim()} onClick={guardar}>
              {inicial ? 'Guardar' : 'Crear expediente'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Guardar en el expediente uno de sus documentos de la Biblioteca */
function DialogoDocumento({ expediente, alCerrar, alGuardar }: {
  expediente: Expediente
  alCerrar: () => void
  alGuardar: (x: Expediente) => void
}) {
  const [docs, setDocs] = useState<Documento[] | null>(null)
  useEffect(() => {
    api
      .get<{ documentos: Documento[] }>('/api/documentos')
      .then((r) => setDocs(r.documentos))
      .catch((e: ErrorApi) => {
        toast.error(e.message)
        setDocs([])
      })
  }, [])

  async function poner(doc: Documento) {
    try {
      alGuardar(await api.post<Expediente>(`/api/expedientes/${expediente.id}/documentos`, { doc_id: doc.id }))
      toast.success(`«${doc.titulo}» quedó en el expediente.`)
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  const yaEstan = new Set(expediente.documentos.map((d) => d.id))
  const libres = (docs ?? []).filter((d) => !yaEstan.has(d.id))
  return (
    <Dialog open onOpenChange={(a) => !a && alCerrar()}>
      <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-medium">Agregar un documento</DialogTitle>
          <DialogDescription>Elija uno de los documentos que subió a su Biblioteca. Solo usted lo ve en el expediente.</DialogDescription>
        </DialogHeader>
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
          {docs === null ? (
            <Cargando renglones={3} que="Cargando sus documentos" />
          ) : libres.length ? (
            libres.map((d) => (
              <Renglon key={d.id} titulo={d.titulo} detalle={[d.numero, d.materia].filter(Boolean).join(' · ')} alTocar={() => poner(d)} />
            ))
          ) : (
            <p className="text-ink-soft">
              {docs.length ? 'Ya están todos en este expediente.' : 'Todavía no ha subido documentos.'}{' '}
              <Link to="/biblioteca" className="text-marca-texto underline">Subir en la Biblioteca</Link>
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
