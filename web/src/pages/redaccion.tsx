import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom'
import { Copy, FileDown, FilePen, FileText, Loader2, PencilLine, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { Cargando } from '@/components/cargando'
import { Formulario } from '@/components/formulario'
import { Historial } from '@/components/historial'
import { TituloSala } from '@/components/oficina'
import { Button } from '@/components/ui/button'
import { api, descargar, ErrorApi } from '@/lib/api'
import { FORMULARIOS, idCampo, type Datos, type Listas } from '@/lib/plantillas'
import { useSesion } from '@/lib/sesion'
import type { EntradaHistorial } from '@/lib/tipos'
import { cn } from '@/lib/utils'

interface Plantilla {
  clave: string
  nombre: string
  sub: string
  valores: Datos
  /** los campos obligatorios: [clave, nombre para el aviso] (los mismos que revisa redaccion.py) */
  requeridos: [string, string][]
}

type Origen = { numero: number; editandoId: number | null } | null

/**
 * Lo escrito en cada plantilla se guarda en este equipo (por cuenta): no se pierde al cambiar de sala,
 * al recargar ni si se apaga el celular. El Reporte puede venir del historial (para editarlo o copiarlo).
 */
const guardado: {
  inicial: { plantillas: Plantilla[]; listas: Listas } | null
  usuario: number | null
  datos: Record<string, Datos>
  origen: Origen
} = { inicial: null, usuario: null, datos: {}, origen: null }

const claveBorrador = (usuario: number) => `papiniano.redaccion.${usuario}`

function leerBorrador(usuario: number): { datos: Record<string, Datos>; origen: Origen } {
  try {
    const b = JSON.parse(localStorage.getItem(claveBorrador(usuario)) ?? 'null')
    if (b && typeof b.datos === 'object') return { datos: b.datos, origen: b.origen ?? null }
  } catch {
    // sin acceso al almacenamiento del navegador (ventana privada): se trabaja sin borrador
  }
  return { datos: {}, origen: null }
}

function guardarBorrador(usuario: number) {
  try {
    localStorage.setItem(claveBorrador(usuario), JSON.stringify({ datos: guardado.datos, origen: guardado.origen }))
  } catch {
    // sin almacenamiento: lo escrito queda mientras la app esté abierta
  }
}

const vacio = (v: string | string[] | undefined) => (Array.isArray(v) ? !v.some((x) => x.trim()) : !String(v ?? '').trim())

/** Las plantillas de solicitudes y el historial de reportes (solo cuentas con plantillas). */
export default function Redaccion() {
  const { clave = 'informe' } = useParams()
  const navegar = useNavigate()
  const { perfil } = useSesion()
  if (guardado.usuario !== perfil.id) {
    Object.assign(guardado, { usuario: perfil.id, ...leerBorrador(perfil.id) })
  }
  const [inicial, setInicial] = useState(guardado.inicial)
  const [datos, setDatos] = useState(guardado.datos)
  const [origen, setOrigen] = useState(guardado.origen)
  // los avisos de campos que faltan son de una plantilla: al cambiar a otra ya no se muestran
  const [avisos, setAvisos] = useState<{ de: string; campos: Record<string, string> }>({ de: '', campos: {} })
  const [generando, setGenerando] = useState<'docx' | 'pdf' | null>(null)
  const [cuantos, setCuantos] = useState<number | null>(null)
  const [error, setError] = useState('')

  function contarHistorial() {
    api.get<EntradaHistorial[]>('/api/historial').then((h) => setCuantos(h.length)).catch(() => {})
  }

  useEffect(() => {
    if (!guardado.inicial)
      api
        .get<{ plantillas: Plantilla[]; listas: Listas }>('/api/redaccion')
        .then((r) => {
          guardado.inicial = r
          setInicial(r)
        })
        .catch((e: ErrorApi) => setError(e.message))
    contarHistorial()
  }, [])

  const plantilla = inicial?.plantillas.find((p) => p.clave === clave)
  const form = plantilla ? (datos[clave] ?? plantilla.valores) : null
  const errores = avisos.de === clave ? avisos.campos : {}

  function poner(nuevos: Record<string, Datos>) {
    guardado.datos = nuevos
    setDatos(nuevos)
    guardarBorrador(perfil.id)
  }

  function cambiarOrigen(o: Origen) {
    guardado.origen = o
    setOrigen(o)
    guardarBorrador(perfil.id)
  }

  function cambiar(campo: string, valor: string | string[]) {
    if (!form) return
    poner({ ...datos, [clave]: { ...form, [campo]: valor } })
    // al escribir en un campo marcado, su aviso se va
    if (errores[campo]) {
      const resto = { ...errores }
      delete resto[campo]
      setAvisos({ de: clave, campos: resto })
    }
  }

  function enBlanco() {
    if (!plantilla) return
    poner({ ...datos, [clave]: plantilla.valores })
    if (clave === 'reporte') cambiarOrigen(null)
    setAvisos({ de: '', campos: {} })
  }

  /** Llena el Reporte de Audiencia con un expediente del historial */
  function abrirDesdeHistorial(e: EntradaHistorial, editar: boolean) {
    const base = inicial!.plantillas.find((p) => p.clave === 'reporte')!.valores
    const tieneDatos = e.datos && Object.keys(e.datos).length > 0
    const reporte: Datos = tieneDatos
      ? { ...base, ...e.datos }
      : {
          // guardado antes de existir "datos": lo que se pueda recuperar
          ...base,
          tribunal: e.tribunal, expediente: e.expediente, demandantes: e.recurrente,
          demandados: e.recurrido.split(',').map((x) => x.trim()).filter(Boolean),
          asunto: e.objeto, parcela: e.parcela, agrimensor: e.agrimensor, fallo: e.fallo,
          fecha_audiencia: e.fecha_audiencia, fecha_proxima: e.fecha_proxima,
        }
    poner({ ...datos, reporte })
    cambiarOrigen({ numero: e.numero, editandoId: editar ? e.id : null })
    navegar('/redaccion/reporte')
  }

  async function generar(formato: 'docx' | 'pdf') {
    if (!form || !plantilla) return
    // los obligatorios vacíos se marcan en el formulario y la pantalla va al primero
    const faltan = plantilla.requeridos.filter(([k]) => vacio(form[k]))
    if (faltan.length) {
      setAvisos({ de: clave, campos: Object.fromEntries(faltan.map(([k, nombre]) => [k, `Falta: ${nombre}`])) })
      toast.error(faltan.length === 1 ? 'Falta un campo: está marcado en rojo.' : `Faltan ${faltan.length} campos: están marcados en rojo.`)
      const primero = document.getElementById(idCampo(faltan[0][0]))
      primero?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      primero?.focus({ preventScroll: true })
      return
    }
    setGenerando(formato)
    try {
      const cabeceras = await descargar(`/api/redaccion/${clave}/${formato}`, {
        datos: form,
        editando_id: clave === 'reporte' ? (origen?.editandoId ?? null) : null,
      })
      const enHistorial = cabeceras.get('X-Historial')
      if (enHistorial === 'si') {
        toast.success('Documento descargado y guardado en el historial.')
        contarHistorial()
      } else if (enHistorial === 'no') {
        toast.warning('El documento se descargó, pero no se pudo guardar en el historial.')
      } else {
        toast.success('Documento descargado.')
      }
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setGenerando(null)
    }
  }

  const pestanas = [
    ...(inicial?.plantillas ?? []).map((p) => ({ clave: p.clave, nombre: p.nombre })),
    { clave: 'historial', nombre: 'Historial' },
  ]

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala
        titulo="Redacción"
        sub={clave === 'historial' ? 'Cada Reporte de Audiencia generado (Word o PDF) se guarda aquí.' : plantilla?.sub}
      />

      <nav aria-label="Plantillas" className="mb-6 flex flex-wrap gap-2">
        {pestanas.map((p) => (
          <NavLink
            key={p.clave}
            to={`/redaccion/${p.clave}`}
            className={cn(
              'flex h-11 shrink-0 items-center gap-2 rounded-full border px-4 text-[0.92rem] whitespace-nowrap transition-colors',
              p.clave === clave
                ? 'border-marca bg-marca font-bold text-sobre-boton'
                : 'border-regla bg-card text-ink hover:border-marca',
            )}
          >
            {p.nombre}
            {p.clave === 'historial' && cuantos !== null && (
              <span className="rounded-full bg-aviso px-2 text-[0.78rem] font-bold text-aviso-texto">{cuantos}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* lo que no está en las plantillas lo redacta Papiniano, en la hoja al lado de la conversación */}
      {clave !== 'historial' && (
        <div className="-mt-2 mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-regla bg-card px-4 py-3">
          <p className="min-w-56 flex-1 text-[0.92rem] text-ink">
            ¿Necesita un escrito que no está en las plantillas? Papiniano se lo redacta y usted le dice qué cambiar.
          </p>
          <Button variant="outline" className="h-11 border-regla" asChild>
            <Link to="/papiniano">
              <FilePen /> Escrito libre con Papiniano
            </Link>
          </Button>
        </div>
      )}

      {error ? (
        <p className="text-destructive">{error}</p>
      ) : !inicial ? (
        <Cargando renglones={4} que="Cargando las plantillas" />
      ) : clave === 'historial' ? (
        <Historial alAbrir={abrirDesdeHistorial} alCambiar={contarHistorial} />
      ) : !plantilla || !form ? (
        <p className="text-ink-soft">Esa plantilla no existe.</p>
      ) : (
        <>
          {clave === 'reporte' && origen && (
            <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-regla bg-aviso px-4 py-3 text-aviso-texto">
              {origen.editandoId ? <PencilLine className="size-5 shrink-0" /> : <Copy className="size-5 shrink-0" />}
              <p className="flex-1 text-[0.92rem]">
                {origen.editandoId
                  ? `Editando el No.${String(origen.numero).padStart(2, '0')} del historial. Al generar el documento se actualiza ese mismo expediente.`
                  : `Copia del No.${String(origen.numero).padStart(2, '0')} del historial. Cambie lo necesario; al generar se guarda como un expediente nuevo.`}
              </p>
            </div>
          )}

          <Formulario bloques={FORMULARIOS[clave]} datos={form} listas={inicial.listas} errores={errores} cambiar={cambiar} />

          <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Button size="grande" className="w-full sm:w-auto sm:min-w-56" disabled={Boolean(generando)} onClick={() => generar('docx')}>
              {generando === 'docx' ? <Loader2 className="animate-spin" /> : <FileText />} Generar en Word
            </Button>
            <Button
              size="grande"
              variant="outline"
              className="w-full border-regla sm:w-auto sm:min-w-56"
              disabled={Boolean(generando)}
              onClick={() => generar('pdf')}
            >
              {generando === 'pdf' ? <Loader2 className="animate-spin" /> : <FileDown />} Generar en PDF
            </Button>
          </div>
          <div className="mt-4 flex flex-col items-center gap-1 text-center">
            <p className="text-[0.88rem] text-ink-soft">
              Lo que escribe se guarda solo en este equipo. El documento se descarga en la carpeta Descargas.
            </p>
            <Button variant="ghost" className="h-11 text-ink-soft" onClick={enBlanco}>
              <RotateCcw /> Empezar esta plantilla en blanco
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
