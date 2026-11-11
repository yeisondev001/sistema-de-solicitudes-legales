import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

/** Una tarjeta del despacho: título con letra de libro, una acción a la derecha y su contenido */
export function Seccion({
  titulo, accion, className, children,
}: {
  titulo: string
  accion?: { texto: string; a: string }
  className?: string
  children: React.ReactNode
}) {
  return (
    <section className={cn('rounded-2xl border border-papel-borde bg-card p-5 md:p-6', className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-heading text-[1.35rem] font-medium text-ink">{titulo}</h2>
        {accion && (
          // 44 px para el dedo sin agrandar el encabezado: el margen negativo se come el relleno
          <Link
            to={accion.a}
            className="-my-2.5 -mr-2 inline-flex min-h-11 shrink-0 items-center px-2 text-[0.9rem] text-marca-texto hover:underline"
          >
            {accion.texto}
          </Link>
        )}
      </div>
      {children}
    </section>
  )
}

/** Un renglón de una lista: título, detalle y, si hace falta, una etiqueta a la derecha */
export function Renglon({
  titulo, detalle, etiqueta, a, alTocar,
}: {
  titulo: string
  detalle?: string
  etiqueta?: string
  a?: string
  alTocar?: () => void
}) {
  const contenido = (
    <>
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 font-bold text-ink">{titulo}</span>
        {detalle && <span className="mt-0.5 block text-[0.88rem] text-ink-soft">{detalle}</span>}
      </span>
      {etiqueta && (
        <span className="shrink-0 rounded-full bg-aviso px-2.5 py-0.5 text-[0.8rem] font-bold text-aviso-texto">{etiqueta}</span>
      )}
    </>
  )
  const clase = 'flex items-start gap-3 border-b border-papel-borde py-3 last:border-b-0 last:pb-0 first:pt-0'
  if (a)
    return (
      <Link to={a} className={cn(clase, 'hover:[&_.font-bold]:text-marca-texto')}>
        {contenido}
      </Link>
    )
  if (alTocar)
    return (
      <button type="button" onClick={alTocar} className={cn(clase, 'w-full text-left hover:[&_.font-bold]:text-marca-texto')}>
        {contenido}
      </button>
    )
  return <div className={clase}>{contenido}</div>
}
