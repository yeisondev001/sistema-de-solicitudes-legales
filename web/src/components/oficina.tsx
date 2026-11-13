import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Building2, CalendarDays, ChevronsUpDown, FolderClosed, House, LibraryBig, LogOut, Menu, Palette, PenLine, Users,
} from 'lucide-react'
import { Apariencia } from '@/components/apariencia'
import { Logo } from '@/components/logo'
import { NOMBRE_ASISTENTE, Papiniano } from '@/components/papiniano'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Progress } from '@/components/ui/progress'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useSesion } from '@/lib/sesion'
import { iniciales, NOMBRE_APP } from '@/lib/tema'
import { cn } from '@/lib/utils'

interface Sala {
  ruta: string
  nombre: string
  icono: React.ComponentType<{ className?: string }>
  pronto?: boolean
}

/** Las salas del despacho. Las que todavía no existen salen con «Pronto». */
function useSalas(): Sala[] {
  const { perfil } = useSesion()
  return [
    { ruta: '/', nombre: 'Escritorio', icono: House },
    { ruta: '/papiniano', nombre: NOMBRE_ASISTENTE, icono: Papiniano },
    { ruta: '/biblioteca', nombre: 'Biblioteca', icono: LibraryBig },
    { ruta: '/expedientes', nombre: 'Expedientes', icono: FolderClosed, pronto: true },
    { ruta: '/redaccion', nombre: 'Redacción', icono: PenLine, pronto: !perfil.plantillas },
    { ruta: '/agenda', nombre: 'Agenda', icono: CalendarDays, pronto: true },
  ]
}

function MenuSalas({ alElegir }: { alElegir?: () => void }) {
  const salas = useSalas()
  return (
    <nav aria-label="Salas del despacho" className="flex flex-col gap-1">
      {salas.map(({ ruta, nombre, icono: Icono, pronto }) => (
        <NavLink
          key={ruta}
          to={ruta}
          end={ruta === '/'}
          onClick={alElegir}
          className={({ isActive }) =>
            cn(
              'flex h-11 items-center gap-3 rounded-lg px-3 text-[0.98rem] transition-colors',
              isActive
                ? 'bg-sidebar-primary font-bold text-sidebar-primary-foreground'
                : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
            )
          }
        >
          <Icono className="size-[1.15rem] shrink-0" />
          <span className="flex-1">{nombre}</span>
          {pronto && <span className="text-[0.78rem] italic opacity-80">Pronto</span>}
        </NavLink>
      ))}
    </nav>
  )
}

/** En la prueba gratis: los días que quedan y las consultas de hoy. En el plan Básico, solo las consultas. */
function CajaPrueba() {
  const { perfil } = useSesion()
  const limite = perfil.prueba ?? perfil.basico
  if (!limite) return null
  const { preguntas_hoy, tope } = limite
  return (
    <div className="space-y-2 border-t border-sidebar-border px-2.5 pt-4">
      <p className="text-[0.8rem] font-bold tracking-wide text-nav-sub">{perfil.prueba ? 'PRUEBA GRATIS' : 'PLAN BÁSICO'}</p>
      {perfil.prueba && (
        <p className="font-heading text-xl text-sobre-panel">
          Quedan {perfil.prueba.dias} día{perfil.prueba.dias === 1 ? '' : 's'}
        </p>
      )}
      <Progress
        value={tope ? Math.min(100, (preguntas_hoy / tope) * 100) : 0}
        className="h-1.5 bg-sidebar-accent [&>*]:bg-nav-linea"
        aria-label="Consultas usadas hoy"
      />
      <p className="text-[0.9rem] text-nav-sub">
        {preguntas_hoy} de {tope} consultas hoy
      </p>
    </div>
  )
}

function Cuenta({ abrirApariencia }: { abrirApariencia: () => void }) {
  const { perfil, salir } = useSesion()
  const navegar = useNavigate()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-3 rounded-lg p-2 text-left outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-sobre-panel text-[0.9rem] font-bold text-panel">
          {iniciales(perfil.nombre)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-bold text-sobre-panel">{perfil.nombre}</span>
          <span className="block truncate text-[0.85rem] text-nav-sub">{perfil.oficina?.nombre ?? 'Mi cuenta · Apariencia'}</span>
        </span>
        <ChevronsUpDown className="size-4 text-nav-sub" />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-60">
        <DropdownMenuLabel className="font-normal text-muted-foreground">
          {perfil.email || perfil.usuario}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {perfil.oficina && (
          <DropdownMenuItem onSelect={() => navegar('/oficina')} className="h-10 text-[0.95rem]">
            <Building2 /> Mi oficina
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onSelect={abrirApariencia} className="h-10 text-[0.95rem]">
          <Palette /> Apariencia
        </DropdownMenuItem>
        {perfil.es_admin && (
          <DropdownMenuItem onSelect={() => navegar('/usuarios')} className="h-10 text-[0.95rem]">
            <Users /> Administrar usuarios
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onSelect={salir} className="h-10 text-[0.95rem]">
          <LogOut /> Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function Lateral({ alElegir, abrirApariencia }: { alElegir?: () => void; abrirApariencia: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto bg-sidebar p-4">
      <div className="px-1 pt-1">
        <Logo enPanel />
      </div>
      <MenuSalas alElegir={alElegir} />
      <div className="mt-auto space-y-3">
        <CajaPrueba />
        <Cuenta abrirApariencia={abrirApariencia} />
      </div>
    </div>
  )
}

/** La oficina: el menú de salas a la izquierda (en el celular, en un panel) y la sala abierta. */
export function Oficina() {
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [apariencia, setApariencia] = useState(false)
  const { pathname } = useLocation()
  // Papiniano usa todo el alto para la conversación; las demás salas se desplazan
  const conversacion = pathname.startsWith('/papiniano')
  // cada sala abre desde arriba
  const contenido = useRef<HTMLElement>(null)
  useEffect(() => {
    // con llaves: en los navegadores nuevos scrollTo devuelve una promesa, y un efecto no puede devolver nada
    contenido.current?.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="flex h-dvh flex-col bg-background lg:flex-row">
      <aside className="hidden w-64 shrink-0 lg:block">
        <Lateral abrirApariencia={() => setApariencia(true)} />
      </aside>

      <header className="flex items-center justify-between bg-sidebar px-3 py-2 lg:hidden">
        <Logo enPanel />
        <Sheet open={menuAbierto} onOpenChange={setMenuAbierto}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon-grande" className="text-sobre-panel hover:bg-sidebar-accent hover:text-sobre-panel" aria-label="Abrir el menú">
              <Menu />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[18rem] border-none p-0 [&>button]:text-sobre-panel">
            <SheetTitle className="sr-only">Menú</SheetTitle>
            <SheetDescription className="sr-only">Las salas del despacho y su cuenta</SheetDescription>
            <Lateral
              alElegir={() => setMenuAbierto(false)}
              abrirApariencia={() => {
                setMenuAbierto(false)
                setApariencia(true)
              }}
            />
          </SheetContent>
        </Sheet>
      </header>

      <main ref={contenido} className={cn('min-h-0 min-w-0 flex-1', conversacion ? 'flex flex-col' : 'overflow-y-auto')}>
        <Outlet />
      </main>

      <Apariencia abierta={apariencia} alCambiar={setApariencia} />
    </div>
  )
}

/** Encabezado de cada sala: ruta, título y una línea de qué se hace allí */
export function TituloSala({ titulo, sub, children }: { titulo: string; sub?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="space-y-1">
        <p className="text-[0.8rem] text-pista">{NOMBRE_APP} › {titulo}</p>
        <h1 className="font-heading text-3xl font-medium text-ink md:text-[2.1rem]">{titulo}</h1>
        {sub && <p className="text-[0.95rem] text-ink-soft">{sub}</p>}
      </div>
      {children}
    </div>
  )
}
