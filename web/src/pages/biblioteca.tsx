import { useCallback, useEffect, useState } from 'react'
import { BookOpen, FileText, Gavel, Loader2, Trash2, Upload, UserRound } from 'lucide-react'
import { toast } from 'sonner'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import { useSubida } from '@/components/subida'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { api, ErrorApi } from '@/lib/api'
import type { Documento } from '@/lib/tipos'

const ESTANTES = [
  { icono: Gavel, titulo: 'Sentencias de la Suprema Corte de Justicia', texto: 'Del Boletín Judicial; las nuevas se agregan solas cada mes.' },
  { icono: BookOpen, titulo: 'Leyes y reglamentos', texto: 'La Ley 108-05 y sus reglamentos, los códigos y otras leyes, artículo por artículo.' },
  { icono: UserRound, titulo: 'Sus documentos', texto: 'Lo que usted sube: solo usted lo ve, y el asistente lo busca junto con lo demás.' },
]

/** Qué hay en la biblioteca y los documentos propios de la persona. */
export default function Biblioteca() {
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
            <p className="max-w-xl text-[0.95rem] text-ink-soft">
              Suba sentencias, resoluciones o escritos en PDF digital o Word (hasta 20 MB). Solo usted los verá.
            </p>
            <Button size="grande" onClick={subida.abrir} disabled={subida.subiendo || datos?.configurada === false}>
              {subida.subiendo ? <Loader2 className="animate-spin" /> : <Upload />}
              {subida.subiendo ? 'Subiendo…' : 'Subir documentos'}
            </Button>
          </div>
          {error ? (
            <p className="text-destructive">{error}</p>
          ) : !datos ? (
            <p className="text-ink-soft">Cargando…</p>
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
                  <Button variant="ghost" size="icon-lg" className="text-destructive" aria-label={`Quitar «${d.titulo}»`} onClick={() => setPorQuitar(d)}>
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
            <AlertDialogCancel className="h-10">Cancelar</AlertDialogCancel>
            <AlertDialogAction className="h-10 bg-destructive text-card hover:bg-destructive/90" onClick={() => porQuitar && quitar(porQuitar)}>
              Quitar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
