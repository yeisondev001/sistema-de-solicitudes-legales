import { useEffect } from 'react'
import { CabeceraPublica, PiePublico } from '@/components/publico'
import { NOMBRE_APP } from '@/lib/tema'

/*
  Las páginas legales del pie (Lemon Squeezy las pide para aprobar la tienda).
  SON BORRADORES: los debe revisar un abogado antes de cobrar. Lo que falta va entre corchetes.
*/

const TITULAR = '[NOMBRE O RAZÓN SOCIAL DEL TITULAR]'
const CORREO = '[CORREO DE CONTACTO]'
const ACTUALIZADO = '[FECHA]'

type Pagina = 'terminos' | 'privacidad' | 'reembolso' | 'contacto'

const PAGINAS: Record<Pagina, { titulo: string; cuerpo: React.ReactNode }> = {
  terminos: {
    titulo: 'Términos de servicio',
    cuerpo: (
      <>
        <p>
          Estos términos regulan el uso de {NOMBRE_APP}, un programa en línea para abogados de la República Dominicana,
          ofrecido por {TITULAR}. Al crear una cuenta o usar el servicio, usted los acepta.
        </p>
        <h2>1. Qué es el servicio</h2>
        <p>
          {NOMBRE_APP} es una herramienta de apoyo: busca en sentencias publicadas en el Boletín Judicial, en leyes y en
          los documentos que usted sube, y un asistente de inteligencia artificial resume lo encontrado con sus citas.{' '}
          <strong>No es asesoría legal ni sustituye el criterio del abogado.</strong> Las respuestas pueden tener errores:
          usted debe verificar cada cita en la fuente oficial antes de usarla.
        </p>
        <h2>2. Su cuenta</h2>
        <p>
          La cuenta es personal. Usted cuida su acceso y es responsable de lo que se haga con ella. Puede entrar con su
          cuenta de Google o con usuario y contraseña.
        </p>
        <h2>3. Prueba gratis, planes y pagos</h2>
        <p>
          La prueba gratis dura los días indicados en la página de planes y tiene un máximo de consultas por día. Los
          planes pagos se cobran por adelantado cada mes a través de Lemon Squeezy, que actúa como vendedor y procesa el
          pago. Puede cancelar cuando quiera: el acceso sigue hasta el final del período pagado.
        </p>
        <h2>4. Uso aceptable</h2>
        <p>
          No use el servicio para fines ilegales, para copiar o revender su contenido de forma masiva, ni para intentar
          entrar a cuentas o datos de otras personas. No escriba en las consultas datos personales de sus clientes que no
          sean necesarios.
        </p>
        <h2>5. Sus documentos</h2>
        <p>
          Los documentos que usted sube siguen siendo suyos. Solo usted los ve, y se usan únicamente para buscarlos
          cuando usted consulta. Puede quitarlos cuando quiera desde la Biblioteca.
        </p>
        <h2>6. Contenido de terceros</h2>
        <p>
          Las sentencias y leyes provienen de publicaciones oficiales. Algunas obras comentadas se citan con su autoría y
          bajo su propia licencia.
        </p>
        <h2>7. Responsabilidad</h2>
        <p>
          El servicio se ofrece tal como está. {TITULAR} no responde por decisiones tomadas solo con base en las
          respuestas del asistente, ni por interrupciones del servicio ajenas a su control.
        </p>
        <h2>8. Cambios y ley aplicable</h2>
        <p>
          Estos términos pueden cambiar; los cambios importantes se avisarán por correo o en la app. Se rigen por las leyes
          de la República Dominicana.
        </p>
      </>
    ),
  },
  privacidad: {
    titulo: 'Política de privacidad',
    cuerpo: (
      <>
        <p>
          {TITULAR} trata sus datos personales conforme a la Ley 172-13 sobre protección integral de los datos personales
          de la República Dominicana. Aquí explicamos qué datos usamos y para qué.
        </p>
        <h2>Qué datos guardamos</h2>
        <ul>
          <li>Su nombre y correo (de su cuenta de Google o los que usted escribe al crear la cuenta).</li>
          <li>Sus conversaciones con el asistente, para que pueda volver a abrirlas.</li>
          <li>Los documentos que usted sube a su biblioteca.</li>
          <li>Cuántas consultas hace por día (para el límite de la prueba).</li>
          <li>Los datos del pago los guarda Lemon Squeezy; nosotros no vemos su tarjeta.</li>
        </ul>
        <h2>Para qué los usamos</h2>
        <p>
          Solo para darle el servicio: entrar a su cuenta, responder sus consultas, guardar su trabajo y cobrar su plan.
          No vendemos sus datos ni los usamos para publicidad.
        </p>
        <h2>Con quién se comparten</h2>
        <p>
          Para funcionar, el servicio usa proveedores que procesan datos por cuenta nuestra: el servidor y la base de datos
          (en Estados Unidos), los servicios de inteligencia artificial que leen la consulta y las fuentes encontradas para
          redactar la respuesta, Google para la entrada con su cuenta y Lemon Squeezy para los pagos. Por eso le pedimos
          no escribir en las consultas datos personales de sus clientes.
        </p>
        <h2>Cookies</h2>
        <p>Usamos una sola cookie, la que mantiene abierta su sesión. No usamos cookies de publicidad ni de seguimiento.</p>
        <h2>Sus derechos</h2>
        <p>
          Puede pedir ver, corregir o borrar sus datos, o cerrar su cuenta, escribiendo a {CORREO}. Las conversaciones y
          documentos los puede borrar usted mismo desde la app.
        </p>
      </>
    ),
  },
  reembolso: {
    titulo: 'Política de reembolso',
    cuerpo: (
      <>
        <p>
          Antes de pagar, puede usar {NOMBRE_APP} gratis durante la prueba, sin tarjeta, para ver si le sirve.
        </p>
        <h2>Cancelar</h2>
        <p>
          Puede cancelar su plan cuando quiera desde su cuenta. No se cobra el mes siguiente y conserva el acceso hasta el
          final del período que ya pagó.
        </p>
        <h2>Reembolsos</h2>
        <p>
          Si el servicio no le funcionó como esperaba, puede pedir el reembolso de su primer pago dentro de los [7] días
          siguientes, escribiendo a {CORREO}. Los pagos de meses siguientes no se reembolsan, salvo que el servicio haya
          estado sin funcionar por causa nuestra.
        </p>
        <p>Los reembolsos los procesa Lemon Squeezy al mismo medio de pago, en el plazo que indique su banco.</p>
      </>
    ),
  },
  contacto: {
    titulo: 'Contacto',
    cuerpo: (
      <>
        <p>¿Preguntas, el plan Despacho para varios abogados, o algo que no funciona? Escríbanos:</p>
        <ul>
          <li>Correo: {CORREO}</li>
          <li>WhatsApp: [NÚMERO]</li>
        </ul>
        <p>Respondemos en días laborables. {TITULAR}, Santo Domingo, República Dominicana.</p>
      </>
    ),
  },
}

/** Una página legal pública, con la cabecera y el pie de la recepción */
export default function Legal({ pagina }: { pagina: Pagina }) {
  const { titulo, cuerpo } = PAGINAS[pagina]
  useEffect(() => {
    document.title = `${titulo} · ${NOMBRE_APP}`
    window.scrollTo(0, 0)
    return () => {
      document.title = NOMBRE_APP
    }
  }, [titulo])

  return (
    <div className="min-h-dvh bg-background text-ink">
      <CabeceraPublica />
      <main className="mx-auto max-w-[760px] px-5 py-10 md:py-14">
        {pagina !== 'contacto' && (
          <p role="note" className="mb-6 rounded-lg border border-regla bg-aviso px-4 py-3 text-[0.9rem] text-aviso-texto">
            Borrador para revisión legal: complete lo que está entre corchetes y hágalo revisar antes de cobrar.
          </p>
        )}
        <h1 className="mb-2 font-heading text-[2.2rem] leading-tight font-medium">{titulo}</h1>
        {pagina !== 'contacto' && <p className="mb-8 text-[0.9rem] text-ink-soft">Última actualización: {ACTUALIZADO}</p>}
        <div className="lectura max-w-none [&_h2]:mt-8 [&_h2]:font-heading [&_h2]:text-[1.3rem]">{cuerpo}</div>
      </main>
      <PiePublico />
    </div>
  )
}
