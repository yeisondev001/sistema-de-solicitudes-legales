import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Building2, Loader2, Trash2, UserPlus } from 'lucide-react'
import { toast } from 'sonner'
import { Cargando } from '@/components/cargando'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ErrorApi } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { OficinaAdmin, Usuario } from '@/lib/tipos'

const PLANES = ['beta', 'prueba', 'basico', 'activo', 'vencido'] as const
// los asientos que paga una oficina: uno por abogado, el dueño incluido (de 4 a 30, como en cuentas.py)
const ASIENTOS = Array.from({ length: 27 }, (_, i) => i + 4)
const casilla = 'size-[1.15rem] accent-[var(--t-accent)]'

/** Administrar usuarios (solo administradores): plan, correo de Google, activo, plantillas y oficina. */
export default function Usuarios() {
  const { perfil } = useSesion()
  const [lista, setLista] = useState<Usuario[] | null>(null)
  const [oficinas, setOficinas] = useState<OficinaAdmin[]>([])
  const [error, setError] = useState('')

  const cargar = useCallback(() => {
    api.get<Usuario[]>('/api/usuarios').then(setLista).catch((e: ErrorApi) => setError(e.message))
    api.get<OficinaAdmin[]>('/api/oficinas').then(setOficinas).catch(() => {})
  }, [])
  useEffect(cargar, [cargar])

  async function cambiar(
    u: Usuario,
    cambio: Partial<Pick<Usuario, 'plan' | 'email' | 'activo' | 'plantillas' | 'oficina_id'>>,
    aviso?: string,
  ) {
    try {
      await api.patch(`/api/usuarios/${u.id}`, cambio)
      if (aviso) toast.success(aviso)
      cargar()
    } catch (e) {
      toast.error((e as ErrorApi).message)
      cargar()
    }
  }

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala titulo="Usuarios" sub="Quién entra al despacho, con qué plan y qué ve." />
      <div className="space-y-5">
        <Seccion titulo="Cuentas">
          {error ? (
            <p className="text-destructive">{error}</p>
          ) : !lista ? (
            <Cargando que="Cargando las cuentas" />
          ) : (
            <ul>
              {lista.map((u) => {
                const propia = u.id === perfil.id
                return (
                  <li key={u.id} className="space-y-3 border-b border-papel-borde py-4 first:pt-0 last:border-b-0 last:pb-0">
                    <p className="text-ink">
                      <strong>{u.nombre || u.usuario}</strong>
                      <span className="text-ink-soft">
                        {' '}· {u.usuario}{u.es_admin ? ' · admin' : ''}
                        {u.plan === 'prueba' && u.prueba_hasta
                          ? ` · prueba hasta ${new Date(u.prueba_hasta * 1000).toLocaleDateString('es-DO')}`
                          : ''}
                        {u.oficina && ` · en ${u.oficina} (vale el plan de la oficina)`}
                      </span>
                    </p>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                      <select
                        value={u.plan}
                        disabled={propia}
                        aria-label={`Plan de ${u.usuario}`}
                        onChange={(e) => cambiar(u, { plan: e.target.value as Usuario['plan'] })}
                        className="h-11 rounded-lg border border-input bg-background px-3 text-[0.95rem] text-ink disabled:opacity-60"
                      >
                        {PLANES.map((p) => (
                          <option key={p} value={p}>{p === 'basico' ? 'básico' : p}</option>
                        ))}
                      </select>
                      <Input
                        defaultValue={u.email}
                        key={`${u.id}-${u.email}`}
                        placeholder="correo de Google"
                        aria-label={`Correo de Google de ${u.usuario}`}
                        className="h-11 bg-background sm:flex-1 text-[0.95rem] md:text-[0.95rem]"
                        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                        onBlur={(e) => {
                          const nuevo = e.target.value.trim().toLowerCase()
                          if (nuevo !== u.email)
                            cambiar(u, { email: nuevo }, nuevo ? 'Correo guardado: con él puede entrar con Google a esta misma cuenta.' : 'Correo quitado.')
                        }}
                      />
                      <label className="flex items-center gap-2 text-[0.95rem] text-ink">
                        <input
                          type="checkbox"
                          className={casilla}
                          checked={u.activo}
                          disabled={propia}
                          onChange={(e) => cambiar(u, { activo: e.target.checked })}
                        />
                        Activo
                      </label>
                    </div>
                    {oficinas.length > 0 && (
                      <select
                        value={u.oficina_id ?? ''}
                        aria-label={`Oficina de ${u.usuario}`}
                        onChange={(e) =>
                          cambiar(
                            u,
                            { oficina_id: e.target.value ? Number(e.target.value) : null },
                            e.target.value ? 'Listo: ya está en la oficina.' : 'Listo: ya no está en ninguna oficina.',
                          )
                        }
                        className="h-11 w-full rounded-lg border border-input bg-background px-3 text-[0.95rem] text-ink sm:w-auto"
                      >
                        <option value="">Sin oficina</option>
                        {oficinas.map((o) => (
                          <option key={o.id} value={o.id}>{o.nombre}</option>
                        ))}
                      </select>
                    )}
                    <label className="flex items-center gap-2 text-[0.95rem] text-ink">
                      <input
                        type="checkbox"
                        className={casilla}
                        checked={u.plantillas}
                        onChange={(e) => cambiar(u, { plantillas: e.target.checked }, 'Listo: se aplica cuando esa persona vuelva a entrar.')}
                      />
                      Ve las plantillas de solicitudes
                    </label>
                  </li>
                )
              })}
            </ul>
          )}
        </Seccion>
        <Oficinas oficinas={oficinas} usuarios={lista ?? []} alCambiar={cargar} />
        <NuevoUsuario alCrear={cargar} />
      </div>
    </div>
  )
}

function NuevoUsuario({ alCrear }: { alCrear: () => void }) {
  const vacio = { usuario: '', nombre: '', clave: '', email: '', es_admin: false, plantillas: false }
  const [f, setF] = useState(vacio)
  const [creando, setCreando] = useState(false)

  async function crear(e: FormEvent) {
    e.preventDefault()
    setCreando(true)
    try {
      await api.post('/api/usuarios', f)
      toast.success(`Usuario «${f.usuario.trim().toLowerCase()}» creado.`)
      setF(vacio)
      alCrear()
    } catch (ex) {
      toast.error((ex as ErrorApi).message)
    } finally {
      setCreando(false)
    }
  }

  const campo = (clave: 'usuario' | 'nombre' | 'clave' | 'email', etiqueta: string, tipo = 'text') => (
    <div className="flex-1 space-y-1.5">
      <Label htmlFor={`nuevo-${clave}`} className="text-[0.9rem] text-ink-soft">{etiqueta}</Label>
      <Input
        id={`nuevo-${clave}`}
        type={tipo}
        autoComplete={tipo === 'password' ? 'new-password' : 'off'}
        value={f[clave]}
        onChange={(e) => setF({ ...f, [clave]: e.target.value })}
        className="h-11 bg-background text-base md:text-base"
      />
    </div>
  )

  return (
    <Seccion titulo="Nuevo usuario">
      <form onSubmit={crear} className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row">
          {campo('usuario', 'Usuario')}
          {campo('nombre', 'Nombre')}
        </div>
        <div className="flex flex-col gap-4 sm:flex-row">
          {campo('clave', 'Contraseña', 'password')}
          {campo('email', 'Correo de Google (opcional)', 'email')}
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <label className="flex items-center gap-2 text-[0.95rem] text-ink">
            <input type="checkbox" className={casilla} checked={f.es_admin} onChange={(e) => setF({ ...f, es_admin: e.target.checked })} />
            Administrador
          </label>
          <label className="flex items-center gap-2 text-[0.95rem] text-ink">
            <input type="checkbox" className={casilla} checked={f.plantillas} onChange={(e) => setF({ ...f, plantillas: e.target.checked })} />
            Ve las plantillas de solicitudes
          </label>
        </div>
        <Button type="submit" size="grande" disabled={creando}>
          {creando ? <Loader2 className="animate-spin" /> : <UserPlus />} Crear usuario
        </Button>
      </form>
    </Seccion>
  )
}

/** Las oficinas del plan Despacho: su dueño, cuántos abogados tiene y su plan, que vale para todos ellos */
function Oficinas({ oficinas, usuarios, alCambiar }: { oficinas: OficinaAdmin[]; usuarios: Usuario[]; alCambiar: () => void }) {
  const [nombre, setNombre] = useState('')
  const [dueno, setDueno] = useState('')
  const [asientos, setAsientos] = useState(4)
  const [creando, setCreando] = useState(false)
  const [porBorrar, setPorBorrar] = useState<OficinaAdmin | null>(null)
  const libres = usuarios.filter((u) => !u.oficina_id)

  async function hacer(accion: () => Promise<unknown>, aviso: string) {
    try {
      await accion()
      toast.success(aviso)
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
    alCambiar()
  }

  async function crear(e: FormEvent) {
    e.preventDefault()
    setCreando(true)
    await hacer(() => api.post('/api/oficinas', { nombre, dueno_id: Number(dueno), asientos }), `Oficina «${nombre.trim()}» creada.`)
    setNombre('')
    setDueno('')
    setAsientos(4)
    setCreando(false)
  }

  return (
    <Seccion titulo="Oficinas (plan Despacho)">
      {oficinas.length ? (
        <ul className="mb-5">
          {oficinas.map((o) => (
            <li key={o.id} className="flex flex-wrap items-center gap-3 border-b border-papel-borde py-3 first:pt-0 last:border-b-0">
              <Building2 className="size-5 shrink-0 text-marca-texto" />
              <p className="min-w-0 flex-1 text-ink">
                <strong>{o.nombre}</strong>
                <span className="text-ink-soft"> · dueño: {o.dueno} · {o.abogados} abogado{o.abogados === 1 ? '' : 's'}</span>
              </p>
              <select
                value={o.asientos}
                aria-label={`Asientos de ${o.nombre}`}
                title="Asientos que paga (uno por abogado)"
                onChange={(e) => hacer(() => api.patch(`/api/oficinas/${o.id}`, { asientos: Number(e.target.value) }), 'Asientos cambiados.')}
                className="h-11 rounded-lg border border-input bg-background px-3 text-[0.95rem] text-ink"
              >
                {ASIENTOS.map((n) => (
                  <option key={n} value={n}>{n} asientos</option>
                ))}
              </select>
              <select
                value={o.plan}
                aria-label={`Plan de ${o.nombre}`}
                onChange={(e) => hacer(() => api.patch(`/api/oficinas/${o.id}`, { plan: e.target.value }), 'Plan de la oficina cambiado.')}
                className="h-11 rounded-lg border border-input bg-background px-3 text-[0.95rem] text-ink"
              >
                <option value="activo">activo</option>
                <option value="vencido">vencido</option>
              </select>
              <Button
                variant="ghost"
                size="icon-grande"
                className="text-ink-soft"
                aria-label={`Borrar ${o.nombre}`}
                title="Borrar la oficina"
                onClick={() => setPorBorrar(o)}
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-5 text-ink-soft">Todavía no hay oficinas.</p>
      )}
      <form onSubmit={crear} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="oficina-nombre" className="text-[0.9rem] text-ink-soft">Nombre de la oficina</Label>
          <Input id="oficina-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} className="h-11 bg-background text-base md:text-base" />
        </div>
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="oficina-dueno" className="text-[0.9rem] text-ink-soft">Dueño (una cuenta que ya existe)</Label>
          <select
            id="oficina-dueno"
            value={dueno}
            onChange={(e) => setDueno(e.target.value)}
            className="h-11 w-full rounded-lg border border-input bg-background px-3 text-[0.95rem] text-ink"
          >
            <option value="">Elegir…</option>
            {libres.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre || u.usuario}
                {u.email ? ` (${u.email})` : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="oficina-asientos" className="text-[0.9rem] text-ink-soft">Asientos</Label>
          <select
            id="oficina-asientos"
            value={asientos}
            onChange={(e) => setAsientos(Number(e.target.value))}
            className="h-11 w-full rounded-lg border border-input bg-background px-3 text-[0.95rem] text-ink"
          >
            {ASIENTOS.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <Button type="submit" size="grande" disabled={creando || !nombre.trim() || !dueno}>
          {creando ? <Loader2 className="animate-spin" /> : <Building2 />} Crear oficina
        </Button>
      </form>
      <p className="mt-3 text-[0.9rem] text-ink-soft">
        El dueño agrega a sus abogados desde «Mi oficina» con el correo de cada uno, hasta llenar los asientos que
        paga (él ocupa uno). Mientras la oficina esté activa, todos usan Papiniano sin límite; si la pone vencida,
        ninguno puede entrar.
      </p>

      <AlertDialog open={Boolean(porBorrar)} onOpenChange={(a) => !a && setPorBorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Borrar {porBorrar?.nombre}?</AlertDialogTitle>
            <AlertDialogDescription>
              Cada abogado sigue con su cuenta y todo lo suyo, pero con el plan que tenía su cuenta antes de entrar (si
              era una prueba vencida, ya no podrá entrar). Sus modelos dejan de estar compartidos.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="peligro"
              size="grande"
              onClick={() => porBorrar && hacer(() => api.borrar(`/api/oficinas/${porBorrar.id}`), 'Oficina borrada.')}
            >
              <Trash2 /> Sí, borrar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Seccion>
  )
}
