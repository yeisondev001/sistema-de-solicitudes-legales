import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen, CalendarDays, FileText, FolderClosed, Gavel, LibraryBig, PenLine, Scale, UserRound, type LucideIcon,
} from 'lucide-react'
import { Papiniano } from '@/components/papiniano'
import { Antetitulo, CabeceraPublica, PiePublico } from '@/components/publico'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { api } from '@/lib/api'
import type { Entrada } from '@/lib/tipos'
import { cn } from '@/lib/utils'

// La prueba gratis la decide el servidor (PRUEBA_DIAS y PRUEBA_PREGUNTAS_DIA en cuentas.py); esto se ve mientras responde
const PRUEBA_INICIAL = { dias: 5, preguntas: 20 }
type Prueba = typeof PRUEBA_INICIAL

/** Lo que Papiniano lee: solo lo que de verdad está cargado (jurisprudencia/leyes.py y el Boletín) */
const FUENTES: { icono: LucideIcon; titulo: string; texto: string; lista?: string[] }[] = [
  {
    icono: Gavel,
    titulo: 'Sentencias de la Suprema Corte',
    texto: 'Las del Boletín Judicial, de todas las salas y materias. Las nuevas se agregan solas cada mes.',
  },
  {
    icono: Scale,
    titulo: 'Códigos',
    texto: 'Artículo por artículo, con su texto oficial.',
    lista: ['Código Civil', 'Código de Procedimiento Civil', 'Código de Trabajo', 'Código Penal (nuevo y el anterior)'],
  },
  {
    icono: BookOpen,
    titulo: 'Leyes y reglamentos',
    texto: 'Registro inmobiliario y otras leyes que se usan a diario.',
    lista: ['Ley 108-05 de Registro Inmobiliario y sus reglamentos', 'Ley 189-11', 'Bien de Familia, Condominios, Urbanización', 'Municipios y medio ambiente'],
  },
  {
    icono: UserRound,
    titulo: 'Sus documentos',
    texto: 'Las sentencias, resoluciones y escritos que usted sube. Solo usted los ve, y Papiniano los busca junto con lo demás.',
  },
]

const SALAS: {
  icono: React.ComponentType<{ className?: string }>
  nombre: string
  texto: string
  pronto?: boolean
  retrato?: boolean
}[] = [
  {
    icono: Papiniano,
    nombre: 'Papiniano',
    retrato: true,
    texto: 'Su asistente. Le pregunta como a un colega y le responde con la jurisprudencia, la ley que aplica y su análisis. También saca las prestaciones laborales con las reglas del Código de Trabajo.',
  },
  { icono: LibraryBig, nombre: 'Biblioteca', texto: 'Todo lo que Papiniano lee, y sus propios documentos. Abre la página del PDF ahí mismo.' },
  { icono: FolderClosed, nombre: 'Expedientes', texto: 'Cada cliente con sus documentos, conversaciones, escritos y plazos, en una carpeta.', pronto: true },
  { icono: PenLine, nombre: 'Redacción', texto: 'Sus modelos de escritos y solicitudes, listos en Word o PDF.', pronto: true },
  { icono: CalendarDays, nombre: 'Agenda', texto: 'Audiencias y vencimientos. El escritorio le avisa lo que vence esta semana.', pronto: true },
]

// Los precios todavía no están decididos: se cambian aquí
const planes = (p: Prueba) => [
  {
    nombre: 'Prueba', precio: 'Gratis', periodo: `${p.dias} días`,
    puntos: [`${p.preguntas} consultas por día a Papiniano`, 'Toda la biblioteca', 'Sin tarjeta'], boton: 'Empezar prueba', a: '/entrar',
  },
  {
    nombre: 'Abogado', precio: '[PRECIO]', periodo: 'al mes', destacado: true,
    puntos: ['Papiniano sin límite diario', 'Sus documentos en el buscador', 'Expedientes y agenda, cuando estén listos'],
    boton: 'Elegir plan', a: '/entrar',
  },
  {
    nombre: 'Despacho', precio: '[PRECIO]', periodo: 'al mes',
    puntos: ['Todo lo del plan Abogado', 'Varios abogados y asistentes', 'Expedientes compartidos'], boton: 'Hablar con nosotros', a: '/contacto',
  },
]

const preguntas = (p: Prueba): [string, string][] => [
  ['¿Papiniano reemplaza al abogado?',
    'No. Es una herramienta de apoyo: busca, lee y resume por usted, pero el criterio es suyo. Por eso cada respuesta trae sus citas, para que las verifique en la fuente oficial antes de usarlas.'],
  ['¿De dónde salen las sentencias y las leyes?',
    'Las sentencias salen del Boletín Judicial de la Suprema Corte de Justicia y las leyes de sus textos oficiales. Cuando Papiniano cita algo, usted puede abrir la página exacta del PDF sin salir de la app.'],
  ['¿Se puede equivocar?',
    'Sí, como cualquier herramienta de inteligencia artificial. Por eso responde con lo que encontró en las fuentes y le muestra de dónde lo sacó. Los montos de prestaciones no los calcula la IA: salen de las fórmulas fijas del Código de Trabajo.'],
  ['¿Quién ve los documentos que subo?',
    'Solo usted. Se usan para buscar cuando usted pregunta, y los puede quitar cuando quiera. Le pedimos no escribir en las consultas datos personales de sus clientes.'],
  ['¿Qué pasa cuando termina la prueba gratis?',
    `La prueba dura ${p.dias} días y no pide tarjeta. Al terminar, elige un plan para seguir; si no, la cuenta queda en pausa y no se le cobra nada.`],
  ['¿Cómo se paga y cómo cancelo?',
    'Con tarjeta, a través de Lemon Squeezy. Puede cancelar cuando quiera desde su cuenta y conserva el acceso hasta el final del mes pagado.'],
  ['¿Por qué se llama Papiniano?',
    'Por Emilio Papiniano (siglo III), el jurista más respetado de Roma: cuando los grandes juristas no se ponían de acuerdo, la ley mandaba seguir su opinión.'],
  ['¿Funciona en el celular?', 'Sí. Funciona en el navegador de la computadora, la tableta y el celular, sin instalar nada.'],
]

/**
 * La página pública: lo primero que ve quien llega. La entrada es otra página (/entrar).
 * Los colores son siempre los de la marca, «Vino y madera».
 */
export default function Inicio() {
  const [prueba, setPrueba] = useState(PRUEBA_INICIAL)
  useEffect(() => {
    api
      .get<Entrada>('/api/entrada')
      .then((d) => setPrueba({ dias: d.dias_prueba, preguntas: d.preguntas_prueba }))
      .catch(() => {})
  }, [])

  return (
    <div className="min-h-dvh bg-background text-ink">
      <CabeceraPublica />

      <main>
        {/* lo principal */}
        <section className="mx-auto grid max-w-[1240px] items-center gap-12 px-5 pt-12 pb-16 md:px-6 md:pt-20 md:pb-24 lg:grid-cols-[1.05fr_1fr]">
          <div className="space-y-7">
            <Antetitulo>PARA ABOGADOS DE REPÚBLICA DOMINICANA</Antetitulo>
            <h1 className="font-heading text-[2.7rem] leading-[1.05] font-medium tracking-tight md:text-[4rem]">
              Todo su trabajo, en una sola oficina.
            </h1>
            <p className="max-w-[34rem] text-lg leading-relaxed text-ink-soft md:text-[1.25rem]">
              Pregúntele a Papiniano, su asistente, como a un colega: le responde con las sentencias de la Suprema Corte y
              las leyes, y le muestra la página exacta de cada cita.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Link to="/entrar" className="rounded-lg bg-boton px-6 py-4 text-[1.05rem] font-bold text-sobre-boton hover:bg-boton/90">
                Empiece gratis
              </Link>
              <a href="#como" className="rounded-lg border border-regla bg-card px-6 py-4 text-[1.05rem] font-bold text-ink hover:border-marca">
                Ver cómo funciona
              </a>
            </div>
            <p className="text-[0.92rem] text-ink-soft">{prueba.dias} días gratis, sin tarjeta. Entra con su cuenta de Gmail.</p>
          </div>
          <EjemploRespuesta />
        </section>

        {/* qué lee */}
        <section id="fuentes" className="scroll-mt-20 border-y border-papel-borde bg-card">
          <div className="mx-auto max-w-[1240px] space-y-10 px-5 py-16 md:px-6 md:py-20">
            <Encabezado antetitulo="QUÉ LEE POR USTED" titulo="El derecho dominicano que usted consulta todos los días, en una sola pregunta." />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {FUENTES.map(({ icono: Icono, titulo, texto, lista }) => (
                <div key={titulo} className="space-y-3 rounded-xl border border-papel-borde bg-background p-6">
                  <Icono className="size-7 text-marca-texto" />
                  <h3 className="font-heading text-[1.3rem] font-semibold">{titulo}</h3>
                  <p className="leading-relaxed text-ink-soft">{texto}</p>
                  {lista && (
                    <ul className="space-y-1.5 border-t border-papel-borde pt-3 text-[0.92rem] text-ink">
                      {lista.map((x) => <li key={x}>{x}</li>)}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* qué hay adentro */}
        <section id="salas" className="mx-auto max-w-[1240px] scroll-mt-20 space-y-10 px-5 py-16 md:px-6 md:py-20">
          <Encabezado antetitulo="QUÉ HAY ADENTRO" titulo="Cada sala de su oficina, a un clic." />
          <div className="grid gap-5 sm:grid-cols-2">
            {SALAS.filter((s) => !s.pronto).map(({ icono: Icono, nombre, texto, retrato }) => (
              <div key={nombre} className="space-y-2.5 rounded-xl border border-papel-borde bg-card p-6">
                <div className="flex items-center justify-between gap-3">
                  {retrato ? (
                    <Icono className="size-[46px]" />
                  ) : (
                    <span className="flex size-[46px] items-center justify-center rounded-[9px] bg-panel text-[#F1E8DA]">
                      <Icono className="size-[22px]" />
                    </span>
                  )}
                </div>
                <h3 className="font-heading text-[1.4rem] font-semibold">{nombre}</h3>
                <p className="leading-relaxed text-ink-soft">{texto}</p>
              </div>
            ))}
          </div>
          <p className="text-[1.05rem] text-ink-soft">
            <strong className="text-ink">Muy pronto, en la misma oficina:</strong> Expedientes (una carpeta por cliente),
            Redacción de escritos y la Agenda de audiencias.
          </p>
        </section>

        {/* cómo funciona */}
        <section id="como" className="scroll-mt-20 border-y border-papel-borde bg-card">
          <div className="mx-auto max-w-[1240px] space-y-10 px-5 py-16 md:px-6 md:py-20">
            <Encabezado antetitulo="CÓMO FUNCIONA" titulo="Pregunte como a un colega. Verifique cada cita." />
            <ol className="grid gap-5 md:grid-cols-3">
              {[
                ['Usted pregunta', 'En sus palabras, o por número de sentencia, expediente o artículo.'],
                ['Él busca y lee', 'Por palabras y por significado en las sentencias, los códigos, las leyes y sus documentos.'],
                ['Le responde con citas', 'Lo que dice la jurisprudencia, la ley y su análisis. Cada cita abre la página del PDF oficial.'],
              ].map(([titulo, texto], i) => (
                <li key={titulo} className="space-y-3 rounded-xl border border-papel-borde bg-background p-6">
                  <span className="flex size-10 items-center justify-center rounded-full bg-boton font-bold text-sobre-boton">{i + 1}</span>
                  <h3 className="font-heading text-[1.3rem] font-semibold">{titulo}</h3>
                  <p className="leading-relaxed text-ink-soft">{texto}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* planes */}
        <section id="planes" className="scroll-mt-20 bg-panel text-sobre-panel">
          <div className="mx-auto max-w-[1240px] space-y-10 px-5 py-16 md:px-6 md:py-20">
            <Encabezado antetitulo="PLANES" titulo="Empiece gratis. Pague cuando le sirva." claro />
            <div className="grid gap-5 md:grid-cols-3">
              {planes(prueba).map((p) => (
                <div
                  key={p.nombre}
                  className={cn('flex flex-col gap-3.5 rounded-2xl p-7', p.destacado ? 'border-2 border-[#F1E8DA] bg-[#4A3527]' : 'border border-[#6B5442]')}
                >
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-heading text-[1.75rem] font-medium">{p.nombre}</h3>
                    {p.destacado && (
                      <span className="shrink-0 rounded-full bg-[#F1E8DA] px-3 py-1 text-[0.8rem] font-bold whitespace-nowrap text-[#7A1F2B]">Recomendado</span>
                    )}
                  </div>
                  <p className="text-[2.1rem] font-bold">
                    {p.precio} <span className="text-base font-normal text-[#E2C9A8]">{p.periodo}</span>
                  </p>
                  <ul className="list-disc space-y-2 pl-5 text-[#F1E8DA]">
                    {p.puntos.map((x) => <li key={x}>{x}</li>)}
                  </ul>
                  <Link
                    to={p.a}
                    className={cn(
                      'mt-auto rounded-lg border border-[#F1E8DA] px-4 py-3.5 text-center font-bold',
                      p.destacado ? 'bg-[#7A1F2B] text-white hover:bg-[#8C2A36]' : 'text-[#F8F4EC] hover:bg-white/10',
                    )}
                  >
                    {p.boton}
                  </Link>
                </div>
              ))}
            </div>
            <p className="text-[0.95rem] text-[#E2C9A8]">Pago seguro con tarjeta a través de Lemon Squeezy. Cancele cuando quiera desde su cuenta.</p>
          </div>
        </section>

        {/* preguntas frecuentes */}
        <section id="preguntas" className="mx-auto grid max-w-[1240px] scroll-mt-20 gap-10 px-5 py-16 md:px-6 md:py-20 lg:grid-cols-[1fr_1.6fr]">
          <div className="space-y-3">
            <Encabezado antetitulo="PREGUNTAS FRECUENTES" titulo="Lo que preguntan los abogados antes de empezar." />
            <p className="text-ink-soft">
              ¿Otra duda? <Link to="/contacto" className="font-bold text-marca-texto hover:underline">Escríbanos</Link>.
            </p>
          </div>
          <Accordion type="single" collapsible className="rounded-2xl border border-papel-borde bg-card px-5 md:px-6">
            {preguntas(prueba).map(([p, r]) => (
              <AccordionItem key={p} value={p} className="border-papel-borde">
                <AccordionTrigger className="py-5 text-left text-[1.05rem] font-bold text-ink hover:no-underline">{p}</AccordionTrigger>
                <AccordionContent className="pb-5 text-base leading-relaxed text-ink-soft">{r}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>

        {/* el último empujón */}
        <section className="px-5 pb-16 md:px-6 md:pb-20">
          <div className="mx-auto flex max-w-[1240px] flex-col items-start justify-between gap-6 rounded-2xl bg-boton px-7 py-10 text-sobre-boton md:flex-row md:items-center md:px-12">
            <div className="space-y-2">
              <h2 className="font-heading text-[2rem] leading-tight font-medium">Pruébelo con su próximo caso.</h2>
              <p className="text-[1.05rem] opacity-90">{prueba.dias} días gratis. Sin tarjeta. Entra con su cuenta de Gmail.</p>
            </div>
            <Link to="/entrar" className="shrink-0 rounded-lg bg-card px-6 py-4 text-[1.05rem] font-bold text-marca-texto hover:bg-background">
              Empiece gratis
            </Link>
          </div>
        </section>
      </main>

      <PiePublico />
    </div>
  )
}

function Encabezado({ antetitulo, titulo, claro = false }: { antetitulo: string; titulo: string; claro?: boolean }) {
  return (
    <div className="max-w-[760px] space-y-2.5">
      <Antetitulo claro={claro}>{antetitulo}</Antetitulo>
      <h2 className="font-heading text-[2rem] leading-tight font-medium md:text-[2.6rem]">{titulo}</h2>
    </div>
  )
}

/** Cómo se ve una respuesta adentro (ilustración, no es una consulta real) */
function EjemploRespuesta() {
  return (
    <div aria-hidden="true" className="space-y-3.5 rounded-2xl border border-papel-borde bg-card p-5 shadow-[0_24px_60px_-20px_color-mix(in_oklab,var(--t-ink)_25%,transparent)] md:p-6">
      <div className="flex items-center gap-2.5 border-b border-papel-borde pb-3.5">
        <Papiniano className="size-9" decorativo />
        <span className="font-heading text-lg font-medium">Papiniano</span>
        <span className="text-[0.85rem] text-ink-soft">· su asistente</span>
      </div>
      <p className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-panel px-4 py-3 text-sobre-panel">
        ¿Qué pasa si se aprobó un deslinde sin citar a los colindantes?
      </p>
      <div className="flex flex-wrap gap-2 text-[0.8rem] text-ink-soft">
        {['Buscó en las sentencias y las leyes', 'Leyó 3 sentencias', '1 reglamento'].map((t) => (
          <span key={t} className="rounded-full bg-[#F1E6DE] px-3 py-1">{t}</span>
        ))}
      </div>
      <div className="space-y-3 rounded-2xl rounded-tl-sm border border-papel-borde bg-background p-5">
        <p className="font-heading text-[1.05rem] leading-relaxed">
          La falta de citación de los colindantes puede llevar a anular el deslinde, porque afecta su derecho de defensa
          {[1, 2].map((n) => (
            <span key={n} className="ml-1.5 rounded bg-[#F1E6DE] px-1.5 py-px font-sans text-[0.8rem] font-bold text-roble">{n}</span>
          ))}
        </p>
        <p className="text-[0.8rem] font-bold tracking-[0.12em] text-marca-texto">LO QUE DICE LA JURISPRUDENCIA · ANÁLISIS</p>
        <p className="text-ink-soft">El criterio de las sentencias, cómo aplica a su caso, los argumentos y los riesgos.</p>
        <div className="flex items-start gap-3 rounded-lg border border-papel-borde bg-card p-3">
          <FileText className="mt-0.5 size-5 shrink-0 text-marca-texto" />
          <div className="text-[0.88rem]">
            <p className="font-bold text-ink">[1] Sentencia de la Tercera Sala — Boletín Judicial, pág. …</p>
            <p className="text-ink-soft">Ver la página aquí · Abrir en el Boletín Judicial</p>
          </div>
        </div>
      </div>
    </div>
  )
}
