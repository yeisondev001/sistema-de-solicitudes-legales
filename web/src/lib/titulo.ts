import { useEffect } from 'react'

/** Pone el título de la pestaña (el que Google muestra) mientras la página está abierta, y al salir deja el de antes */
export function useTitulo(titulo: string) {
  useEffect(() => {
    const antes = document.title
    document.title = titulo
    return () => {
      document.title = antes
    }
  }, [titulo])
}
