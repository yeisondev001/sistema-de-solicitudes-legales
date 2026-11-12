import { useEffect, useState } from 'react'

/** Si la ventana tiene al menos ese ancho (y se actualiza al cambiarla de tamaño) */
export function useAncho(minimo: number) {
  const consulta = `(min-width: ${minimo}px)`
  const [ancha, setAncha] = useState(() => window.matchMedia(consulta).matches)
  useEffect(() => {
    const m = window.matchMedia(consulta)
    const cambiar = () => setAncha(m.matches)
    m.addEventListener('change', cambiar)
    return () => m.removeEventListener('change', cambiar)
  }, [consulta])
  return ancha
}
