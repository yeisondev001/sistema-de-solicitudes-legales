import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { BookOpen, ChevronDown, ChevronLeft, ChevronRight, Copy, ExternalLink, FileText, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { NOMBRE_ASISTENTE, Papiniano } from '@/components/papiniano'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { Fuente, Turno } from '@/lib/tipos'

export function BurbujaUsuario({ texto }: { texto: string }) {
  return (
    <div className="ml-12 self-end rounded-2xl rounded-br-sm bg-panel px-4 py-3 whitespace-pre-wrap text-sobre-panel">
      {texto}
    </div>
  )
}

/** Una respuesta de Papiniano, el asistente: el texto (Markdown), copiar, y las fuentes citadas con su página. */
export function Burbuja({ turno }: { turno: Turno }) {
  const citadas = new Set(turno.citadas ?? [])
  // si respondió la IA se muestran solo las fuentes que citó; si no, todas las encontradas
  const lista = (turno.fuentes ?? [])
    .map((f, i) => [i + 1, f] as const)
    .filter(([n]) => citadas.has(n) || !turno.ia)
  const titulo = citadas.size
    ? lista.length === 1 ? 'Ver la fuente citada' : `Ver las ${lista.length} fuentes citadas`
    : `Ver las ${lista.length} fuentes encontradas`

  function copiar() {
    // sin las marcas de Markdown (** y >), para pegarlo en un escrito o un correo
    navigator.clipboard
      .writeText(turno.texto.replace(/\*\*|__/g, '').replace(/^>\s?/gm, ''))
      .then(() => toast.success('Respuesta copiada.'))
      .catch(() => toast.error('No se pudo copiar. Seleccione el texto a mano.'))
  }

  return (
    <div className="mr-6 space-y-1.5">
      <div className="flex items-center gap-2 text-[0.82rem] font-bold text-ink-soft">
        <Papiniano className="size-7" decorativo />
        <span className="flex-1 text-[0.9rem] text-ink">{NOMBRE_ASISTENTE}</span>
        {(turno.fuentes || turno.ia) && (
          <Button variant="ghost" size="sm" className="h-11 px-3 text-ink-soft" onClick={copiar}>
            <Copy /> Copiar
          </Button>
        )}
      </div>
      <div className="space-y-3 rounded-2xl rounded-tl-sm border border-papel-borde bg-card px-5 py-4">
        <div className="lectura">
          <Markdown
            remarkPlugins={[remarkGfm]}
            components={{
              table: (props) => (
                <div className="tabla">
                  <table {...props} />
                </div>
              ),
              a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
            }}
          >
            {turno.texto}
          </Markdown>
        </div>
        {lista.length > 0 && (
          <Collapsible>
            <CollapsibleTrigger className="group flex w-full items-center gap-2 rounded-md py-1.5 text-[0.88rem] font-bold text-ink-soft hover:text-ink">
              <BookOpen className="size-[1.1rem] text-marca-texto" />
              <span className="flex-1 text-left">{titulo}</span>
              <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" />
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-2 pt-2">
              {lista.map(([n, f]) => (
                <TarjetaFuente key={n} n={n} f={f} citada={citadas.has(n)} />
              ))}
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    </div>
  )
}

/** El extracto viene con las palabras buscadas entre <b>…</b>: se resaltan sin meter HTML */
function Extracto({ texto }: { texto: string }) {
  return (
    <>
      {texto.split(/(<b>.*?<\/b>)/g).map((parte, i) =>
        parte.startsWith('<b>') ? (
          <strong key={i} className="font-bold text-ink not-italic">{parte.slice(3, -4)}</strong>
        ) : (
          parte
        ),
      )}
    </>
  )
}

const ABRIR: Record<string, string> = { ley: 'Abrir el texto oficial', doctrina: 'Abrir el libro' }

function TarjetaFuente({ n, f, citada }: { n: number; f: Fuente; citada: boolean }) {
  const [verPagina, setVerPagina] = useState(false)
  const [leer, setLeer] = useState(false)
  return (
    <div className="space-y-1.5 rounded-lg border border-papel-borde bg-background p-3">
      <p className="flex gap-2 text-[0.88rem] font-bold text-ink">
        <span className={citada ? 'text-marca-texto' : 'text-ink-soft'}>[{n}]</span>
        <span>{f.referencia}</span>
      </p>
      {f.extracto && (
        <p className="text-[0.88rem] text-ink-soft italic">
          «…<Extracto texto={f.extracto} />…»
        </p>
      )}
      <div className="flex flex-wrap gap-1">
        {f.fuente_url ? (
          <Button variant="ghost" size="sm" className="h-11 px-3 text-ink" onClick={() => setVerPagina(true)}>
            <FileText /> Ver la página aquí
          </Button>
        ) : (
          <Button variant="ghost" size="sm" className="h-11 px-3 text-ink" onClick={() => setLeer(true)}>
            <FileText /> Leer aquí
          </Button>
        )}
        {f.fuente_url && (
          <Button variant="ghost" size="sm" className="h-11 px-3 text-ink-soft" asChild>
            <a href={`${f.fuente_url}#page=${f.pagina}`} target="_blank" rel="noreferrer">
              <ExternalLink /> {ABRIR[f.origen] ?? 'Abrir en el Boletín Judicial'}
            </a>
          </Button>
        )}
      </div>
      {verPagina && <Visor f={f} alCerrar={() => setVerPagina(false)} />}
      <Dialog open={leer} onOpenChange={setLeer}>
        <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-heading text-lg font-medium">{f.referencia}</DialogTitle>
            <DialogDescription>Es la parte del documento que encontró el buscador.</DialogDescription>
          </DialogHeader>
          <p className="leading-relaxed whitespace-pre-wrap text-ink">{f.texto}</p>
        </DialogContent>
      </Dialog>
    </div>
  )
}

/**
 * La página citada del PDF oficial, tal como es, como imagen (la arma jurisprudencia/visor.py
 * sin descargar el PDF entero), con botones para pasar de página.
 */
function Visor({ f, alCerrar }: { f: Fuente; alCerrar: () => void }) {
  const [pagina, setPagina] = useState(f.pagina)
  const [total, setTotal] = useState<number | null>(null)
  const [imagen, setImagen] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    let url: string | null = null
    setImagen(null)
    setError('')
    fetch(`/api/pagina?url=${encodeURIComponent(f.fuente_url)}&n=${pagina}`, { credentials: 'same-origin' })
      .then(async (r) => {
        if (!r.ok) throw new Error()
        const t = Number(r.headers.get('X-Total-Paginas'))
        url = URL.createObjectURL(await r.blob())
        if (vigente) {
          setTotal(t || null)
          setImagen(url)
        }
      })
      .catch(() => vigente && setError('No se pudo abrir la página. Use «Abrir el PDF oficial».'))
    return () => {
      vigente = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [f.fuente_url, pagina])

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && alCerrar()}>
      <DialogContent className="flex max-h-[94dvh] flex-col gap-3 sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="pr-8 font-heading text-base font-medium">{f.referencia}</DialogTitle>
          <DialogDescription className="sr-only">La página del documento oficial</DialogDescription>
        </DialogHeader>
        <div className="min-h-[50dvh] flex-1 overflow-y-auto rounded-md border border-papel-borde bg-white">
          {imagen ? (
            <img src={imagen} alt={`Página ${pagina}`} className="w-full" />
          ) : (
            <div className="flex h-[50dvh] flex-col items-center justify-center gap-3 p-6 text-center text-[0.95rem] text-neutral-600">
              {error || (
                <>
                  <Loader2 className="size-6 animate-spin" /> Abriendo la página…
                </>
              )}
            </div>
          )}
        </div>
        <DialogFooter className="flex-row items-center justify-between gap-2 sm:justify-between">
          <div className="flex items-center">
            <Button variant="ghost" size="icon-grande" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)} aria-label="Página anterior">
              <ChevronLeft />
            </Button>
            <span className="min-w-28 text-center text-[0.9rem] text-ink-soft">
              Página {pagina}{total ? ` de ${total}` : ''}
            </span>
            <Button
              variant="ghost"
              size="icon-grande"
              disabled={Boolean(total) && pagina >= (total ?? 0)}
              onClick={() => setPagina(pagina + 1)}
              aria-label="Página siguiente"
            >
              <ChevronRight />
            </Button>
          </div>
          <Button variant="ghost" className="h-11 text-ink-soft" asChild>
            <a href={`${f.fuente_url}#page=${pagina}`} target="_blank" rel="noreferrer">
              <ExternalLink /> <span className="sr-only sm:not-sr-only">Abrir el PDF oficial</span>
            </a>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
