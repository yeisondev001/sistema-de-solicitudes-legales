import { useId } from 'react'
import { cn } from '@/lib/utils'

export const NOMBRE_ASISTENTE = 'Papiniano'

// Los colores de la marca, iguales en todos los temas: el ícono es parte de la identidad, como el logo
const VINO = '#7A1F2B'
const MARFIL = '#F8F4EC'
const ORO = '#E2C29B'
const HOJA = 'M0 0 C2 -2.1 5 -2.1 7 0 C5 2.1 2 2.1 0 0 Z'
// las hojas de la corona, de la nuca a la frente: [x, y, giro hacia afuera, giro hacia adentro]
const HOJAS: [number, number, number, number][] = [
  [20.4, 31.5, -112, -60], [21.4, 25.6, -92, -40], [24.2, 20.6, -72, -20], [28.4, 17.1, -52, 2], [33.5, 15.3, -28, 24],
]

/**
 * Papiniano, el asistente, en camafeo: su perfil en marfil sobre vino, con corona de laurel y toga,
 * dentro de un borde de perlas doradas. Por Emilio Papiniano (siglo III), el jurista más respetado de Roma.
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
      <circle cx="32" cy="32" r="30" fill="none" stroke={ORO} strokeWidth="2.2" strokeDasharray="0 3.4" strokeLinecap="round" />
      <clipPath id={recorte}>
        <circle cx="32" cy="32" r="29" />
      </clipPath>
      <g clipPath={`url(#${recorte})`}>
        {/* el perfil, mirando a la derecha, con la toga sobre los hombros */}
        <path
          fill={MARFIL}
          d="M24.5 47 C20 43 17.5 36 18 29 C18.5 19 25 13 33 13.5 C39 14 43 18 43.8 23.5 C44 25 44.3 25.6 44.6 26 L47.6 31.6 C47.8 32.2 47.3 32.8 46.6 32.8 L45 33 C45.6 33.6 45.6 34.3 45 34.8 L44.6 35.2 C45.3 35.7 45.2 36.6 44.5 37 C44.9 38.9 44.4 40.5 42.9 41.2 C41.2 41.9 39.7 42 38.7 42.5 L38.6 49 C45 50.5 51 54 53 66 L9 66 C11 54 16.5 49.5 24.5 47 Z"
        />
        <g fill="none" stroke={VINO} strokeLinecap="round" strokeLinejoin="round">
          {/* ojo, ceja, oreja, boca y los pliegues de la toga */}
          <path strokeWidth="1.2" d="M39.2 26.9 C40 26.2 41.2 26.2 42 26.8 C41.2 27.4 40 27.4 39.2 26.9 Z" />
          <path strokeWidth="1.2" d="M38.6 25 C40 24.2 41.8 24.2 43 24.9" />
          <path strokeWidth="1.3" d="M29.5 27 C27.5 27 26.8 30.5 28.6 32 C29.4 32.6 30.2 31.8 29.8 30.8" />
          <path strokeWidth="1.1" d="M44.6 35.2 L43 35.4" />
          <path strokeWidth="1.5" d="M20 54 C27 51.5 33 53 39.5 60 M27 48.6 C31 49.6 35.2 52 37.8 55.2" />
          {/* la rama de la corona */}
          <path strokeWidth="1" d="M21.2 35 C19.5 27 22 19.5 28.5 16.3 C33 14.3 38 15 41.2 18.6" />
        </g>
        <g fill={VINO}>
          {HOJAS.flatMap(([x, y, afuera, adentro]) => [
            <path key={`${x}a`} d={HOJA} transform={`translate(${x} ${y}) rotate(${afuera})`} />,
            <path key={`${x}b`} d={HOJA} transform={`translate(${x} ${y}) rotate(${adentro})`} />,
          ])}
        </g>
      </g>
    </svg>
  )
}
