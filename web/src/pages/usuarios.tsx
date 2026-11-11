import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Loader2, UserPlus } from 'lucide-react'
import { toast } from 'sonner'
import { Cargando } from '@/components/cargando'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ErrorApi } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Usuario } from '@/lib/tipos'

const PLANES = ['beta', 'prueba', 'activo', 'vencido'] as const
const casilla = 'size-[1.15rem] accent-[var(--t-accent)]'

/** Administrar usuarios (solo administradores): plan, correo de Google, activo y plantillas. */
export default function Usuarios() {
  const { perfil } = useSesion()
  const [lista, setLista] = useState<Usuario[] | null>(null)
  const [error, setError] = useState('')

  const cargar = useCallback(() => {
    api.get<Usuario[]>('/api/usuarios').then(setLista).catch((e: ErrorApi) => setError(e.message))
  }, [])
  useEffect(cargar, [cargar])

  async function cambiar(u: Usuario, cambio: Partial<Pick<Usuario, 'plan' | 'email' | 'activo' | 'plantillas'>>, aviso?: string) {
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
                          <option key={p} value={p}>{p}</option>
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
