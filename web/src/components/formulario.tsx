import { useId, useState } from 'react'
import { ChevronDown, CircleMinus, CirclePlus } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { MATERIAS, type Bloque, type Campo, type Datos, type Listas } from '@/lib/plantillas'
import { cn } from '@/lib/utils'

const ROMANOS = ['I', 'II', 'III', 'IV', 'V', 'VI']
const campoClase = 'h-11 bg-background px-3 text-base md:text-base'

/** Un formulario de Redacción: tarjetas numeradas (I, II…) con sus campos. */
export function Formulario({
  bloques, datos, listas, cambiar,
}: {
  bloques: Bloque[]
  datos: Datos
  listas: Listas
  cambiar: (clave: string, valor: string | string[]) => void
}) {
  return (
    <div className="space-y-5">
      {bloques.map((b, i) => (
        <section key={b.titulo} className="rounded-2xl border border-papel-borde bg-card p-5 md:p-6">
          <div className="mb-5 flex items-center gap-3.5">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-marca font-heading text-[1.05rem] text-marca-texto">
              {ROMANOS[i]}
            </span>
            <div>
              <h2 className="font-heading text-[1.25rem] leading-tight font-medium text-ink">{b.titulo}</h2>
              <p className="text-[0.88rem] text-ink-soft">{b.sub}</p>
            </div>
          </div>
          <div className="space-y-4">
            {b.filas.map((fila, j) => {
              const visibles = fila.filter((c) => !(c.tipo === 'sala' && !String(datos.materia ?? '')))
              if (!visibles.length) return null
              return (
                <div key={j} className="flex flex-col gap-4 md:flex-row">
                  {visibles.map((c) => (
                    <div key={c.clave} className={cn('min-w-0', c.corto ? 'md:w-32 md:shrink-0' : 'md:flex-1')}>
                      <CampoFormulario campo={c} datos={datos} listas={listas} cambiar={cambiar} />
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

function Etiqueta({ id, campo, texto }: { id: string; campo: Campo; texto?: string }) {
  return (
    <Label htmlFor={id} className="mb-1.5 text-[0.9rem] text-ink-soft">
      {texto ?? campo.etiqueta}
      {campo.requerido && <span className="text-marca-texto" aria-hidden>*</span>}
    </Label>
  )
}

function CampoFormulario({
  campo, datos, listas, cambiar,
}: {
  campo: Campo
  datos: Datos
  listas: Listas
  cambiar: (clave: string, valor: string | string[]) => void
}) {
  const id = useId()
  const valor = datos[campo.clave]
  const texto = typeof valor === 'string' ? valor : ''
  const materia = String(datos.materia ?? '')
  const poner = (v: string) => cambiar(campo.clave, v)

  // asunto, tribunal y sala cambian con la materia elegida
  let tipo = campo.tipo ?? 'texto'
  let opciones: string[] = campo.opciones ? listas[campo.opciones] : []
  let filtrar = true
  let etiqueta = campo.etiqueta
  if (tipo === 'asunto') {
    if (materia === 'MATERIA INMOBILIARIA') [tipo, opciones, filtrar] = ['combo', listas.asuntos_inmobiliaria, false]
    else tipo = 'texto'
  } else if (tipo === 'tribunal') {
    if (materia === 'MATERIA INMOBILIARIA') [tipo, opciones] = ['combo', listas.tribunales_inmobiliaria]
    else if (materia === 'MATERIA CIVIL') [tipo, opciones] = ['combo', listas.tribunales_civil]
    else [tipo, etiqueta] = ['largo', campo.etiquetaOtra ?? campo.etiqueta]
  } else if (tipo === 'sala') {
    if (materia === 'MATERIA INMOBILIARIA') [tipo, opciones] = ['combo', listas.salas_inmobiliaria]
    else tipo = 'texto'
  } else if (tipo === 'combo') {
    filtrar = false
  }

  if (tipo === 'materia')
    return (
      <div>
        <p className="mb-1.5 text-[0.9rem] text-ink-soft">{campo.etiqueta}</p>
        <div role="radiogroup" aria-label={campo.etiqueta} className="inline-flex flex-wrap gap-2">
          {MATERIAS.map((m) => (
            <button
              key={m.nombre}
              type="button"
              role="radio"
              aria-checked={materia === m.valor}
              onClick={() => poner(m.valor)}
              className={cn(
                'h-10 rounded-full border px-4 text-[0.95rem] transition-colors',
                materia === m.valor ? 'border-marca bg-marca text-sobre-boton' : 'border-regla bg-background text-ink hover:border-marca',
              )}
            >
              {m.nombre}
            </button>
          ))}
        </div>
      </div>
    )

  if (tipo === 'lista') {
    const filas = Array.isArray(valor) && valor.length ? valor : ['']
    return (
      <div>
        <Etiqueta id={`${id}-0`} campo={campo} />
        <div className="space-y-2">
          {filas.map((v, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-6 shrink-0 text-right text-[0.9rem] text-ink-soft">{i + 1}-</span>
              <Input
                id={`${id}-${i}`}
                value={v}
                placeholder={campo.pista}
                onChange={(e) => cambiar(campo.clave, filas.map((x, k) => (k === i ? e.target.value : x)))}
                className={campoClase}
              />
              <button
                type="button"
                disabled={filas.length <= 1}
                onClick={() => cambiar(campo.clave, filas.filter((_, k) => k !== i))}
                className="flex size-10 shrink-0 items-center justify-center rounded-lg text-marca-texto hover:bg-muted disabled:opacity-30"
                aria-label={`Quitar ${i + 1}`}
              >
                <CircleMinus className="size-5" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => cambiar(campo.clave, [...filas, ''])}
            className="ml-8 flex items-center gap-1.5 rounded-md py-1.5 text-[0.92rem] text-marca-texto hover:underline"
          >
            <CirclePlus className="size-4" /> {campo.agregar ?? 'Agregar'}
          </button>
        </div>
      </div>
    )
  }

  if (tipo === 'combo')
    return (
      <div>
        <Etiqueta id={id} campo={campo} texto={etiqueta} />
        <Combo id={id} valor={texto} opciones={opciones} filtrar={filtrar} alCambiar={poner} />
      </div>
    )

  if (tipo === 'largo')
    return (
      <div>
        <Etiqueta id={id} campo={campo} texto={etiqueta} />
        <Textarea
          id={id}
          value={texto}
          placeholder={campo.pista}
          onChange={(e) => poner(e.target.value)}
          rows={2}
          className="min-h-11 bg-background px-3 py-2.5 text-base md:text-base"
        />
      </div>
    )

  // texto, fecha y cédula: las fechas y cédulas solo aceptan números y separadores
  const filtro = tipo === 'fecha' ? /[^0-9/]/g : tipo === 'cedula' ? /[^0-9-]/g : null
  return (
    <div>
      <Etiqueta id={id} campo={campo} texto={etiqueta} />
      <Input
        id={id}
        value={texto}
        placeholder={tipo === 'fecha' ? 'DD/MM/AAAA' : campo.pista}
        inputMode={filtro ? 'numeric' : undefined}
        onChange={(e) => poner(filtro ? e.target.value.replace(filtro, '') : e.target.value)}
        className={campoClase}
      />
    </div>
  )
}

const sinTildes = (t: string) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Campo con lista de opciones: se puede elegir una o escribir otra cosa */
function Combo({
  id, valor, opciones, filtrar, alCambiar,
}: {
  id: string
  valor: string
  opciones: string[]
  filtrar: boolean
  alCambiar: (v: string) => void
}) {
  const [abierto, setAbierto] = useState(false)
  const [activo, setActivo] = useState(-1)
  const q = sinTildes(valor.trim())
  const lista = filtrar && q && !opciones.includes(valor) ? opciones.filter((o) => sinTildes(o).includes(q)) : opciones

  function elegir(o: string) {
    alCambiar(o)
    setAbierto(false)
    setActivo(-1)
  }

  return (
    <div className="relative">
      <Input
        id={id}
        role="combobox"
        aria-expanded={abierto}
        aria-controls={`${id}-opciones`}
        aria-autocomplete="list"
        autoComplete="off"
        value={valor}
        onChange={(e) => {
          alCambiar(e.target.value)
          setAbierto(true)
          setActivo(-1)
        }}
        onFocus={() => setAbierto(true)}
        onBlur={() => setAbierto(false)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setAbierto(true)
            setActivo((a) => Math.min(a + 1, lista.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActivo((a) => Math.max(a - 1, 0))
          } else if (e.key === 'Enter' && abierto && activo >= 0) {
            e.preventDefault()
            elegir(lista[activo])
          } else if (e.key === 'Escape') {
            setAbierto(false)
          }
        }}
        placeholder="Elija de la lista o escriba"
        className={cn(campoClase, 'pr-10')}
      />
      <button
        type="button"
        tabIndex={-1}
        aria-label="Ver las opciones"
        onMouseDown={(e) => {
          e.preventDefault()
          setAbierto(!abierto)
          document.getElementById(id)?.focus()
        }}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-soft"
      >
        <ChevronDown className="size-4" />
      </button>
      {abierto && lista.length > 0 && (
        <ul
          id={`${id}-opciones`}
          role="listbox"
          className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-regla bg-popover py-1 shadow-lg"
        >
          {lista.map((o, i) => (
            <li
              key={o}
              role="option"
              aria-selected={o === valor}
              onMouseDown={(e) => {
                e.preventDefault()
                elegir(o)
              }}
              onMouseEnter={() => setActivo(i)}
              className={cn(
                'cursor-pointer px-3 py-2 text-[0.92rem] text-ink',
                i === activo && 'bg-muted',
                o === valor && 'font-bold text-marca-texto',
              )}
            >
              {o}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
