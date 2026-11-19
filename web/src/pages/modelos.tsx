import { useNavigate } from 'react-router-dom'
import { ListaModelos } from '@/components/modelos'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import type { Modelo } from '@/lib/tipos'

/**
 * Sala «Modelos»: todas las plantillas de escritos, con un buscador. Al elegir una se abre Papiniano con ese
 * modelo en la hoja y pidiendo los datos del caso (ver asistente.tsx, `state.modelo`).
 */
export default function Modelos() {
  const navegar = useNavigate()

  function usar(m: Modelo) {
    navegar('/papiniano', { state: { modelo: { clave: m.clave, nombre: m.nombre } } })
  }

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala
        titulo="Modelos"
        sub="Busque el escrito que necesita, mírelo y elíjalo: Papiniano lo redacta con usted a partir de ese modelo."
      />
      <Seccion titulo="Modelos de escritos">
        <div className="space-y-4">
          <ListaModelos alUsar={usar} ocupado={false} />
        </div>
      </Seccion>
    </div>
  )
}
