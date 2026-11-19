import { useCallback, useEffect, useState } from 'react'
import { BookOpen, FileSearch, FileText, Gavel, Loader2, Quote, ScanSearch, ShieldCheck, Trash2, Upload, UserRound } from 'lucide-react'
import { toast } from 'sonner'
import { Cargando } from '@/components/cargando'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import { useSubida } from '@/components/subida'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { api, ErrorApi } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Documento } from '@/lib/tipos'

const ESTANTES = [
  { icono: Gavel, titulo: 'Sentencias de la Suprema Corte de Justicia', texto: 'Del Boletín Judicial; las nuevas se agregan solas cada mes.' },
  { icono: BookOpen, titulo: 'Leyes y reglamentos', texto: 'La Ley 108-05 y sus reglamentos, los códigos y otras leyes, artículo por artículo.' },
  { icono: UserRound, titulo: 'Sus documentos', texto: 'Lo que usted sube: solo usted lo ve, y Papiniano lo busca junto con lo demás.' },
]

// Cómo trabaja Papiniano: una IA que responde con los textos de esta biblioteca, no de memoria.
// Sin prometer que nunca se equivoca: lo que se promete es que todo se puede comprobar.
const PASOS = [
  { icono: ScanSearch, titulo: 'Busca en la biblioteca', texto: 'Ante cada pregunta busca en las sentencias, las leyes y sus documentos, por las palabras y por la idea.' },
  { icono: FileSearch, titulo: 'Lee lo que encontró', texto: 'Responde con esos textos, no de memoria. Si no encuentra nada que sirva, se lo dice en vez de inventar una respuesta.' },
  { icono: Quote, titulo: 'Cita cada afirmación', texto: 'Cada dato lleva su fuente entre corchetes: la sentencia o el artículo exacto de donde sale.' },
  { icono: ShieldCheck, titulo: 'Usted lo comprueba', texto: 'Un clic abre la página original del Boletín Judicial o de la ley, tal como es, para verificarla antes de usarla.' },
]

/** Qué hay en la biblioteca y los documentos propios de la persona. */
export default function Biblioteca() {
  const { perfil } = useSesion()
  const [datos, setDatos] = useState<{ configurada: boolean; documentos: Documento[] } | null>(null)
  const [error, setError] = useState('')
  const [porQuitar, setPorQuitar] = useState<Documento | null>(null)

  const cargar = useCallback(() => {
    api
      .get<{ configurada: boolean; documentos: Documento[] }>('/api/documentos')
      .then((d) => {
        setDatos(d)
        setError('')
      })
      .catch((e: ErrorApi) => setError(e.message))
  }, [])
  useEffect(cargar, [cargar])
  const subida = useSubida(cargar)

  async function quitar(d: Documento) {
    try {
      await api.borrar(`/api/documentos/${d.id}`)
      toast.success(`«${d.titulo}» quitado del buscador.`)
      cargar()
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      {subida.entrada}
      <TituloSala titulo="Biblioteca" sub="Las sentencias, las leyes y sus documentos, en un mismo buscador." />

      <div className="space-y-5">
        <Seccion titulo="Cómo trabaja Papiniano">
          <p className="mb-4 max-w-3xl text-[0.98rem] text-ink-soft">
            Papiniano es una inteligencia artificial que responde <strong className="text-ink">a partir de los textos de esta
            biblioteca</strong>, no de lo que «cree saber». Por eso cada respuesta trae sus fuentes y usted puede comprobar
            cada una.
          </p>
          <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {PASOS.map(({ icono: Icono, titulo, texto }, i) => (
              <li key={titulo} className="space-y-2 rounded-xl border border-papel-borde bg-background p-4">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-full bg-marca-texto/10 text-sm font-bold text-marca-texto">
                    {i + 1}
                  </span>
                  <Icono className="size-5 text-marca-texto" aria-hidden />
                </div>
                <p className="font-bold text-ink">{titulo}</p>
                <p className="text-[0.92rem] text-ink-soft">{texto}</p>
              </li>
            ))}
          </ol>
          <p className="mt-4 text-[0.88rem] italic text-ink-soft">
            Es una herramienta de apoyo: revise siempre la fuente antes de citarla en un escrito.
          </p>
        </Seccion>

        <Seccion titulo="Qué hay en su biblioteca">
          <div className="grid gap-4 md:grid-cols-3">
            {ESTANTES.map(({ icono: Icono, titulo, texto }) => (
              <div key={titulo} className="space-y-2 rounded-xl border border-papel-borde bg-background p-4">
                <Icono className="size-6 text-marca-texto" />
                <p className="font-bold text-ink">{titulo}</p>
                <p className="text-[0.92rem] text-ink-soft">{texto}</p>
              </div>
            ))}
          </div>
        </Seccion>

        <Seccion titulo="Mis documentos">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            {perfil.propios ? (
              <>
                <p className="max-w-xl text-[0.95rem] text-ink-soft">
                  Suba sentencias, resoluciones o escritos en PDF digital o Word (hasta 20 MB). Solo usted los verá.
                </p>
                <Button size="grande" onClick={subida.abrir} disabled={subida.subiendo || datos?.configurada === false}>
                  {subida.subiendo ? <Loader2 className="animate-spin" /> : <Upload />}
                  {subida.subiendo ? 'Subiendo…' : 'Subir documentos'}
                </Button>
              </>
            ) : (
              <p className="max-w-xl text-[0.95rem] text-ink-soft">
                Subir sus propios documentos para que Papiniano también busque en ellos viene con el plan Abogado. Para
                pasar al plan Abogado, escríbanos.
              </p>
            )}
          </div>
          {error ? (
            <p className="text-destructive">{error}</p>
          ) : !datos ? (
            <Cargando que="Cargando sus documentos" />
          ) : !datos.configurada ? (
            <p className="text-ink-soft">Falta configurar el buscador en el servidor (variable JURIS_DATABASE_URL).</p>
          ) : datos.documentos.length ? (
            <ul>
              {datos.documentos.map((d) => (
                <li key={d.id} className="flex items-center gap-3 border-t border-papel-borde py-2.5">
                  <FileText className="size-5 shrink-0 text-ink-soft" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-ink">{d.titulo}</p>
                    <p className="truncate text-[0.85rem] text-ink-soft">
                      {[d.numero, d.sala, d.materia].filter(Boolean).join(' · ') || 'Sin ficha'}
                    </p>
                  </div>
                  <Button variant="ghost" size="icon-grande" className="text-destructive" aria-label={`Quitar «${d.titulo}»`} onClick={() => setPorQuitar(d)}>
                    <Trash2 />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-ink-soft">Todavía no ha subido documentos.</p>
          )}
        </Seccion>
      </div>

      <AlertDialog open={Boolean(porQuitar)} onOpenChange={(abierto) => !abierto && setPorQuitar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Quitar el documento?</AlertDialogTitle>
            <AlertDialogDescription>
              «{porQuitar?.titulo}» deja de salir en sus búsquedas. Si lo necesita otra vez, súbalo de nuevo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande">Cancelar</AlertDialogCancel>
            <AlertDialogAction variant="peligro" size="grande" onClick={() => porQuitar && quitar(porQuitar)}>
              <Trash2 /> Sí, quitar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
