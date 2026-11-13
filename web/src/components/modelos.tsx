import { useEffect, useState } from 'react'
import { Eye, Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Hoja } from '@/components/escrito'
import { SubirModelo, type Borrador } from '@/components/mis-modelos'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api, ErrorApi } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Modelo } from '@/lib/tipos'
import { cn } from '@/lib/utils'

interface Catalogo {
  modelos: Modelo[]
  /** los que subió el abogado */
  propios: Modelo[]
  /** los que comparten sus colegas de oficina (plan Despacho) */
  oficina: Modelo[]
  /** clave → nombre, en el orden en que se muestran */
  grupos: Record<string, string>
  materias: Record<string, string>
}

/**
 * «Modelos»: los suyos («Mis modelos», que sube él) y los de todos, por grupo (actos, demandas, conclusiones…)
 * y con un filtro por materia. Cada uno se puede ver antes de usarlo; al usarlo, Papiniano lo pone en la hoja
 * y pide los datos.
 */
export function GaleriaModelos({
  abierto, alCerrar, alUsar, ocupado,
}: {
  abierto: boolean
  alCerrar: () => void
  alUsar: (m: Modelo) => void
  ocupado: boolean
}) {
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [error, setError] = useState('')
  const [materia, setMateria] = useState('')
  const [viendo, setViendo] = useState<Modelo | null>(null)
  // subir uno nuevo (null) o editar uno suyo; undefined: no se está subiendo nada
  const [subiendo, setSubiendo] = useState<Borrador | null | undefined>(undefined)
  const [porBorrar, setPorBorrar] = useState<Modelo | null>(null)
  const { perfil } = useSesion()

  useEffect(() => {
    if (!abierto || catalogo) return
    api
      .get<Catalogo>('/api/modelos')
      .then(setCatalogo)
      .catch((e: ErrorApi) => setError(e.message))
  }, [abierto, catalogo])

  const deMateria = (m: Modelo) => !materia || m.materia === materia
  const lista = catalogo?.modelos.filter(deMateria) ?? []
  const propios = catalogo?.propios.filter(deMateria) ?? []
  const deOficina = catalogo?.oficina.filter(deMateria) ?? []
  const materias = catalogo
    ? Object.entries(catalogo.materias).filter(([k]) =>
        [...catalogo.modelos, ...catalogo.propios, ...catalogo.oficina].some((m) => m.materia === k),
      )
    : []
  const idDe = (m: Modelo) => Number(m.clave.replace('propio-', ''))

  async function editar(m: Modelo) {
    try {
      const r = await api.get<Modelo & { texto: string }>(`/api/modelos/${m.clave}`)
      setSubiendo({
        id: idDe(m), nombre: r.nombre, grupo: r.grupo, materia: r.materia, texto: r.texto, compartido: Boolean(r.compartido),
      })
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  async function borrar(m: Modelo) {
    try {
      await api.borrar(`/api/modelos/propios/${idDe(m)}`)
      toast.success('Modelo borrado.')
      setCatalogo(null) // se vuelve a pedir la lista
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(a) => !a && alCerrar()}>
      <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-medium">Modelos de escritos</DialogTitle>
          <DialogDescription>
            Elija uno: Papiniano lo pone en la hoja y le pide los datos del caso. Están hechos de escritos reales, sin
            ningún dato de las personas.
          </DialogDescription>
        </DialogHeader>

        {catalogo ? (
          <>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Materia">
              {[['', 'Todas'] as const, ...materias].map(([clave, nombre]) => (
                <button
                  key={clave}
                  type="button"
                  aria-pressed={materia === clave}
                  onClick={() => setMateria(clave)}
                  className={cn(
                    'h-10 rounded-full border px-4 text-[0.92rem] transition-colors',
                    materia === clave ? 'border-marca bg-marca font-bold text-sobre-boton' : 'border-regla bg-card text-ink hover:border-marca',
                  )}
                >
                  {nombre}
                </button>
              ))}
            </div>
            <div className="-mx-1 min-h-0 flex-1 space-y-6 overflow-y-auto px-1 pb-1">
              <section className="space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-heading text-lg font-medium text-ink">
                    Mis modelos <span className="font-sans text-[0.9rem] text-ink-soft">({propios.length})</span>
                  </h3>
                  <Button variant="outline" className="h-11 border-regla" onClick={() => setSubiendo(null)}>
                    <Plus /> Subir mi modelo
                  </Button>
                </div>
                {propios.length ? (
                  <ul className="space-y-2.5">
                    {propios.map((m) => (
                      <li key={m.clave}>
                        <FichaModelo
                          modelo={m}
                          materia={catalogo.materias[m.materia]}
                          grupo={catalogo.grupos[m.grupo]}
                          ocupado={ocupado}
                          alVer={() => setViendo(m)}
                          alUsar={() => alUsar(m)}
                          alEditar={() => editar(m)}
                          alBorrar={() => setPorBorrar(m)}
                        />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[0.92rem] text-ink-soft">
                    {catalogo.propios.length
                      ? 'Ninguno de sus modelos es de esta materia.'
                      : perfil.oficina
                        ? 'Suba sus propios escritos en Word para usarlos como modelo. Solo los ve usted, salvo los que comparta con su oficina.'
                        : 'Suba sus propios escritos en Word para usarlos como modelo. Solo los ve usted.'}
                  </p>
                )}
              </section>
              {deOficina.length > 0 && (
                <section className="space-y-2.5">
                  <h3 className="font-heading text-lg font-medium text-ink">
                    De la oficina <span className="font-sans text-[0.9rem] text-ink-soft">({deOficina.length})</span>
                  </h3>
                  <ul className="space-y-2.5">
                    {deOficina.map((m) => (
                      <li key={m.clave}>
                        <FichaModelo
                          modelo={m}
                          materia={catalogo.materias[m.materia]}
                          grupo={catalogo.grupos[m.grupo]}
                          ocupado={ocupado}
                          alVer={() => setViendo(m)}
                          alUsar={() => alUsar(m)}
                        />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {Object.entries(catalogo.grupos).map(([grupo, nombre]) => {
                const delGrupo = lista.filter((m) => m.grupo === grupo)
                return (
                  delGrupo.length > 0 && (
                    <section key={grupo} className="space-y-2.5">
                      <h3 className="font-heading text-lg font-medium text-ink">
                        {nombre} <span className="font-sans text-[0.9rem] text-ink-soft">({delGrupo.length})</span>
                      </h3>
                      <ul className="space-y-2.5">
                        {delGrupo.map((m) => (
                          <li key={m.clave}>
                            <FichaModelo
                              modelo={m}
                              materia={catalogo.materias[m.materia]}
                              ocupado={ocupado}
                              alVer={() => setViendo(m)}
                              alUsar={() => alUsar(m)}
                            />
                          </li>
                        ))}
                      </ul>
                    </section>
                  )
                )
              })}
            </div>
          </>
        ) : error ? (
          <p className="text-destructive" role="alert">{error}</p>
        ) : (
          <p className="flex items-center gap-2 text-ink-soft">
            <Loader2 className="size-4 animate-spin" /> Buscando los modelos…
          </p>
        )}
      </DialogContent>
      <VistaModelo
        key={viendo?.clave}
        modelo={viendo}
        ocupado={ocupado}
        alCerrar={() => setViendo(null)}
        alUsar={(m) => {
          setViendo(null)
          alUsar(m)
        }}
      />
      {catalogo && subiendo !== undefined && (
        <SubirModelo
          borrador={subiendo}
          grupos={catalogo.grupos}
          materias={catalogo.materias}
          alCerrar={() => setSubiendo(undefined)}
          alGuardar={() => {
            setSubiendo(undefined)
            setCatalogo(null)
          }}
        />
      )}
      <AlertDialog open={Boolean(porBorrar)} onOpenChange={(a) => !a && setPorBorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Borrar su modelo?</AlertDialogTitle>
            <AlertDialogDescription>
              «{porBorrar?.nombre}». Los escritos que ya hizo con él no se borran. Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande">Cancelar</AlertDialogCancel>
            <AlertDialogAction variant="peligro" size="grande" onClick={() => porBorrar && borrar(porBorrar)}>
              <Trash2 /> Sí, borrar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  )
}

/** Un modelo en una lista: su nombre, dónde y cuándo se usa, y los botones para verlo o usarlo (y, si es suyo, editarlo o borrarlo) */
function FichaModelo({
  modelo, materia, grupo, ocupado, alVer, alUsar, alEditar, alBorrar,
}: {
  modelo: Modelo
  materia?: string
  grupo?: string
  ocupado: boolean
  alVer: () => void
  alUsar: () => void
  alEditar?: () => void
  alBorrar?: () => void
}) {
  const donde = [modelo.tribunal || grupo, materia].filter(Boolean).join(' · ')
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-papel-borde bg-card p-4 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-bold text-ink">{modelo.nombre}</p>
        {donde && <p className="text-[0.85rem] text-ink-soft">{donde}</p>}
        {!modelo.propio && <p className="text-[0.92rem] leading-snug text-ink-soft">{modelo.cuando}</p>}
        {modelo.propio && modelo.compartido && <p className="text-[0.85rem] text-marca-texto">Compartido con la oficina</p>}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        {alEditar && (
          <Button variant="ghost" size="icon-grande" className="text-ink-soft" onClick={alEditar} aria-label={`Editar «${modelo.nombre}»`} title="Editar">
            <Pencil />
          </Button>
        )}
        {alBorrar && (
          <Button variant="ghost" size="icon-grande" className="text-ink-soft" onClick={alBorrar} aria-label={`Borrar «${modelo.nombre}»`} title="Borrar">
            <Trash2 />
          </Button>
        )}
        <Button variant="outline" className="h-11 flex-1 border-regla sm:flex-none" onClick={alVer}>
          <Eye /> Ver
        </Button>
        <Button className="h-11 flex-1 sm:flex-none" disabled={ocupado} onClick={alUsar}>
          Usar este
        </Button>
      </div>
    </div>
  )
}

/** Ver un modelo antes de usarlo: la hoja como saldría, con los datos por llenar en amarillo */
export function VistaModelo({
  modelo, ocupado, alCerrar, alUsar,
}: {
  modelo: Modelo | null
  ocupado: boolean
  alCerrar: () => void
  alUsar: (m: Modelo) => void
}) {
  const [texto, setTexto] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!modelo) return
    api
      .get<{ texto: string }>(`/api/modelos/${modelo.clave}`)
      .then((r) => setTexto(r.texto))
      .catch((e: ErrorApi) => setError(e.message))
  }, [modelo])

  return (
    <Dialog open={Boolean(modelo)} onOpenChange={(a) => !a && alCerrar()}>
      <DialogContent className="flex max-h-[92dvh] flex-col sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl font-medium">{modelo?.nombre}</DialogTitle>
          <DialogDescription>{modelo?.cuando} Lo amarillo es lo que se llena con los datos del caso.</DialogDescription>
        </DialogHeader>
        <div className="@container -mx-1 min-h-0 flex-1 overflow-y-auto rounded-lg bg-muted/60 p-3 md:p-5">
          {texto ? (
            <Hoja texto={texto} />
          ) : error ? (
            <p className="text-destructive" role="alert">{error}</p>
          ) : (
            <p className="flex items-center gap-2 text-ink-soft">
              <Loader2 className="size-4 animate-spin" /> Abriendo el modelo…
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" size="grande" className="border-regla" onClick={alCerrar}>Cerrar</Button>
          <Button size="grande" disabled={ocupado || !modelo} onClick={() => modelo && alUsar(modelo)}>
            Usar este modelo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Los modelos que Papiniano ofrece en la conversación, y la opción de redactarlo sin modelo */
export function ModelosSugeridos({
  modelos, ocupado, alVer, alUsar, alSinModelo,
}: {
  modelos: Modelo[]
  ocupado: boolean
  alVer: (m: Modelo) => void
  alUsar: (m: Modelo) => void
  alSinModelo?: () => void
}) {
  return (
    <div className="space-y-2.5">
      <ul className="space-y-2.5">
        {modelos.map((m) => (
          <li key={m.clave}>
            <FichaModelo modelo={m} ocupado={ocupado} alVer={() => alVer(m)} alUsar={() => alUsar(m)} />
          </li>
        ))}
      </ul>
      {alSinModelo && (
        <Button variant="ghost" className="h-11 text-ink-soft" disabled={ocupado} onClick={alSinModelo}>
          Redactarlo sin modelo
        </Button>
      )}
    </div>
  )
}
