import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'

const SALAS = {
  expedientes: {
    titulo: 'Expedientes',
    texto: 'Una carpeta por cliente con sus documentos, conversaciones y plazos. Viene pronto.',
  },
  agenda: {
    titulo: 'Agenda',
    texto: 'Audiencias y vencimientos; el escritorio le avisará lo de la semana. Viene pronto.',
  },
  redaccion: {
    titulo: 'Redacción',
    texto: 'Las plantillas de solicitudes y el historial de reportes se están pasando a esta versión de la app.',
  },
}

/** Las salas que todavía no existen en esta versión */
export default function Pronto({ sala }: { sala: keyof typeof SALAS }) {
  const { titulo, texto } = SALAS[sala]
  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala titulo={titulo} />
      <Seccion titulo="Pronto">
        <p className="text-ink-soft">{texto}</p>
      </Seccion>
    </div>
  )
}
