import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Loader2 } from 'lucide-react'
import { Logo } from '@/components/logo'
import { Papiniano } from '@/components/papiniano'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ErrorApi } from '@/lib/api'
import type { Entrada as DatosEntrada, Perfil } from '@/lib/tipos'
import { cn } from '@/lib/utils'

// En el plan gratis de Render el servidor se duerme: la primera entrada del día puede tardar hasta un minuto
const AVISO_LENTO_MS = 4000
const REINTENTOS = 10
const ESPERA_REINTENTO_MS = 3000

/**
 * La entrada (/entrar): Google y usuario/contraseña. La primera vez del sistema, crear el administrador.
 * Se llega desde «Entrar» o «Empiece gratis» de la página pública.
 */
export default function Entrada({ alEntrar }: { alEntrar: (p: Perfil) => void }) {
  const [datos, setDatos] = useState<DatosEntrada | null>(null)
  // si Google no dejó entrar, vuelve con ?error=…; se muestra y se limpia la dirección
  const [error, setError] = useState(() => new URLSearchParams(window.location.search).get('error') ?? '')
  const [lento, setLento] = useState(false)

  useEffect(() => {
    if (window.location.search) window.history.replaceState(null, '', '/entrar')
    let vigente = true
    const aviso = setTimeout(() => setLento(true), AVISO_LENTO_MS)
    // si el servidor está despertando puede fallar las primeras veces: se reintenta solo antes de mostrar el error
    const pedir = (quedan: number) =>
      api
        .get<DatosEntrada>('/api/entrada')
        .then((d) => {
          if (vigente) setDatos(d)
        })
        .catch((e: ErrorApi) => {
          if (!vigente) return
          if (quedan > 0) setTimeout(() => vigente && void pedir(quedan - 1), ESPERA_REINTENTO_MS)
          else setError(e.message)
        })
    pedir(REINTENTOS)
    return () => {
      vigente = false
      clearTimeout(aviso)
    }
  }, [])

  return (
    <div className="grid min-h-dvh grid-rows-[auto_1fr] bg-background text-ink lg:grid-cols-[1fr_1.1fr] lg:grid-rows-1">
      {/* la foto: en el celular, una franja arriba; en pantallas grandes, toda la izquierda */}
      {/* en el celular la franja es baja, para que «Entrar» quede en la primera pantalla */}
      <aside className="relative flex h-[270px] flex-col justify-between overflow-hidden bg-panel px-5 pt-3 pb-5 text-sobre-panel md:px-10 lg:h-auto lg:p-12">
        {/* una abogada en su escritorio, con la PC y el expediente (Unsplash, de ergonofis; libre de uso) */}
        <img
          src="/entrada.webp"
          alt=""
          width={1100}
          height={1300}
          fetchPriority="high"
          className="entrada-foto absolute inset-0 size-full object-cover"
        />
        <div className="entrada-tono absolute inset-0" />
        <div className="entrada-sombra absolute inset-0" />
        <div className="relative flex items-center justify-between">
          <Logo enPanel />
          <VolverAlInicio className="text-nav hover:text-sobre-panel lg:hidden" />
        </div>
        <div className="relative">
          <BurbujaPapiniano />
          <h2 className="font-heading text-[1.5rem] leading-[1.12] font-medium lg:text-[2.5rem]">
            Su despacho,<br />listo para trabajar.
          </h2>
          <p className="mt-3.5 hidden max-w-[30rem] text-[1.1rem] leading-relaxed text-nav lg:block">
            Papiniano trabaja a su lado: busca las sentencias, cita las leyes y le redacta el escrito.
          </p>
          <p className="mt-9 hidden text-[0.9rem] text-nav-sub lg:block">Hecho en República Dominicana · Ley 172-13</p>
        </div>
      </aside>

      <main className="flex flex-col px-5 pt-6 pb-6 md:px-10 lg:py-6">
        <div className="hidden justify-end lg:flex">
          <VolverAlInicio className="text-ink-soft hover:text-marca-texto" />
        </div>
        <div className="flex flex-1 items-start justify-center pb-8 lg:items-center lg:py-10">
          <div className="w-full max-w-[420px]">
            {datos ? (
              datos.primera_vez ? (
                <CrearAdmin datos={datos} alEntrar={alEntrar} />
              ) : (
                <Entrar datos={datos} alEntrar={alEntrar} errorInicial={error} />
              )
            ) : error ? (
              <p className="text-sm text-destructive" role="alert">{error}</p>
            ) : (
              <div className="flex items-start gap-3 text-ink-soft" role="status">
                <Loader2 className="mt-0.5 size-5 shrink-0 animate-spin" />
                {lento ? (
                  <div>
                    <p className="text-ink">Despertando el servidor…</p>
                    <p className="text-[0.9rem]">La primera entrada del día puede tardar hasta un minuto.</p>
                  </div>
                ) : (
                  'Un momento…'
                )}
              </div>
            )}
          </div>
        </div>
        <p className="text-center text-[0.85rem] text-ink-soft">
          Al entrar acepta los <Link to="/terminos" className="text-marca-texto hover:underline">términos de servicio</Link> y
          la <Link to="/privacidad" className="text-marca-texto hover:underline">política de privacidad</Link>.
        </p>
      </main>
    </div>
  )
}

/**
 * En el celular va sobre la foto; en pantallas grandes, arriba del formulario. Alto de 44 px para el dedo.
 * En los celulares angostos dice solo «Inicio», para que no se parta en dos líneas junto al logo
 */
function VolverAlInicio({ className }: { className: string }) {
  return (
    <Link to="/" className={cn('-mr-2 inline-flex min-h-11 items-center gap-1.5 px-2 text-[0.95rem] whitespace-nowrap', className)}>
      <ArrowLeft className="size-4" />
      <span className="sm:hidden">Inicio</span>
      <span className="hidden sm:inline">Volver al inicio</span>
    </Link>
  )
}

/** Papiniano en burbuja de chat sobre la foto: primero «escribiendo…» y luego el mensaje (ilustración) */
function BurbujaPapiniano() {
  const [listo, setListo] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)

  useEffect(() => {
    if (listo) return
    const t = setTimeout(() => setListo(true), 2000)
    return () => clearTimeout(t)
  }, [listo])

  return (
    // va justo encima de la frase, en el mismo bloque, para que nunca la tape en las laptops de pantalla baja;
    // en el celular, sin camafeo (ya está el del logo)
    <div aria-hidden="true" className="mb-4 ml-3 flex max-w-[310px] items-end gap-4 lg:mb-9 lg:ml-0 lg:max-w-[370px]">
      <Papiniano className="hidden size-[38px] drop-shadow-[0_6px_12px_rgb(0_0_0/0.45)] lg:block" decorativo />
      <div className="burbuja-papiniano bg-sobre-panel px-3.5 pt-2 pb-2.5 text-[0.88rem] leading-snug text-ink lg:text-[0.95rem]">
        <b className="block font-heading text-[0.82rem] font-medium text-marca-texto">Papiniano</b>
        {listo ? (
          <span className="mensaje-llega block">
            Listo, le redacté la instancia. Faltan los datos del cliente.
            <small className="mt-0.5 block text-right text-[0.7rem] text-pista">ahora</small>
          </span>
        ) : (
          <span className="escribiendo-puntos inline-flex gap-1 pt-1.5 pb-1"><i /><i /><i /></span>
        )}
      </div>
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
        {/* fondo blanco y borde marcado: que se vea bien dónde se escribe */}
        <Input
          id={id}
          type={clave && !ver ? 'password' : 'text'}
          className="h-12 border-pista/80 bg-papel px-3.5 text-base md:text-base"
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
