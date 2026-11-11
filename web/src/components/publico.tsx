import { Link } from 'react-router-dom'
import { Logo } from '@/components/logo'
import { NOMBRE_APP } from '@/lib/tema'

/** Arriba de las páginas públicas: el logo, el menú y los botones para entrar o empezar. */
export function CabeceraPublica({ conMenu = true }: { conMenu?: boolean }) {
  return (
    <header className="sticky top-0 z-30 border-b border-papel-borde bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1240px] items-center justify-between gap-4 px-5 py-3.5 md:px-6">
        <Link to="/" aria-label="Inicio">
          <Logo />
        </Link>
        {conMenu && (
          <nav aria-label="Principal" className="hidden items-center gap-7 text-[0.95rem] whitespace-nowrap xl:flex">
            <a href="/#fuentes" className="text-ink hover:text-marca-texto">Qué lee</a>
            <a href="/#salas" className="text-ink hover:text-marca-texto">Qué hay adentro</a>
            <a href="/#como" className="text-ink hover:text-marca-texto">Cómo funciona</a>
            <a href="/#planes" className="text-ink hover:text-marca-texto">Planes</a>
            <a href="/#preguntas" className="text-ink hover:text-marca-texto">Preguntas</a>
          </nav>
        )}
        <div className="flex items-center gap-2 whitespace-nowrap sm:gap-3">
          <Link to="/entrar" className="rounded-lg border border-regla px-4 py-2.5 font-bold text-ink hover:border-marca hover:text-marca-texto sm:border-transparent sm:px-3">
            Entrar
          </Link>
          {/* en el celular no cabe: el botón grande está justo debajo */}
          <Link to="/entrar" className="hidden rounded-lg bg-boton px-5 py-2.5 font-bold text-sobre-boton hover:bg-boton/90 sm:inline-block">
            Empiece gratis
          </Link>
        </div>
      </div>
    </header>
  )
}

const ANIO = new Date().getFullYear()

const COLUMNAS: [string, [string, string][]][] = [
  ['Producto', [['Qué lee', '/#fuentes'], ['Qué hay adentro', '/#salas'], ['Cómo funciona', '/#como'], ['Planes', '/#planes']]],
  ['Ayuda', [['Preguntas frecuentes', '/#preguntas'], ['Contacto', '/contacto']]],
  ['Legal', [['Términos de servicio', '/terminos'], ['Privacidad', '/privacidad'], ['Política de reembolso', '/reembolso']]],
]

export function PiePublico() {
  return (
    <footer className="border-t border-papel-borde bg-card">
      <div className="mx-auto grid max-w-[1240px] gap-10 px-5 py-12 md:grid-cols-[1.4fr_repeat(3,1fr)] md:px-6">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-xs text-[0.92rem] text-ink-soft">
            La oficina digital del abogado dominicano. Herramienta de apoyo: no sustituye el criterio del abogado.
          </p>
        </div>
        {COLUMNAS.map(([titulo, enlaces]) => (
          <nav key={titulo} aria-label={titulo} className="space-y-3">
            <h2 className="text-[0.85rem] font-bold tracking-wide text-ink-soft uppercase">{titulo}</h2>
            <ul className="space-y-2">
              {enlaces.map(([texto, a]) => (
                <li key={texto}>
                  {a.startsWith('/#') ? (
                    <a href={a} className="text-ink hover:text-marca-texto">{texto}</a>
                  ) : (
                    <Link to={a} className="text-ink hover:text-marca-texto">{texto}</Link>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-papel-borde">
        <p className="mx-auto max-w-[1240px] px-5 py-5 text-[0.85rem] text-ink-soft md:px-6">
          © {ANIO} {NOMBRE_APP}. Hecho en República Dominicana. Datos protegidos según la Ley 172-13.
        </p>
      </div>
    </footer>
  )
}

/** La línea chica en mayúsculas sobre cada título */
export function Antetitulo({ children, claro = false }: { children: React.ReactNode; claro?: boolean }) {
  return (
    <p className={claro ? 'text-sm font-bold tracking-[0.14em] text-[#E2C9A8]' : 'text-sm font-bold tracking-[0.14em] text-roble'}>
      {children}
    </p>
  )
}
