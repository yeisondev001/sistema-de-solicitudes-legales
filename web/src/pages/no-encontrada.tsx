import { Link, useLocation } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Papiniano } from '@/components/papiniano'
import { Antetitulo, CabeceraPublica, PiePublico } from '@/components/publico'
import { NOMBRE_APP } from '@/lib/tema'
import { useTitulo } from '@/lib/titulo'

/**
 * La página 404: una dirección que no existe. El servidor ya la manda con el código 404 y «noindex» (servidor.pantallas),
 * así Google la descarta en vez de guardarla como página; aquí solo se ayuda a la persona a seguir: la dirección que
 * escribió y los enlaces que más se buscan. Sin sesión va con la cabecera pública; dentro de la app, con el menú.
 */

// [texto, dirección, es un ancla de la portada]
const PUBLICAS: [string, string, boolean][] = [
  ['Calculadora de prestaciones laborales', '/calculadora-prestaciones-laborales', false],
  ['Planes y precios', '/#planes', true],
  ['Preguntas frecuentes', '/#preguntas', true],
  ['Contacto', '/contacto', false],
]
const DE_LA_APP: [string, string, boolean][] = [
  ['Pregúntele a Papiniano', '/papiniano', false],
  ['Expedientes', '/expedientes', false],
  ['Agenda', '/agenda', false],
  ['Biblioteca', '/biblioteca', false],
]

export default function NoEncontrada({ dentro = false }: { dentro?: boolean }) {
  useTitulo(`Página no encontrada · ${NOMBRE_APP}`)
  const { pathname } = useLocation()
  const enlaces = dentro ? DE_LA_APP : PUBLICAS

  const contenido = (
    <div className="mx-auto flex max-w-[640px] flex-col items-center px-5 py-14 text-center md:py-24">
      <Papiniano decorativo className="size-20" />
      <div className="mt-6 space-y-3">
        <Antetitulo>ERROR 404</Antetitulo>
        <h1 className="font-heading text-[2.2rem] leading-tight font-medium md:text-[2.6rem]">No encontramos esta página</h1>
        <p className="text-[1.08rem] leading-relaxed text-ink-soft">
          La dirección <code className="rounded bg-papel px-1.5 py-0.5 text-[0.95rem] break-all text-ink">{pathname}</code> no
          existe en {NOMBRE_APP}. Puede que esté mal escrita o que la página se haya movido.
        </p>
      </div>
      <Link
        to="/"
        className="mt-8 rounded-lg bg-boton px-6 py-3.5 text-[1.05rem] font-bold text-sobre-boton hover:bg-boton/90"
      >
        {dentro ? 'Ir al Escritorio' : 'Ir al inicio'}
      </Link>
      <nav aria-label="Páginas que le pueden servir" className="mt-10 w-full border-t border-papel-borde pt-8">
        <h2 className="text-[0.85rem] font-bold tracking-wide text-ink-soft uppercase">O vaya a</h2>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {enlaces.map(([texto, a, ancla]) => {
            const clase =
              'flex h-full items-center justify-between gap-3 rounded-lg border border-papel-borde bg-card px-4 py-3 text-left font-semibold text-ink hover:border-marca hover:text-marca-texto'
            const flecha = <ArrowRight className="size-4 shrink-0" aria-hidden />
            return (
              <li key={a}>
                {ancla ? (
                  <a href={a} className={clase}>{texto}{flecha}</a>
                ) : (
                  <Link to={a} className={clase}>{texto}{flecha}</Link>
                )}
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )

  // dentro de la app ya hay un <main> (components/oficina.tsx)
  if (dentro) return contenido
  return (
    <div className="min-h-dvh bg-background text-ink">
      <CabeceraPublica />
      <main>{contenido}</main>
      <PiePublico />
    </div>
  )
}
