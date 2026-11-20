import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { api, SESION_TERMINADA } from '@/lib/api'
import { ContextoSesion, type Sesion } from '@/lib/sesion'
import { aplicarColores, aplicarLetra } from '@/lib/tema'
import type { Perfil } from '@/lib/tipos'
import { ArticuloBlog, Blog } from '@/pages/blog'
import Calculadora from '@/pages/calculadora'
import Entrada from '@/pages/entrada'
import Inicio from '@/pages/inicio'
import Legal from '@/pages/legal'
import NoEncontrada from '@/pages/no-encontrada'

// Las pantallas de la app se bajan recién al abrirlas (cada una en su archivo): la página pública, la calculadora y la
// entrada no cargan todo el programa, y así abren más rápido (Google mide esa velocidad).
const Oficina = lazy(() => import('@/components/oficina').then((m) => ({ default: m.Oficina })))
const Agenda = lazy(() => import('@/pages/agenda'))
const Asistente = lazy(() => import('@/pages/asistente'))
const Biblioteca = lazy(() => import('@/pages/biblioteca'))
const Escritorio = lazy(() => import('@/pages/escritorio'))
const Expedientes = lazy(() => import('@/pages/expedientes'))
const MiOficina = lazy(() => import('@/pages/mi-oficina'))
const Modelos = lazy(() => import('@/pages/modelos'))
const Plan = lazy(() => import('@/pages/plan'))
const Redaccion = lazy(() => import('@/pages/redaccion'))
const Redactar = lazy(() => import('@/pages/redactar'))
const Usuarios = lazy(() => import('@/pages/usuarios'))
const Errores = lazy(() => import('@/pages/errores'))

// Las pantallas de la app: sin sesión piden entrar. Son las mismas de servidor.RUTAS_APP (allí no van a Google y
// cualquier otra dirección responde 404): si se agrega una pantalla, agregarla en los dos lados.
const RUTAS_APP = [
  'plan', 'papiniano', 'papiniano/:id', 'modelos', 'redactar', 'biblioteca', 'redaccion', 'redaccion/:clave',
  'usuarios', 'errores', 'oficina', 'expedientes', 'expedientes/:id', 'agenda',
]

export default function App() {
  // undefined: todavía se está preguntando al servidor si hay sesión
  const [perfil, setPerfil] = useState<Perfil | null | undefined>(undefined)
  const navegar = useNavigate()

  const refrescar = useCallback(() => {
    api.get<Perfil>('/api/sesion').then(setPerfil).catch(() => setPerfil(null))
  }, [])

  useEffect(refrescar, [refrescar])

  // llegó desde «Elegir plan» de la página pública: al entrar lo lleva directo a pagar ese plan
  useEffect(() => {
    if (!perfil) return
    try {
      const guardado = sessionStorage.getItem('plan_elegido')
      if (!guardado) return
      sessionStorage.removeItem('plan_elegido')
      const { plan, ciclo } = JSON.parse(guardado) as { plan: string; ciclo: string }
      navegar(`/plan?elegir=${encodeURIComponent(plan)}&ciclo=${encodeURIComponent(ciclo)}`, { replace: true })
    } catch {
      // sin almacenamiento: queda en el escritorio y elige en «Mi plan»
    }
  }, [perfil, navegar])

  // marcó «Quiero recibir novedades y promociones» al entrar: se guarda en su cuenta, con la fecha
  useEffect(() => {
    if (!perfil) return
    try {
      if (sessionStorage.getItem('acepta_promociones') !== '1') return
      sessionStorage.removeItem('acepta_promociones')
    } catch {
      return
    }
    if (perfil.promociones) return
    api.post<Perfil>('/api/promociones', { acepta: true }).then(setPerfil).catch(() => {})
  }, [perfil])

  // el tema de la persona por dentro; por fuera, la marca
  useEffect(() => {
    aplicarColores(perfil?.colores)
    aplicarLetra(perfil?.letra)
  }, [perfil])

  useEffect(() => {
    const terminar = () => setPerfil(null)
    window.addEventListener(SESION_TERMINADA, terminar)
    return () => window.removeEventListener(SESION_TERMINADA, terminar)
  }, [])

  const sesion = useMemo<Sesion | null>(
    () =>
      perfil
        ? {
            perfil,
            refrescar,
            cambiarPerfil: setPerfil,
            salir: () => {
              api.post('/api/salir').finally(() => {
                setPerfil(null)
                navegar('/', { replace: true })
              })
            },
          }
        : null,
    [perfil, refrescar, navegar],
  )

  if (perfil === undefined) return <div className="min-h-dvh bg-background" aria-busy="true" />

  // las páginas legales, la calculadora de prestaciones y el blog se ven con o sin sesión
  const legales = [
    ...(['terminos', 'privacidad', 'reembolso', 'contacto'] as const).map((p) => (
      <Route key={p} path={p} element={<Legal pagina={p} />} />
    )),
    <Route key="calculadora" path="calculadora-prestaciones-laborales" element={<Calculadora />} />,
    <Route key="blog" path="blog" element={<Blog />} />,
    <Route key="articulo" path="blog/:slug" element={<ArticuloBlog />} />,
  ]

  // sin sesión: la página pública en /, la entrada en /entrar, las pantallas de la app piden entrar y cualquier otra
  // dirección es la página 404
  if (!sesion)
    return (
      <Routes>
        {legales}
        <Route index element={<Inicio />} />
        <Route
          path="entrar"
          element={
            <Entrada
              alEntrar={(p) => {
                setPerfil(p)
                navegar('/', { replace: true })
              }}
            />
          }
        />
        {RUTAS_APP.map((p) => (
          <Route key={p} path={p} element={<Navigate to="/entrar" replace />} />
        ))}
        <Route path="*" element={<NoEncontrada />} />
      </Routes>
    )

  // la prueba terminó o el plan venció: solo la pantalla de pago (todo lo demás pediría un plan activo)
  if (sesion.perfil.por_pagar)
    return (
      <ContextoSesion.Provider value={sesion}>
        <Suspense fallback={<div className="min-h-dvh bg-background" aria-busy="true" />}>
          <Routes>
            {legales}
            <Route path="*" element={<Plan soloPagar />} />
          </Routes>
        </Suspense>
      </ContextoSesion.Provider>
    )

  return (
    <ContextoSesion.Provider value={sesion}>
      <Suspense fallback={<div className="min-h-dvh bg-background" aria-busy="true" />}>
      <Routes>
        {legales}
        <Route element={<Oficina />}>
          <Route path="plan" element={<Plan />} />
          <Route index element={<Escritorio />} />
          <Route path="papiniano" element={<Asistente />} />
          <Route path="papiniano/:id" element={<Asistente />} />
          <Route path="modelos" element={<Modelos />} />
          <Route path="redactar" element={<Redactar />} />
          <Route path="biblioteca" element={<Biblioteca />} />
          {sesion.perfil.plantillas ? (
            <>
              <Route path="redaccion" element={<Redaccion />} />
              <Route path="redaccion/:clave" element={<Redaccion />} />
            </>
          ) : (
            <Route path="redaccion/*" element={<Navigate to="/" replace />} />
          )}
          {/* lo del administrador; a los demás los lleva al Escritorio */}
          {sesion.perfil.es_admin ? (
            <>
              <Route path="usuarios" element={<Usuarios />} />
              <Route path="errores" element={<Errores />} />
            </>
          ) : (
            <>
              <Route path="usuarios" element={<Navigate to="/" replace />} />
              <Route path="errores" element={<Navigate to="/" replace />} />
            </>
          )}
          {/* siempre: al aceptar una invitación se llega aquí antes de que se vuelva a leer la cuenta */}
          <Route path="oficina" element={<MiOficina />} />
          <Route path="expedientes" element={<Expedientes />} />
          <Route path="expedientes/:id" element={<Expedientes />} />
          <Route path="agenda" element={<Agenda />} />
          {/* con sesión, /entrar lleva al Escritorio; lo que no existe es la 404, dentro de la app */}
          <Route path="entrar" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NoEncontrada dentro />} />
        </Route>
      </Routes>
      </Suspense>
    </ContextoSesion.Provider>
  )
}
