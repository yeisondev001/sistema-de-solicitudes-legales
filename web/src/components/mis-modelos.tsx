import { useRef, useState } from 'react'
import { Eye, FileUp, Loader2, PencilLine, Replace } from 'lucide-react'
import { toast } from 'sonner'
import { Hoja } from '@/components/escrito'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ErrorApi, leerModelo } from '@/lib/api'
import { espacios, etiqueta } from '@/lib/escrito'
import type { Modelo } from '@/lib/tipos'

/** Lo que se está editando: un modelo nuevo (sin id) o uno suyo que ya existe */
export interface Borrador {
  id?: number
  nombre: string
  grupo: string
  materia: string
  texto: string
}

const SELECT =
  'h-11 w-full rounded-lg border border-pista/80 bg-papel px-3 text-base text-ink outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'

/**
 * Subir un modelo propio en dos pasos: elegir el Word y revisarlo. Al leerlo, la app ya cambió los datos que
 * reconoce (cédulas, montos, fechas…); los nombres los marca el abogado con «Convertir en dato», que cambia
 * ese texto en todo el modelo. Se guarda en su cuenta y solo lo ve él. El Word no se guarda ni pasa por la IA.
 */
export function SubirModelo({
  borrador, grupos, materias, alCerrar, alGuardar,
}: {
  /** null: elegir el archivo; si no, revisar ese borrador */
  borrador: Borrador | null
  grupos: Record<string, string>
  materias: Record<string, string>
  alCerrar: () => void
  alGuardar: (m: Modelo) => void
}) {
  const [actual, setActual] = useState<Borrador | null>(borrador)
  const [avisoLeido, setAvisoLeido] = useState('')
  const [leyendo, setLeyendo] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [vista, setVista] = useState(false)
  // «Convertir en dato»: el texto que seleccionó y el nombre que le pone
  const [seleccion, setSeleccion] = useState('')
  const [dato, setDato] = useState('')
  const area = useRef<HTMLTextAreaElement>(null)

  async function leer(archivo: File) {
    setLeyendo(true)
    try {
      const r = await leerModelo(archivo)
      setActual({ nombre: r.nombre, grupo: '', materia: '', texto: r.texto })
      setAvisoLeido(
        r.cambios
          ? `Ya cambiamos ${r.cambios === 1 ? '1 dato' : `${r.cambios} datos`} que reconocimos (cédulas, montos, fechas…).`
          : '',
      )
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setLeyendo(false)
    }
  }

  function seleccionar() {
    const t = area.current
    if (!t) return
    const s = t.value.slice(t.selectionStart, t.selectionEnd).trim()
    setSeleccion(s.length >= 2 && s.length <= 200 && !s.includes('\n') ? s : '')
  }

  const nombreDato = dato.toUpperCase().replace(/[[\]]/g, '').replace(/\s+/g, ' ').trim()
  const veces = actual && seleccion ? actual.texto.split(seleccion).length - 1 : 0

  function convertir() {
    if (!actual || !seleccion || nombreDato.length < 2) return
    setActual({ ...actual, texto: actual.texto.split(seleccion).join(`[${nombreDato}]`) })
    toast.success(`«${seleccion}» ahora es [${nombreDato}] (${veces === 1 ? '1 vez' : `${veces} veces`}).`)
    setSeleccion('')
    setDato('')
  }

  async function guardar() {
    if (!actual) return
    setGuardando(true)
    try {
      const cuerpo = { nombre: actual.nombre, grupo: actual.grupo, materia: actual.materia, texto: actual.texto }
      const m = actual.id
        ? await api.put<Modelo>(`/api/modelos/propios/${actual.id}`, cuerpo)
        : await api.post<Modelo>('/api/modelos/propios', cuerpo)
      toast.success(actual.id ? 'Modelo guardado.' : 'Modelo guardado en «Mis modelos».')
      alGuardar(m)
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setGuardando(false)
    }
  }

  const datos = actual ? espacios(actual.texto) : []

  return (
    <Dialog open onOpenChange={(a) => !a && alCerrar()}>
      <DialogContent className="flex max-h-[92dvh] flex-col sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-medium">
            {actual?.id ? 'Editar mi modelo' : 'Subir mi modelo'}
          </DialogTitle>
          <DialogDescription>
            Se guarda en su cuenta y solo lo ve usted. El Word no se guarda ni se le envía a la IA.
          </DialogDescription>
        </DialogHeader>

        {!actual ? (
          <div className="space-y-4">
            <p className="text-ink">
              Elija un escrito suyo en Word (.docx). Después lo revisa y cambia los nombres y datos del caso por datos
              por llenar, para usarlo en otros casos.
            </p>
            <label className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed border-regla bg-card px-6 py-10 text-center hover:border-marca">
              {leyendo ? <Loader2 className="size-8 animate-spin text-marca-texto" /> : <FileUp className="size-8 text-marca-texto" />}
              <span className="font-bold text-ink">{leyendo ? 'Leyendo el archivo…' : 'Elegir el archivo de Word'}</span>
              <span className="text-[0.9rem] text-ink-soft">Si es un .doc, ábralo en Word y guárdelo como .docx.</span>
              <input
                type="file"
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="sr-only"
                disabled={leyendo}
                onChange={(e) => {
                  const archivo = e.target.files?.[0]
                  e.target.value = ''
                  if (archivo) leer(archivo)
                }}
              />
            </label>
          </div>
        ) : (
          <div className="-mx-1 min-h-0 flex-1 space-y-4 overflow-y-auto px-1 pb-1">
            <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
              <div className="space-y-1.5">
                <Label htmlFor="modelo-nombre" className="text-[0.9rem] text-ink-soft">Nombre del modelo</Label>
                <Input
                  id="modelo-nombre"
                  value={actual.nombre}
                  onChange={(e) => setActual({ ...actual, nombre: e.target.value })}
                  className="h-11 border-pista/80 bg-papel text-base md:text-base"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="modelo-grupo" className="text-[0.9rem] text-ink-soft">Tipo</Label>
                <select
                  id="modelo-grupo"
                  value={actual.grupo}
                  onChange={(e) => setActual({ ...actual, grupo: e.target.value })}
                  className={SELECT}
                >
                  <option value="">Sin tipo</option>
                  {Object.entries(grupos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="modelo-materia" className="text-[0.9rem] text-ink-soft">Materia</Label>
                <select
                  id="modelo-materia"
                  value={actual.materia}
                  onChange={(e) => setActual({ ...actual, materia: e.target.value })}
                  className={SELECT}
                >
                  <option value="">Sin materia</option>
                  {Object.entries(materias).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
            </div>

            <div className="space-y-2 rounded-xl border border-aviso-texto/25 bg-aviso px-4 py-3 text-[0.92rem] text-ink">
              <p className="font-bold">Antes de guardarlo, quite los datos del caso</p>
              <p>
                {avisoLeido && `${avisoLeido} `}
                Los nombres de personas y empresas, direcciones y números de expediente o de parcela los cambia usted:
                seleccione el texto en el modelo y toque «Convertir en dato». Así nunca le llegan a la IA.
              </p>
            </div>

            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[14rem] flex-1 space-y-1.5">
                <Label htmlFor="modelo-dato" className="text-[0.9rem] text-ink-soft">
                  {seleccion ? `«${seleccion.length > 40 ? `${seleccion.slice(0, 40)}…` : seleccion}» se cambia por:` : 'Seleccione un texto en el modelo'}
                </Label>
                <Input
                  id="modelo-dato"
                  value={dato}
                  disabled={!seleccion}
                  onChange={(e) => setDato(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && convertir()}
                  placeholder="Por ejemplo: NOMBRE DEL DEMANDANTE"
                  className="h-11 border-pista/80 bg-papel text-base uppercase md:text-base"
                />
              </div>
              <Button className="h-11" disabled={!seleccion || nombreDato.length < 2} onClick={convertir}>
                <Replace /> Convertir en dato {veces > 1 && `(${veces} veces)`}
              </Button>
              <Button variant="outline" className="h-11 border-regla" onClick={() => setVista(!vista)}>
                {vista ? <PencilLine /> : <Eye />} {vista ? 'Volver a editar' : 'Ver cómo queda'}
              </Button>
            </div>

            {vista ? (
              <div className="@container rounded-lg bg-muted/60 p-3 md:p-5">
                <Hoja texto={actual.texto} />
              </div>
            ) : (
              <textarea
                ref={area}
                value={actual.texto}
                onChange={(e) => setActual({ ...actual, texto: e.target.value })}
                onSelect={seleccionar}
                aria-label="Texto del modelo"
                style={{ fontFamily: '"Century Gothic", "Didact Gothic", sans-serif' }}
                className="block min-h-[45dvh] w-full resize-y rounded-lg border border-pista/80 bg-papel p-4 text-[0.95rem] leading-relaxed text-ink outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
            )}

            {datos.length > 0 && (
              <p className="text-[0.9rem] text-ink-soft">
                <strong className="text-ink">Datos por llenar ({datos.length}):</strong>{' '}
                {datos.slice(0, 12).map(etiqueta).join(' · ')}
                {datos.length > 12 && ` y ${datos.length - 12} más`}
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" size="grande" className="border-regla" onClick={alCerrar}>Cancelar</Button>
          {actual && (
            <Button size="grande" disabled={guardando || !actual.nombre.trim() || !actual.texto.trim()} onClick={guardar}>
              {guardando && <Loader2 className="animate-spin" />} Guardar modelo
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
