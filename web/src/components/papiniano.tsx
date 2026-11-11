import { useId } from 'react'
import { cn } from '@/lib/utils'

export const NOMBRE_ASISTENTE = 'Papiniano'

// Los colores de la marca, iguales en todos los temas: el ícono es parte de la identidad, como el logo
const VINO = '#7A1F2B'
const MARFIL = '#F8F4EC'
const ORO = '#E2C29B'
const HOJA = 'M0 0 C1.6 -1.5 4 -1.5 5.6 0 C4 1.5 1.6 1.5 0 0 Z'
const HOJAS: [number, number, number][] = [
  [20.2, 33.5, -80], [20, 27.6, -62], [22, 22.3, -42], [25.8, 18.6, -20], [30.8, 17, 2], [35.6, 17.6, 22],
]

/**
 * Papiniano, el asistente: un busto romano de perfil con corona de laurel y toga.
 * Por Emilio Papiniano (siglo III), el jurista más respetado de Roma.
 */
export function Papiniano({ className, decorativo = false }: { className?: string; decorativo?: boolean }) {
  const recorte = useId()
  return (
    <svg
      viewBox="0 0 64 64"
      className={cn('size-10 shrink-0', className)}
      {...(decorativo ? { 'aria-hidden': true } : { role: 'img', 'aria-label': NOMBRE_ASISTENTE })}
    >
      <circle cx="32" cy="32" r="32" fill={VINO} />
      <circle cx="32" cy="32" r="29.5" fill="none" stroke={ORO} strokeWidth="1" />
      <clipPath id={recorte}>
        <circle cx="32" cy="32" r="29" />
      </clipPath>
      <g clipPath={`url(#${recorte})`}>
        <path
          fill={MARFIL}
          d="M24 45 C20.5 41 18.5 35.5 18.5 29.5 C18.5 20 24.5 14 32.5 14 C39.5 14 43.5 18.5 43.5 24.5 L43.6 26.2 L46.6 31.4 C46.9 32 46.5 32.5 45.9 32.6 L44.2 32.8 L44.6 34.6 L43.6 35.4 L44 37.2 C44.1 39.6 42.6 41 40 41 L37.8 41.3 L38.2 45.5 C44.5 46.8 50 50 52 58 L52 66 L10 66 L10 60 C11.5 52 17 47.2 24 45 Z"
        />
        <g fill="none" stroke={VINO} strokeLinecap="round">
          {/* la toga, el ojo y la oreja */}
          <path strokeWidth="1.6" d="M20 52 C27 50.5 33 52 39 58" />
          <path strokeWidth="1.6" d="M27 47.5 C31 48.5 35 51 37.5 54" />
          <path strokeWidth="1.5" d="M38.6 27.6 L41.2 27.4" />
          <path strokeWidth="1.5" d="M28.6 27.5 C27 27.5 26.6 30.5 28.4 31.6" />
          {/* la rama de la corona */}
          <path strokeWidth="1.1" d="M21.5 36 C19.5 28 22 20.5 28 17.6 C32 16 37 16.4 40.2 19.6" />
        </g>
        <g fill={VINO}>
          {HOJAS.map(([x, y, giro]) => (
            <path key={`${x}-${y}`} d={HOJA} transform={`translate(${x} ${y}) rotate(${giro})`} />
          ))}
        </g>
      </g>
    </svg>
  )
}
