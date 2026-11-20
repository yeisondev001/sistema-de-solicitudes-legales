import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Antetitulo, CabeceraPublica, PiePublico } from '@/components/publico'
import { api } from '@/lib/api'
import { NOMBRE_APP } from '@/lib/tema'
import { useTitulo } from '@/lib/titulo'
import NoEncontrada from '@/pages/no-encontrada'

/**
 * El blog (/blog y /blog/<dirección>): guías para traer visitas desde Google. Los artículos son archivos Markdown en
 * la carpeta blog/ del servidor (ver blog.py); el servidor ya manda el artículo completo en el HTML para Google, y
 * aquí se muestra con el mismo diseño de la página pública.
 */

interface Resumen {
  slug: string
  titulo: string
  descripcion: string
  fecha: string
  actualizado: string
}
interface Articulo extends Resumen {
  publicado: boolean
  revisado: string
  html: string
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
const fechaLarga = (iso: string) => {
  const [a, m, d] = iso.split('-').map(Number)
  return a && m && d ? `${d} de ${MESES[m - 1]} de ${a}` : iso
}

function Marco({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-background text-ink">
      <CabeceraPublica />
      <main className="mx-auto max-w-[760px] px-5 py-10 md:py-14">{children}</main>
      <PiePublico />
    </div>
  )
}

export function Blog() {
  useTitulo(`Blog: guías de derecho dominicano · ${NOMBRE_APP}`)
  const [lista, setLista] = useState<Resumen[] | null>(null)
  useEffect(() => {
    window.scrollTo(0, 0)
    api.get<Resumen[]>('/api/blog').then(setLista).catch(() => setLista([]))
  }, [])

  return (
    <Marco>
      <div className="space-y-3">
        <Antetitulo>BLOG</Antetitulo>
        <h1 className="font-heading text-[2.3rem] leading-tight font-medium md:text-[2.8rem]">Guías de derecho dominicano</h1>
        <p className="text-[1.1rem] leading-relaxed text-ink-soft">
          Explicadas paso a paso y con los artículos de la ley, para el trabajo de todos los días.
        </p>
      </div>
      <div className="mt-10 space-y-4">
        {lista === null ? (
          <p className="text-ink-soft" role="status">Cargando…</p>
        ) : lista.length === 0 ? (
          <p className="rounded-xl border border-papel-borde bg-card p-6 text-ink-soft">Muy pronto publicamos las primeras guías.</p>
        ) : (
          lista.map((a) => (
            <article key={a.slug} className="rounded-xl border border-papel-borde bg-card p-6 hover:border-marca">
              <h2 className="font-heading text-[1.45rem] leading-snug font-medium">
                <Link to={`/blog/${a.slug}`} className="text-ink hover:text-marca-texto">{a.titulo}</Link>
              </h2>
              <p className="mt-2 text-ink-soft">{a.descripcion}</p>
              <p className="mt-3 text-[0.85rem] text-ink-soft">{fechaLarga(a.actualizado)}</p>
            </article>
          ))
        )}
      </div>
    </Marco>
  )
}

export function ArticuloBlog() {
  const { slug = '' } = useParams()
  const [a, setA] = useState<Articulo | null | 'no'>(null)
  useTitulo(a && a !== 'no' ? `${a.titulo} · ${NOMBRE_APP}` : NOMBRE_APP)
  useEffect(() => {
    window.scrollTo(0, 0)
    setA(null)
    api
      .get<Articulo>(`/api/blog/${encodeURIComponent(slug)}`)
      .then(setA)
      .catch(() => setA('no'))
  }, [slug])

  if (a === 'no') return <NoEncontrada />
  return (
    <Marco>
      {a === null ? (
        <p className="text-ink-soft" role="status">Cargando…</p>
      ) : (
        <article>
          <nav aria-label="Ruta" className="mb-6 text-[0.9rem] text-ink-soft">
            <Link to="/" className="hover:text-marca-texto">Inicio</Link> › <Link to="/blog" className="hover:text-marca-texto">Blog</Link>
          </nav>
          {!a.publicado && (
            <p className="mb-6 rounded-xl border border-aviso-texto/30 bg-aviso p-4 text-[0.95rem] text-aviso-texto">
              <strong>Borrador.</strong> Falta la revisión de un abogado: todavía no sale en el blog ni en Google.
            </p>
          )}
          <h1 className="font-heading text-[2.1rem] leading-tight font-medium md:text-[2.6rem]">{a.titulo}</h1>
          <p className="mt-3 text-[0.9rem] text-ink-soft">
            Actualizado el {fechaLarga(a.actualizado)} · Equipo de {NOMBRE_APP}
            {a.revisado && <> · Revisado por {a.revisado}</>}
          </p>
          {/* el HTML lo arma el servidor desde nuestros propios archivos Markdown (blog/), no viene de usuarios */}
          <div
            className="lectura mt-8 max-w-none text-[1.05rem] leading-relaxed [&_a]:font-semibold [&_h2]:mt-10 [&_h2]:text-[1.5rem]"
            dangerouslySetInnerHTML={{ __html: a.html }}
          />
        </article>
      )}
    </Marco>
  )
}
