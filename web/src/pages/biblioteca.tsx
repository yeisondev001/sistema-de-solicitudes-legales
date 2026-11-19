import { BookOpen, FileSearch, Gavel, Quote, ScanSearch, ShieldCheck } from 'lucide-react'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'

const ESTANTES = [
  { icono: Gavel, titulo: 'Sentencias de la Suprema Corte de Justicia', texto: 'Del Boletín Judicial; las nuevas se agregan solas cada mes.' },
  { icono: BookOpen, titulo: 'Leyes y reglamentos', texto: 'La Ley 108-05 y sus reglamentos, los códigos y otras leyes, artículo por artículo.' },
]

// Cómo trabaja Papiniano: una IA que responde con los textos de esta biblioteca, no de memoria.
// Sin prometer que nunca se equivoca: lo que se promete es que todo se puede comprobar.
const PASOS = [
  { icono: ScanSearch, titulo: 'Busca en la biblioteca', texto: 'Ante cada pregunta busca en las sentencias y en las leyes, por las palabras y por la idea.' },
  { icono: FileSearch, titulo: 'Lee lo que encontró', texto: 'Responde con esos textos, no de memoria. Si no encuentra nada que sirva, se lo dice en vez de inventar una respuesta.' },
  { icono: Quote, titulo: 'Cita cada afirmación', texto: 'Cada dato lleva su fuente entre corchetes: la sentencia o el artículo exacto de donde sale.' },
  { icono: ShieldCheck, titulo: 'Usted lo comprueba', texto: 'Un clic abre la página original del Boletín Judicial o de la ley, tal como es, para verificarla antes de usarla.' },
]

/** Qué hay en la biblioteca y cómo la usa Papiniano para responder. */
export default function Biblioteca() {
  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala titulo="Biblioteca" sub="Las sentencias y las leyes de donde Papiniano saca cada respuesta." />

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
          <div className="grid gap-4 md:grid-cols-2">
            {ESTANTES.map(({ icono: Icono, titulo, texto }) => (
              <div key={titulo} className="space-y-2 rounded-xl border border-papel-borde bg-background p-4">
                <Icono className="size-6 text-marca-texto" />
                <p className="font-bold text-ink">{titulo}</p>
                <p className="text-[0.92rem] text-ink-soft">{texto}</p>
              </div>
            ))}
          </div>
        </Seccion>
      </div>
    </div>
  )
}
