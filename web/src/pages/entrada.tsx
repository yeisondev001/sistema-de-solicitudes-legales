import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CalendarDays, Eye, EyeOff, FolderClosed, LibraryBig, Loader2, MessageCircle, PenLine, type LucideIcon,
} from 'lucide-react'
import { Antetitulo, CabeceraPublica, PiePublico } from '@/components/publico'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ErrorApi } from '@/lib/api'
import type { Entrada as DatosEntrada, Perfil } from '@/lib/tipos'
import { cn } from '@/lib/utils'

const SALAS: { icono: LucideIcon; nombre: string; texto: string; pronto?: boolean }[] = [
  {
    icono: MessageCircle,
    nombre: 'Asistente',
    texto: 'Su pasante. Le pregunta como a un colega y le responde con la jurisprudencia, la ley que aplica y su análisis, cada cosa citada. También saca las prestaciones laborales con las reglas del Código de Trabajo.',
  },
  {
    icono: LibraryBig,
    nombre: 'Biblioteca',
    texto: 'El Boletín Judicial, los códigos, las leyes y los documentos que usted sube. Abre la página del PDF ahí mismo.',
  },
  {
    icono: FolderClosed,
    nombre: 'Expedientes',
    texto: 'Cada cliente con sus documentos, sus conversaciones con el asistente, sus escritos y sus plazos, en una carpeta.',
    pronto: true,
  },
  {
    icono: PenLine,
    nombre: 'Redacción',
    texto: 'Sus modelos de escritos y solicitudes, listos en Word o PDF.',
    pronto: true,
  },
  {
    icono: CalendarDays,
    nombre: 'Agenda',
    texto: 'Audiencias y vencimientos de todos sus expedientes. El escritorio le avisa lo que vence esta semana.',
    pronto: true,
  },
]

// Los precios todavía no están decididos: se cambian aquí
const PLANES = [
  {
    nombre: 'Prueba', precio: 'Gratis', periodo: (dias: number) => `${dias} días`,
    puntos: ['20 consultas por día al asistente', 'Toda la biblioteca', 'Sin tarjeta'], boton: 'Empezar prueba',
  },
  {
    nombre: 'Abogado', precio: '[PRECIO]', periodo: () => 'al mes', destacado: true,
    puntos: ['Asistente sin límite diario', 'Sus documentos en el buscador', 'Expedientes y agenda, cuando estén listos'],
    boton: 'Elegir plan',
  },
  {
    nombre: 'Despacho', precio: '[PRECIO]', periodo: () => 'al mes',
    puntos: ['Todo lo del plan Abogado', 'Varios abogados y asistentes', 'Expedientes compartidos'], boton: 'Hablar con nosotros',
  },
]

/**
 * La recepción: la página pública (qué es, qué hay adentro, cómo trabaja el asistente y los planes)
 * con la entrada a la vista, como en el diseño (lienzo «Despacho jurídico digital», tablero 1).
 */
export default function Entrada({ alEntrar }: { alEntrar: (p: Perfil) => void }) {
  const [datos, setDatos] = useState<DatosEntrada | null>(null)
  // si Google no dejó entrar, vuelve con ?error=…; se muestra y se limpia la dirección
  const [error, setError] = useState(() => new URLSearchParams(window.location.search).get('error') ?? '')
  const tarjeta = useRef<HTMLDivElement>(null)
  const navegar = useNavigate()

  useEffect(() => {
    if (window.location.search) window.history.replaceState(null, '', '/')
    api.get<DatosEntrada>('/api/entrada').then(setDatos).catch((e: ErrorApi) => setError(e.message))
  }, [])

  // «Entrar» y «Empezar prueba» llevan a la tarjeta de entrada (con Google, la prueba empieza ahí mismo)
  function irAEntrar() {
    tarjeta.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setTimeout(() => tarjeta.current?.querySelector<HTMLInputElement>('input')?.focus({ preventScroll: true }), 400)
  }
  const empezar = () => (datos?.google ? window.location.assign('/api/google') : irAEntrar())
  const dias = datos?.dias_prueba ?? 14

  return (
    <div className="min-h-dvh bg-background text-ink">
      <CabeceraPublica enInicio alEntrar={irAEntrar} />

      <main>
        <section className="mx-auto grid max-w-[1240px] items-center gap-10 px-5 py-10 md:grid-cols-[7fr_5fr] md:gap-14 md:px-6 md:py-[72px]">
          <div className="space-y-6">
            <Antetitulo>PARA ABOGADOS DE REPÚBLICA DOMINICANA</Antetitulo>
            <h1 className="font-heading text-[2.6rem] leading-[1.08] font-medium tracking-tight md:text-[3.6rem]">
              Todo su trabajo, en una sola oficina.
            </h1>
            <p className="max-w-[36rem] text-lg leading-relaxed text-ink-soft md:text-[1.2rem]">
              Investigue con las sentencias de la Suprema Corte, consulte los códigos y las leyes y guarde sus documentos
              sin salir de aquí. Su asistente lee por usted y le muestra la página exacta de cada cita.
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <Button size="grande" className="h-[3.25rem] px-6 text-base" onClick={empezar}>
                Probar {dias} días gratis
              </Button>
              <a href="#asistente" className="px-1.5 py-3 font-bold text-marca-texto hover:underline">Ver cómo funciona</a>
            </div>
            <ul className="flex flex-wrap gap-x-7 gap-y-2.5 border-t border-papel-borde pt-5 text-[0.95rem] text-ink-soft">
              <li><strong className="text-ink">Sentencias</strong> de la Suprema Corte</li>
              <li><strong className="text-ink">Códigos y leyes</strong> por artículo</li>
              <li><strong className="text-ink">Sus documentos</strong> en el mismo buscador</li>
            </ul>
          </div>
          <div
            id="entrar"
            ref={tarjeta}
            className="mx-auto w-full max-w-[460px] scroll-mt-6 rounded-2xl border border-papel-borde bg-card p-6 shadow-[0_18px_44px_-12px_color-mix(in_oklab,var(--t-ink)_14%,transparent)] md:p-8"
          >
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

        <section id="salas" className="scroll-mt-4 border-y border-papel-borde bg-card">
          <div className="mx-auto max-w-[1240px] space-y-10 px-5 py-16 md:px-6 md:py-20">
            <div className="max-w-[700px] space-y-2.5">
              <Antetitulo>QUÉ HAY ADENTRO</Antetitulo>
              <h2 className="font-heading text-[2rem] leading-tight font-medium md:text-[2.6rem]">Cada sala de su oficina, a un clic.</h2>
            </div>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {SALAS.map(({ icono: Icono, nombre, texto, pronto }) => (
                <div key={nombre} className="space-y-2.5 rounded-xl border border-papel-borde bg-background p-6">
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex size-[46px] items-center justify-center rounded-[9px] bg-panel text-[#F1E8DA]">
                      <Icono className="size-[22px]" />
                    </span>
                    {pronto && <span className="rounded-full bg-aviso px-2.5 py-0.5 text-[0.8rem] font-bold text-aviso-texto">Pronto</span>}
                  </div>
                  <h3 className="font-heading text-[1.4rem] font-semibold">{nombre}</h3>
                  <p className="leading-relaxed text-ink-soft">{texto}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="asistente" className="mx-auto grid max-w-[1240px] scroll-mt-4 items-center gap-12 px-5 py-16 md:px-6 md:py-20 lg:grid-cols-2">
          <div className="space-y-6">
            <Antetitulo>CÓMO TRABAJA EL ASISTENTE</Antetitulo>
            <h2 className="font-heading text-[2rem] leading-tight font-medium md:text-[2.6rem]">
              Pregunte como a un colega. Verifique cada cita.
            </h2>
            <ol className="space-y-4">
              {[
                ['Usted pregunta', 'en lenguaje normal, o por número de sentencia o expediente.'],
                ['Él busca', 'por palabras y por significado en las sentencias, los códigos, las leyes y sus documentos.'],
                ['Le responde', 'con lo que dice la jurisprudencia, la ley y su análisis. Cada cita abre la página del PDF oficial.'],
              ].map(([fuerte, resto], i) => (
                <li key={fuerte} className="flex items-start gap-3.5">
                  <span className="flex size-[34px] shrink-0 items-center justify-center rounded-full bg-boton font-bold text-sobre-boton">{i + 1}</span>
                  <span className="pt-1 leading-relaxed text-ink-soft"><strong className="text-ink">{fuerte}</strong> {resto}</span>
                </li>
              ))}
            </ol>
          </div>
          {/* una conversación de ejemplo, como se ve adentro */}
          <div aria-hidden="true" className="space-y-3.5 rounded-2xl border border-papel-borde bg-card p-6 shadow-[0_12px_30px_-10px_color-mix(in_oklab,var(--t-ink)_14%,transparent)]">
            <p className="ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-panel px-4 py-3 text-sobre-panel">
              ¿Qué pasa si se aprobó un deslinde sin citar a los colindantes?
            </p>
            <div className="flex flex-wrap gap-2 text-[0.8rem] text-ink-soft">
              {['Buscó en las sentencias y las leyes', 'Leyó 3 sentencias', '1 reglamento'].map((t) => (
                <span key={t} className="rounded-full bg-[#F1E6DE] px-3 py-1">{t}</span>
              ))}
            </div>
            <div className="space-y-2.5 rounded-2xl rounded-tl-sm border border-papel-borde bg-background p-5 font-heading text-[1.05rem] leading-relaxed">
              <p>
                La falta de citación de los colindantes puede llevar a anular el deslinde, porque afecta su derecho de
                defensa{' '}
                {[1, 2].map((n) => (
                  <span key={n} className="ml-1 rounded bg-[#F1E6DE] px-1.5 py-px font-sans text-[0.8rem] font-bold text-roble">{n}</span>
                ))}
              </p>
              <p className="font-sans text-[0.8rem] font-bold tracking-[0.12em] text-marca-texto">LO QUE DICE LA JURISPRUDENCIA · ANÁLISIS</p>
              <p className="text-ink-soft">El criterio de las sentencias, cómo aplica a su caso, los argumentos y los riesgos.</p>
            </div>
          </div>
        </section>

        <section id="planes" className="scroll-mt-4 bg-panel text-sobre-panel">
          <div className="mx-auto max-w-[1240px] space-y-10 px-5 py-16 md:px-6 md:py-20">
            <div className="max-w-[700px] space-y-2.5">
              <Antetitulo claro>PLANES</Antetitulo>
              <h2 className="font-heading text-[2rem] leading-tight font-medium md:text-[2.6rem]">Empiece gratis. Pague cuando le sirva.</h2>
            </div>
            <div className="grid gap-5 md:grid-cols-3">
              {PLANES.map((p) => (
                <div
                  key={p.nombre}
                  className={cn(
                    'flex flex-col gap-3.5 rounded-2xl p-7',
                    p.destacado ? 'border-2 border-[#F1E8DA] bg-[#4A3527]' : 'border border-[#6B5442]',
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-heading text-[1.75rem] font-medium">{p.nombre}</h3>
                    {p.destacado && (
                      <span className="shrink-0 rounded-full bg-[#F1E8DA] px-3 py-1 text-[0.8rem] font-bold whitespace-nowrap text-[#7A1F2B]">Recomendado</span>
                    )}
                  </div>
                  <p className="text-[2.1rem] font-bold">
                    {p.precio} <span className="text-base font-normal text-[#E2C9A8]">{p.periodo(dias)}</span>
                  </p>
                  <ul className="list-disc space-y-2 pl-5 text-[#F1E8DA]">
                    {p.puntos.map((x) => <li key={x}>{x}</li>)}
                  </ul>
                  <button
                    type="button"
                    onClick={p.nombre === 'Despacho' ? () => navegar('/contacto') : empezar}
                    className={cn(
                      'mt-auto rounded-lg border border-[#F1E8DA] px-4 py-3.5 font-bold',
                      p.destacado ? 'bg-[#7A1F2B] text-white hover:bg-[#8C2A36]' : 'text-[#F8F4EC] hover:bg-white/10',
                    )}
                  >
                    {p.boton}
                  </button>
                </div>
              ))}
            </div>
            <p className="text-[0.95rem] text-[#E2C9A8]">
              Pago seguro con tarjeta a través de Lemon Squeezy. Cancele cuando quiera desde su cuenta.
            </p>
          </div>
        </section>
      </main>

      <PiePublico />
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
