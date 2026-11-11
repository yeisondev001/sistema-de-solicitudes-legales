import type { Colores } from './tipos'

export const NOMBRE_APP = 'Papiniano' // el producto se llama igual que su asistente

/**
 * Pone los colores de un tema (de temas.py) en las variables --t-* de index.css.
 * Sin colores vuelve a la marca, que es la que está escrita en index.css.
 */
export function aplicarColores(colores?: Colores | null) {
  const raiz = document.documentElement
  for (const nombre of [...raiz.style]) if (nombre.startsWith('--t-')) raiz.style.removeProperty(nombre)
  raiz.classList.toggle('dark', Boolean(colores?.oscuro))
  if (!colores) return
  for (const [nombre, valor] of Object.entries(colores)) {
    if (typeof valor === 'string') raiz.style.setProperty(`--t-${nombre.toLowerCase().replaceAll('_', '-')}`, valor)
  }
}

/** Iniciales para el círculo de la cuenta: «Ana Martínez» → «AM» */
export function iniciales(nombre: string) {
  const partes = nombre.trim().split(/\s+/).filter(Boolean)
  return ((partes[0]?.[0] ?? '') + (partes.length > 1 ? partes[partes.length - 1][0] : '')).toUpperCase() || '?'
}
