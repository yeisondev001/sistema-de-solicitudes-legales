import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { Oficina } from '@/components/oficina'
import { api, SESION_TERMINADA } from '@/lib/api'
import { ContextoSesion, type Sesion } from '@/lib/sesion'
import { aplicarColores } from '@/lib/tema'
import type { Perfil } from '@/lib/tipos'
import Asistente from '@/pages/asistente'
import Biblioteca from '@/pages/biblioteca'
import Entrada from '@/pages/entrada'
import Escritorio from '@/pages/escritorio'
import Pronto from '@/pages/pronto'

export default function App() {
  // undefined: todavía se está preguntando al servidor si hay sesión
  const [perfil, setPerfil] = useState<Perfil | null | undefined>(undefined)
  const navegar = useNavigate()

  const refrescar = useCallback(() => {
    api.get<Perfil>('/api/sesion').then(setPerfil).catch(() => setPerfil(null))
  }, [])

  useEffect(refrescar, [refrescar])

  // el tema de la persona por dentro; por fuera, la marca
  useEffect(() => aplicarColores(perfil?.colores), [perfil])

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

  if (!sesion)
    return (
      <Entrada
        alEntrar={(p) => {
          setPerfil(p)
          navegar('/', { replace: true })
        }}
      />
    )

  return (
    <ContextoSesion.Provider value={sesion}>
      <Routes>
        <Route element={<Oficina />}>
          <Route index element={<Escritorio />} />
          <Route path="asistente" element={<Asistente />} />
          <Route path="asistente/:id" element={<Asistente />} />
          <Route path="biblioteca" element={<Biblioteca />} />
          <Route path="redaccion" element={<Pronto sala="redaccion" />} />
          <Route path="expedientes" element={<Pronto sala="expedientes" />} />
          <Route path="agenda" element={<Pronto sala="agenda" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ContextoSesion.Provider>
  )
}
