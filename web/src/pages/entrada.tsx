import { useEffect, useState, type FormEvent } from 'react'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { Logo } from '@/components/logo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ErrorApi } from '@/lib/api'
import type { Entrada as DatosEntrada, Perfil } from '@/lib/tipos'

/** La recepción: a la izquierda qué es el despacho; a la derecha, la entrada (Google y usuario). */
export default function Entrada({ alEntrar }: { alEntrar: (p: Perfil) => void }) {
  const [datos, setDatos] = useState<DatosEntrada | null>(null)
  // si Google no dejó entrar, vuelve con ?error=…; se muestra y se limpia la dirección
  const [error, setError] = useState(() => new URLSearchParams(window.location.search).get('error') ?? '')

  useEffect(() => {
    if (window.location.search) window.history.replaceState(null, '', '/')
    api.get<DatosEntrada>('/api/entrada').then(setDatos).catch((e: ErrorApi) => setError(e.message))
  }, [])

  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b border-papel-borde">
        <div className="mx-auto flex max-w-[1240px] items-center px-5 py-4">
          <Logo />
        </div>
      </header>
      <main className="mx-auto grid max-w-[1240px] items-center gap-10 px-5 py-8 md:grid-cols-[7fr_5fr] md:gap-12 md:py-[72px]">
        <section className="order-2 space-y-6 md:order-1">
          <p className="text-sm font-bold tracking-wide text-marca-texto">PARA ABOGADOS DE REPÚBLICA DOMINICANA</p>
          <h1 className="font-heading text-4xl leading-tight font-medium text-ink md:text-[3.4rem]">
            Todo su trabajo, en una sola oficina.
          </h1>
          <p className="max-w-[38rem] text-lg leading-relaxed text-ink-soft md:text-[1.15rem]">
            Investigue con las sentencias de la Suprema Corte y las leyes, calcule prestaciones y guarde sus documentos
            sin salir de aquí. Su asistente lee por usted y le muestra la página exacta de cada cita.
          </p>
          <ul className="flex flex-wrap gap-x-7 gap-y-2.5 border-t border-papel-borde pt-5 text-[0.95rem] text-ink-soft">
            <li><strong className="text-ink">Sentencias</strong> de la Suprema Corte</li>
            <li><strong className="text-ink">Leyes</strong> artículo por artículo</li>
            <li><strong className="text-ink">Sus documentos</strong> en el mismo buscador</li>
          </ul>
        </section>
        <section className="order-1 md:order-2">
          <div className="mx-auto w-full max-w-[460px] rounded-2xl border border-papel-borde bg-card p-6 shadow-[0_18px_44px_-12px_color-mix(in_oklab,var(--t-ink)_14%,transparent)] md:p-8">
            {datos ? (
              datos.primera_vez ? (
                <CrearAdmin datos={datos} alEntrar={alEntrar} />
              ) : (
                <Entrar datos={datos} alEntrar={alEntrar} errorInicial={error} />
              )
            ) : error ? (
              <p className="text-sm text-destructive" role="alert">{error}</p>
            ) : (
              <div className="flex items-center gap-3 text-ink-soft">
                <Loader2 className="size-5 animate-spin" /> Un momento…
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

function Campo({
  id, etiqueta, clave = false, ...props
}: { id: string; etiqueta: string; clave?: boolean } & React.ComponentProps<typeof Input>) {
  const [ver, setVer] = useState(false)
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-[0.95rem] text-ink-soft">{etiqueta}</Label>
      <div className="relative">
        <Input
          id={id}
          type={clave && !ver ? 'password' : 'text'}
          className="h-12 bg-background px-3.5 text-base md:text-base"
          {...props}
        />
        {clave && (
          <button
            type="button"
            onClick={() => setVer(!ver)}
            className="absolute inset-y-0 right-0 flex w-12 items-center justify-center text-ink-soft hover:text-ink"
            aria-label={ver ? 'Ocultar la contraseña' : 'Mostrar la contraseña'}
          >
            {ver ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
          </button>
        )}
      </div>
    </div>
  )
}

function Encabezado({ titulo, sub }: { titulo: string; sub: string }) {
  return (
    <div className="space-y-1.5">
      <h2 className="font-heading text-[1.75rem] font-medium text-ink">{titulo}</h2>
      <p className="text-[0.95rem] text-ink-soft">{sub}</p>
    </div>
  )
}

function Entrar({ datos, alEntrar, errorInicial }: { datos: DatosEntrada; alEntrar: (p: Perfil) => void; errorInicial: string }) {
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const [error, setError] = useState(errorInicial)
  const [entrando, setEntrando] = useState(false)

  async function entrar(e: FormEvent) {
    e.preventDefault()
    setEntrando(true)
    setError('')
    try {
      alEntrar(await api.post<Perfil>('/api/entrar', { usuario, clave }))
    } catch (ex) {
      setError((ex as ErrorApi).message)
      setEntrando(false)
    }
  }

  return (
    <form onSubmit={entrar} className="flex flex-col gap-4">
      <Encabezado
        titulo="Entrar a su despacho"
        sub={datos.google ? 'Con su cuenta de Gmail, en un clic.' : 'Con su usuario y contraseña.'}
      />
      {datos.google && (
        <>
          <a
            href="/api/google"
            className="flex h-12 items-center justify-center gap-3 rounded-lg border border-[#747775] bg-white text-base font-bold text-[#1F1F1F] transition-colors hover:bg-[#F7F8F8]"
          >
            <img src="/google_g.svg" alt="" className="size-5" />
            Continuar con Google
          </a>
          <div className="flex items-center gap-3 text-sm text-pista">
            <span className="h-px flex-1 bg-papel-borde" />o con usuario y contraseña
            <span className="h-px flex-1 bg-papel-borde" />
          </div>
        </>
      )}
      <Campo id="usuario" etiqueta="Usuario" autoComplete="username" value={usuario} onChange={(e) => setUsuario(e.target.value)} />
      <Campo id="clave" etiqueta="Contraseña" clave autoComplete="current-password" value={clave} onChange={(e) => setClave(e.target.value)} />
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      <Button type="submit" size="grande" disabled={entrando} className="h-12 bg-panel text-sobre-panel hover:bg-panel/90">
        {entrando && <Loader2 className="animate-spin" />}
        {entrando ? 'Un momento…' : 'Entrar'}
      </Button>
      {datos.google && (
        <p className="rounded-lg border border-papel-borde bg-background px-3.5 py-3 text-[0.9rem] text-ink-soft">
          <strong className="text-ink">¿Primera vez?</strong> Su despacho se abre solo al entrar con Google:{' '}
          <strong className="text-marca-texto">{datos.dias_prueba} días gratis</strong>, sin tarjeta.
        </p>
      )}
    </form>
  )
}

function CrearAdmin({ datos, alEntrar }: { datos: DatosEntrada; alEntrar: (p: Perfil) => void }) {
  const [f, setF] = useState({ nombre: '', usuario: '', clave: '', clave2: '', codigo: '' })
  const [error, setError] = useState(datos.falta_codigo ? 'Falta la variable CODIGO_INSTALACION en el servidor para crear el administrador.' : '')
  const [creando, setCreando] = useState(false)
  const cambiar = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })

  async function crear(e: FormEvent) {
    e.preventDefault()
    setCreando(true)
    setError('')
    try {
      alEntrar(await api.post<Perfil>('/api/crear-admin', f))
    } catch (ex) {
      setError((ex as ErrorApi).message)
      setCreando(false)
    }
  }

  return (
    <form onSubmit={crear} className="flex flex-col gap-4">
      <Encabezado titulo="Crear administrador" sub="Primera vez: cree la cuenta principal del sistema." />
      <Campo id="nombre" etiqueta="Nombre completo" autoComplete="name" value={f.nombre} onChange={cambiar('nombre')} />
      <Campo id="usuario" etiqueta="Usuario" autoComplete="username" value={f.usuario} onChange={cambiar('usuario')} />
      <Campo id="clave" etiqueta="Contraseña" clave autoComplete="new-password" value={f.clave} onChange={cambiar('clave')} />
      <Campo id="clave2" etiqueta="Repita la contraseña" clave autoComplete="new-password" value={f.clave2} onChange={cambiar('clave2')} />
      {datos.pide_codigo && (
        <Campo id="codigo" etiqueta="Código de instalación" clave value={f.codigo} onChange={cambiar('codigo')} />
      )}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      <Button type="submit" size="grande" disabled={creando} className="h-12 bg-panel text-sobre-panel hover:bg-panel/90">
        {creando && <Loader2 className="animate-spin" />}
        {creando ? 'Creando la cuenta…' : 'Crear y entrar'}
      </Button>
    </form>
  )
}
