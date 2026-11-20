import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ExternalLink, Loader2, LogOut } from 'lucide-react'
import { toast } from 'sonner'
import { Logo } from '@/components/logo'
import { TituloSala } from '@/components/oficina'
import { Button } from '@/components/ui/button'
import { api, ErrorApi } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import { claseBotonPlan, InterruptorCiclo, TarjetaPlan } from '@/components/tarjeta-plan'
import { planes, PRUEBA_INICIAL } from '@/pages/inicio'

const NOMBRE_PLAN: Record<string, string> = {
  beta: 'Acceso completo', prueba: 'Prueba gratis', basico: 'Aspirante', activo: 'Abogado', vencido: 'Sin plan',
}
const PLAN_DE: Record<string, 'basico' | 'activo' | 'buffet'> = { Aspirante: 'basico', Abogado: 'activo', Buffet: 'buffet' }

/** Mi plan: elegir y pagar con Polar, ver el plan actual y administrar la suscripción (recibos, tarjeta, cancelar). */
export default function Plan({ soloPagar = false }: { soloPagar?: boolean }) {
  const { perfil, refrescar, salir } = useSesion()
  const [params] = useSearchParams()
  const [anual, setAnual] = useState(false)
  const [activo, setActivo] = useState<boolean | null>(null)
  const [enCurso, setEnCurso] = useState('')
  const navegar = useNavigate()
  const volvio = params.get('pago') === 'ok'
  // viene de «Elegir plan» de la página pública (?elegir=abogado): no se le vuelven a mostrar los planes, solo
  // «Abriendo el pago…» hasta que llega a Polar. Se guarda al abrir, porque enseguida se quita de la dirección.
  const [abriendo, setAbriendo] = useState(() => {
    const e = params.get('elegir')
    return e === 'aspirante' || e === 'abogado' || e === 'buffet'
      ? { plan: e, ciclo: params.get('ciclo') === 'anual' ? 'año' : 'mes' }
      : null
  })
  const yaIntentado = useRef(false)

  useEffect(() => {
    api.get<{ activo: boolean }>('/api/pagos').then((d) => setActivo(d.activo)).catch(() => setActivo(false))
  }, [])

  useEffect(() => {
    if (!activo || !abriendo || yaIntentado.current) return
    yaIntentado.current = true
    // sin ?elegir= en la dirección: si vuelve atrás desde Polar, queda en Mi plan y no lo manda otra vez al pago
    navegar('/plan', { replace: true })
    void ir('/api/pagos/pagar', abriendo, abriendo.plan === 'buffet' ? 'Buffet' : abriendo.plan === 'abogado' ? 'Abogado' : 'Aspirante')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activo, abriendo])

  // al volver de pagar, Polar tarda unos segundos en avisar: se vuelve a leer la cuenta hasta que cambie el plan
  useEffect(() => {
    if (!volvio) return
    let n = 0
    const t = setInterval(() => {
      refrescar()
      if (++n >= 15) clearInterval(t)
    }, 3000)
    return () => clearInterval(t)
  }, [volvio, refrescar])

  async function ir(ruta: string, cuerpo: unknown, clave: string) {
    setEnCurso(clave)
    try {
      const { url } = await api.post<{ url: string }>(ruta, cuerpo)
      window.location.href = url
    } catch (e) {
      toast.error(e instanceof ErrorApi ? e.message : 'No se pudo abrir el pago. Intente en un momento.')
      setEnCurso('')
      setAbriendo(null)   // si el pago no abrió, se le muestran los planes para que elija otra vez
    }
  }

  // mientras se abre el pago del plan que eligió en la página pública (si los pagos no están activos, la página normal)
  if (abriendo && activo !== false) {
    const nombre = abriendo.plan === 'buffet' ? 'Buffet' : abriendo.plan === 'abogado' ? 'Abogado' : 'Aspirante'
    const aviso = (
      <div role="status" aria-live="polite" className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-5 text-center">
        <Loader2 className="size-8 animate-spin text-marca-texto" aria-hidden />
        <p className="font-heading text-[1.6rem] leading-tight text-ink">Abriendo el pago del plan {nombre}…</p>
        <p className="text-ink-soft">Lo llevamos a la pantalla segura de Polar.</p>
      </div>
    )
    return soloPagar ? <div className="min-h-dvh bg-background">{aviso}</div> : aviso
  }

  const duenoDeOficina = !!perfil.oficina?.es_dueno
  const paga = perfil.plan === 'basico' || perfil.plan === 'activo'
  const titulo = soloPagar ? (perfil.plan === 'prueba' ? 'Su prueba gratis terminó' : 'Su plan terminó') : 'Mi plan'
  const sub = soloPagar
    ? 'Elija un plan para seguir. Sus documentos, expedientes y conversaciones están guardados.'
    : `Su plan actual: ${perfil.oficina ? 'Buffet' : (NOMBRE_PLAN[perfil.plan] ?? perfil.plan)}.`

  const contenido = (
    <div className="mx-auto max-w-5xl">
      <TituloSala titulo={titulo} sub={sub}>
        {soloPagar && (
          <Button variant="outline" onClick={salir}><LogOut /> Salir</Button>
        )}
      </TituloSala>

      {volvio && (
        <p className="mb-6 flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-4 font-bold text-emerald-900">
          <Loader2 className="size-5 animate-spin" /> Gracias. Estamos activando su plan; en unos segundos queda listo.
        </p>
      )}
      {activo === false && (
        <p className="mb-6 rounded-xl border border-papel-borde bg-card p-4 text-ink">
          El pago con tarjeta se activa muy pronto. Mientras tanto escríbanos a{' '}
          <a href="mailto:soportepapiniano@gmail.com" className="font-bold text-marca-texto underline">soportepapiniano@gmail.com</a>{' '}
          y le activamos su plan.
        </p>
      )}

      <section className="rounded-3xl bg-panel px-5 py-8 text-sobre-panel md:px-8 md:py-10">
        <div className="mb-8">
          <InterruptorCiclo anual={anual} setAnual={setAnual} />
        </div>
        <div className="grid gap-5 md:grid-cols-3">
          {planes(PRUEBA_INICIAL).filter((p) => !duenoDeOficina || p.nombre === 'Buffet').map((p) => {
            const plan = PLAN_DE[p.nombre]
            const esMio = plan === 'buffet' ? duenoDeOficina && perfil.plan === 'activo' : plan === perfil.plan && !perfil.oficina
            return (
              <TarjetaPlan
                key={p.nombre}
                p={p}
                anual={anual}
                accion={
                  <button
                    type="button"
                    className={claseBotonPlan(p.destacado)}
                    disabled={!activo || esMio || !!enCurso}
                    onClick={() => ir('/api/pagos/pagar', { plan: p.nombre.toLowerCase(), ciclo: anual ? 'año' : 'mes' }, p.nombre)}
                  >
                    {enCurso === p.nombre ? <Loader2 className="mx-auto size-5 animate-spin" /> : esMio ? 'Su plan actual' : `Elegir ${p.nombre}`}
                  </button>
                }
              />
            )
          })}
        </div>
      </section>

      {paga && !soloPagar && (
        <div className="mt-8 rounded-2xl border border-papel-borde bg-card p-6">
          <h2 className="font-heading text-[1.4rem] font-medium text-ink">Su suscripción</h2>
          <p className="mt-1 text-ink-soft">Vea sus recibos, cambie su tarjeta o cancele. Si cancela, conserva el acceso hasta el final del período pagado.</p>
          <Button className="mt-4" variant="outline" disabled={!!enCurso} onClick={() => ir('/api/pagos/portal', undefined, 'portal')}>
            {enCurso === 'portal' ? <Loader2 className="animate-spin" /> : <ExternalLink />} Administrar mi suscripción
          </Button>
        </div>
      )}
      <p className="mt-6 text-[0.9rem] text-ink-soft">
        Pago seguro con tarjeta a través de Polar, que cobra, factura y reembolsa. Reembolso dentro de los 7 días del primer pago; vea la{' '}
        <Link to="/reembolso" className="text-marca-texto underline">política de reembolso</Link>.
      </p>
    </div>
  )

  if (!soloPagar) return contenido
  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b border-papel-borde bg-background/95">
        <div className="mx-auto flex max-w-[1240px] items-center px-5 py-3.5 md:px-6">
          <Logo />
        </div>
      </header>
      <main className="px-5 py-10 md:px-6">{contenido}</main>
    </div>
  )
}
