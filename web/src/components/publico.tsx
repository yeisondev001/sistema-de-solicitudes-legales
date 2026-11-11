import { Link } from 'react-router-dom'
import { Logo } from '@/components/logo'

/** Arriba de las páginas públicas: el logo y el menú. En las páginas legales, el menú lleva al inicio. */
export function CabeceraPublica({ enInicio = false, alEntrar }: { enInicio?: boolean; alEntrar?: () => void }) {
  const a = (ancla: string) => (enInicio ? ancla : `/${ancla}`)
  return (
    <header className="border-b border-papel-borde bg-background">
      <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-4 px-5 py-4 md:px-6">
        <Link to="/" aria-label="Inicio">
          <Logo />
        </Link>
        <nav aria-label="Principal" className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[0.95rem]">
          <a href={a('#salas')} className="hidden text-ink hover:text-marca-texto md:inline">Qué hay adentro</a>
          <a href={a('#asistente')} className="hidden text-ink hover:text-marca-texto md:inline">Cómo trabaja el asistente</a>
          <a href={a('#planes')} className="text-ink hover:text-marca-texto">Planes</a>
          {enInicio ? (
            <button type="button" onClick={alEntrar} className="rounded-lg bg-boton px-5 py-3 font-bold text-sobre-boton hover:bg-boton/90">
              Entrar
            </button>
          ) : (
            <Link to="/" className="rounded-lg bg-boton px-5 py-3 font-bold text-sobre-boton hover:bg-boton/90">
              Entrar
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}

export function PiePublico() {
  return (
    <footer className="mx-auto flex max-w-[1240px] flex-wrap justify-between gap-4 px-5 pt-8 pb-12 text-[0.92rem] text-ink-soft md:px-6">
      <span>Herramienta de apoyo: no sustituye el criterio del abogado. Datos protegidos según la Ley 172-13.</span>
      <nav aria-label="Legal" className="flex flex-wrap gap-x-5 gap-y-2">
        <Link to="/terminos" className="text-marca-texto hover:underline">Términos de servicio</Link>
        <Link to="/privacidad" className="text-marca-texto hover:underline">Privacidad</Link>
        <Link to="/reembolso" className="text-marca-texto hover:underline">Política de reembolso</Link>
        <Link to="/contacto" className="text-marca-texto hover:underline">Contacto</Link>
      </nav>
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
