import { useEffect, useState } from 'react'
import { NavLink, useNavigate, useParams } from 'react-router-dom'
import { Copy, FileDown, FileText, Loader2, PencilLine } from 'lucide-react'
import { toast } from 'sonner'
import { Formulario } from '@/components/formulario'
import { Historial } from '@/components/historial'
import { TituloSala } from '@/components/oficina'
import { Button } from '@/components/ui/button'
import { api, descargar, ErrorApi } from '@/lib/api'
import { FORMULARIOS, type Datos, type Listas } from '@/lib/plantillas'
import type { EntradaHistorial } from '@/lib/tipos'
import { cn } from '@/lib/utils'

interface Plantilla {
  clave: string
  nombre: string
  sub: string
  valores: Datos
}

/**
 * Lo escrito en cada plantilla se conserva mientras la app esté abierta, aunque se cambie de
 * sala, como en la app anterior. El Reporte puede venir del historial (para editarlo o copiarlo).
 */
const guardado: {
  inicial: { plantillas: Plantilla[]; listas: Listas } | null
  datos: Record<string, Datos>
  origen: { numero: number; editandoId: number | null } | null
} = { inicial: null, datos: {}, origen: null }

/** Las plantillas de solicitudes y el historial de reportes (solo cuentas con plantillas). */
export default function Redaccion() {
  const { clave = 'informe' } = useParams()
  const navegar = useNavigate()
  const [inicial, setInicial] = useState(guardado.inicial)
  const [datos, setDatos] = useState(guardado.datos)
  const [origen, setOrigen] = useState(guardado.origen)
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

  function poner(nuevos: Record<string, Datos>) {
    guardado.datos = nuevos
    setDatos(nuevos)
  }

  function cambiarOrigen(o: typeof guardado.origen) {
    guardado.origen = o
    setOrigen(o)
  }

  function cambiar(campo: string, valor: string | string[]) {
    if (form) poner({ ...datos, [clave]: { ...form, [campo]: valor } })
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
    if (!form) return
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
              'flex h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-[0.92rem] whitespace-nowrap transition-colors',
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

      {error ? (
        <p className="text-destructive">{error}</p>
      ) : !inicial ? (
        <p className="flex items-center gap-2 text-ink-soft">
          <Loader2 className="size-4 animate-spin" /> Cargando las plantillas…
        </p>
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
              <Button
                variant="ghost"
                className="h-9 text-aviso-texto hover:bg-black/5"
                onClick={() => {
                  poner({ ...datos, reporte: plantilla.valores })
                  cambiarOrigen(null)
                }}
              >
                Empezar uno en blanco
              </Button>
            </div>
          )}

          <Formulario bloques={FORMULARIOS[clave]} datos={form} listas={inicial.listas} cambiar={cambiar} />

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
          <p className="mt-3 text-center text-[0.85rem] text-ink-soft">
            El documento se descarga en su equipo (carpeta Descargas).
          </p>
        </>
      )}
    </div>
  )
}
