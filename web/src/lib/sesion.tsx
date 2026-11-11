import { createContext, useContext } from 'react'
import type { Perfil } from './tipos'

export interface Sesion {
  perfil: Perfil
  /** Vuelve a leer la cuenta (después de una pregunta, para el contador de la prueba) */
  refrescar: () => void
  cambiarPerfil: (perfil: Perfil) => void
  salir: () => void
}

export const ContextoSesion = createContext<Sesion | null>(null)

export function useSesion() {
  const sesion = useContext(ContextoSesion)
  if (!sesion) throw new Error('useSesion fuera de la oficina')
  return sesion
}
