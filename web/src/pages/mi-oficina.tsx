import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, FileText, Loader2, Lock, LogOut, UserPlus, X } from 'lucide-react'
import { toast } from 'sonner'
import { Cargando } from '@/components/cargando'
import { TituloSala } from '@/components/oficina'
import { Seccion } from '@/components/seccion'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ErrorApi } from '@/lib/api'
import { useSesion } from '@/lib/sesion'
import type { Invitacion, MiOficina, Modelo } from '@/lib/tipos'

interface Datos {
  oficina: MiOficina | null
  invitaciones: Invitacion[]
}

/** «2026-11-12» → «Hoy», «Ayer» o «12 nov» */
function ultimoUso(dia?: string | null) {
  if (!dia) return 'Todavía no consulta'
  const [a, m, d] = dia.split('-').map(Number)
  const fecha = new Date(a, m - 1, d)
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  const dias = Math.round((hoy.getTime() - fecha.getTime()) / 86400000)
  if (dias <= 0) return 'Hoy'
  if (dias === 1) return 'Ayer'
  return fecha.toLocaleDateString('es-DO', { day: 'numeric', month: 'short' })
}

/**
 * «Mi oficina» (plan Despacho): quiénes están y los modelos que comparten. El dueño agrega abogados por su
 * correo, ve cuánto usa cada uno (nunca lo que pregunta) y los puede quitar; los demás pueden salir.
 */
export default function MiOficinaPagina() {
  const { refrescar } = useSesion()
  const navegar = useNavigate()
  const [datos, setDatos] = useState<Datos | null>(null)
  const [error, setError] = useState('')
  const [compartidos, setCompartidos] = useState<Modelo[] | null>(null)
  const [porQuitar, setPorQuitar] = useState<{ id: number; nombre: string } | null>(null)
  const [saliendo, setSaliendo] = useState(false)

  const cargar = useCallback(() => {
    api.get<Datos>('/api/oficina').then(setDatos).catch((e: ErrorApi) => setError(e.message))
    api
      .get<{ propios: Modelo[]; oficina: Modelo[] }>('/api/modelos')
      .then((r) => setCompartidos([...r.propios.filter((m) => m.compartido), ...r.oficina]))
      .catch(() => setCompartidos([]))
  }, [])
  useEffect(cargar, [cargar])

  async function hacer(accion: () => Promise<unknown>, aviso: string) {
    try {
      await accion()
      toast.success(aviso)
      cargar()
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  async function salir() {
    try {
      await api.post('/api/oficina/salir')
      toast.success('Salió de la oficina. Todo lo suyo sigue en su cuenta.')
      refrescar()
      navegar('/', { replace: true })
    } catch (e) {
      toast.error((e as ErrorApi).message)
    }
  }

  const o = datos?.oficina
  // los correos que todavía no aceptan ya ocupan su asiento
  const ocupados = o ? o.abogados.length + o.pendientes.length : 0
  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-8 md:py-8">
      <TituloSala titulo="Mi oficina" sub={o ? `${o.nombre} · plan Despacho` : 'Plan Despacho: varios abogados, una sola factura.'} />
      {error ? (
        <p className="text-destructive" role="alert">{error}</p>
      ) : !datos ? (
        <Cargando que="Abriendo su oficina" />
      ) : !o ? (
        <div className="space-y-5">
          <InvitacionesOficina invitaciones={datos.invitaciones} alCambiar={cargar} />
          {!datos.invitaciones.length && (
            <Seccion titulo="No está en ninguna oficina">
              <p className="text-ink">
                Con el plan Despacho, varios abogados trabajan en una misma oficina y pagan una sola factura. Si su
                oficina lo quiere, escríbanos desde Contacto.
              </p>
            </Seccion>
          )}
        </div>
      ) : (
        <div className="space-y-5">
          <Seccion titulo="Abogados">
            <ul>
              {o.abogados.map((a) => (
                <li key={a.id} className="flex items-center gap-3 border-b border-papel-borde py-3 first:pt-0 last:border-b-0">
                  {/* en el celular, el uso baja debajo del nombre */}
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-6 gap-y-2">
                    <div className="min-w-[11rem] flex-1">
                      <p className="font-bold text-ink">
                        {a.nombre}
                        {a.dueno && <span className="font-normal text-ink-soft"> · dueño</span>}
                      </p>
                      {o.es_dueno && a.email && <p className="truncate text-[0.88rem] text-ink-soft">{a.email}</p>}
                    </div>
                    {o.es_dueno && (
                      <div className="flex gap-6 text-[0.92rem] text-ink-soft">
                        <div className="sm:w-32">
                          <span className="block text-[0.78rem] tracking-wide uppercase">Último uso</span>
                          {ultimoUso(a.ultimo)}
                        </div>
                        <div className="sm:w-36">
                          <span className="block text-[0.78rem] tracking-wide uppercase">Consultas del mes</span>
                          <span className="font-bold text-ink">{a.mes ?? 0}</span>
                        </div>
                      </div>
                    )}
                  </div>
                  {o.es_dueno && (
                    <div className="w-11 shrink-0">
                      {!a.dueno && (
                        <Button
                          variant="ghost"
                          size="icon-grande"
                          className="text-ink-soft"
                          aria-label={`Quitar a ${a.nombre} de la oficina`}
                          title="Quitar de la oficina"
                          onClick={() => setPorQuitar(a)}
                        >
                          <X />
                        </Button>
                      )}
                    </div>
                  )}
                </li>
              ))}
              {o.pendientes.map((email) => (
                <li key={email} className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-papel-borde py-3 last:border-b-0">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-bold text-ink">{email}</p>
                    <p className="text-[0.88rem] text-aviso-texto">Todavía no ha aceptado</p>
                  </div>
                  <Button
                    variant="ghost"
                    className="h-11 text-ink-soft"
                    onClick={() => hacer(() => api.post('/api/oficina/invitaciones/cancelar', { email }), `Ya no se espera a ${email}.`)}
                  >
                    Cancelar
                  </Button>
                </li>
              ))}
            </ul>
            {o.es_dueno && (
              <p className="mt-5 text-ink">
                <strong>Asientos:</strong> {ocupados} de {o.asientos} ocupados
                <span className="text-ink-soft"> · uno por abogado, usted incluido</span>
              </p>
            )}
            {o.es_dueno &&
              (ocupados < o.asientos ? (
                <Agregar alAgregar={(email) => hacer(() => api.post('/api/oficina/invitaciones', { email }), `Listo: cuando ${email} entre a Papiniano, verá la invitación.`)} />
              ) : (
                <p className="mt-2 text-ink-soft">
                  Para agregar a otro abogado, escríbanos desde Contacto y le sumamos un asiento.
                </p>
              ))}
            <p className="mt-4 flex gap-2 text-[0.9rem] text-ink-soft">
              <Lock className="mt-0.5 size-4 shrink-0" />
              {o.es_dueno
                ? 'Usted ve quién usa Papiniano y cuánto. Lo que cada abogado pregunta, sus documentos y sus escritos son solo suyos.'
                : 'El dueño ve cuántas consultas hace usted, no lo que pregunta. Sus conversaciones, documentos y escritos son solo suyos.'}
            </p>
          </Seccion>

          <Seccion titulo="Modelos de la oficina">
            {compartidos === null ? (
              <Cargando renglones={2} que="Buscando los modelos" />
            ) : compartidos.length ? (
              <ul>
                {compartidos.map((m) => (
                  <li key={m.clave} className="flex items-center gap-3 border-b border-papel-borde py-3 first:pt-0 last:border-b-0 last:pb-0">
                    <FileText className="size-5 shrink-0 text-marca-texto" />
                    <span className="min-w-0 flex-1 font-bold text-ink">{m.nombre}</span>
                    <span className="shrink-0 text-[0.88rem] text-ink-soft">{m.oficina ? `subió ${m.autor}` : 'subió usted'}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ink-soft">Todavía nadie comparte un modelo.</p>
            )}
            <p className="mt-4 text-[0.9rem] text-ink-soft">
              Para compartir uno de los suyos: en Papiniano abra «Modelos», edite el modelo y marque «Compartirlo con
              la oficina». Papiniano también se los sugiere a todos.
            </p>
          </Seccion>

          {!o.es_dueno && (
            <div>
              <Button variant="outline" size="grande" className="border-regla" onClick={() => setSaliendo(true)}>
                <LogOut /> Salir de la oficina
              </Button>
            </div>
          )}
        </div>
      )}

      <AlertDialog open={Boolean(porQuitar)} onOpenChange={(a) => !a && setPorQuitar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Quitar a {porQuitar?.nombre}?</AlertDialogTitle>
            <AlertDialogDescription>
              Sigue con su cuenta, sus conversaciones, documentos y modelos, pero ya no con el plan de la oficina. Sus
              modelos dejan de estar compartidos.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="peligro"
              size="grande"
              onClick={() => porQuitar && hacer(() => api.borrar(`/api/oficina/abogados/${porQuitar.id}`), `${porQuitar.nombre} ya no está en la oficina.`)}
            >
              Sí, quitar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={saliendo} onOpenChange={setSaliendo}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-xl font-medium">¿Salir de {o?.nombre}?</AlertDialogTitle>
            <AlertDialogDescription>
              Sigue con su cuenta, sus conversaciones, documentos y modelos, pero ya no con el plan de la oficina. Sus
              modelos dejan de estar compartidos.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel size="grande">Cancelar</AlertDialogCancel>
            <AlertDialogAction variant="peligro" size="grande" onClick={salir}>
              Sí, salir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

/** El dueño agrega a un abogado con su correo de Google */
function Agregar({ alAgregar }: { alAgregar: (email: string) => Promise<void> }) {
  const [email, setEmail] = useState('')
  const [agregando, setAgregando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setAgregando(true)
    await alAgregar(email.trim().toLowerCase())
    setAgregando(false)
    setEmail('')
  }

  return (
    <form onSubmit={enviar} className="mt-3 space-y-1.5">
      <Label htmlFor="agregar-abogado" className="text-[0.95rem] text-ink">Agregar un abogado</Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id="agregar-abogado"
          type="email"
          autoComplete="off"
          placeholder="correo@gmail.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="h-11 bg-background text-base sm:flex-1 md:text-base"
        />
        <Button type="submit" size="grande" disabled={agregando || !email.trim()}>
          {agregando ? <Loader2 className="animate-spin" /> : <UserPlus />} Agregar
        </Button>
      </div>
      <p className="text-[0.88rem] text-ink-soft">
        Use el correo con el que entra a Papiniano con Google. Al entrar, verá la invitación en su escritorio.
      </p>
    </form>
  )
}

/** Las oficinas que le piden unirse a este abogado: acepta o no. Va en el escritorio y en «Mi oficina». */
export function InvitacionesOficina({ invitaciones, alCambiar }: { invitaciones: Invitacion[]; alCambiar?: () => void }) {
  const { refrescar } = useSesion()
  const navegar = useNavigate()
  const [ocupado, setOcupado] = useState(false)

  async function responder(i: Invitacion, unirme: boolean) {
    setOcupado(true)
    try {
      await api.post(`/api/oficina/${unirme ? 'unirme' : 'rechazar'}/${i.id}`)
      if (unirme) {
        toast.success(`Ya está en ${i.nombre}.`)
        refrescar()
        navegar('/oficina')
      }
      alCambiar?.()
    } catch (e) {
      toast.error((e as ErrorApi).message)
    } finally {
      setOcupado(false)
    }
  }

  return invitaciones.map((i) => (
    <section key={i.id} className="rounded-2xl border-2 border-marca bg-card p-5 md:p-6">
      <div className="flex items-start gap-3">
        <Building2 className="mt-1 size-6 shrink-0 text-marca-texto" />
        <div className="space-y-2">
          <h2 className="font-heading text-[1.35rem] font-medium text-ink">{i.dueno} le pide unirse a «{i.nombre}»</h2>
          <p className="text-ink">
            Si se une, usa Papiniano con el plan de la oficina. El dueño verá cuántas consultas hace, no lo que
            pregunta: sus conversaciones, documentos y escritos siguen siendo solo suyos.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button size="grande" disabled={ocupado} onClick={() => responder(i, true)}>
              Unirme a la oficina
            </Button>
            <Button variant="outline" size="grande" className="border-regla" disabled={ocupado} onClick={() => responder(i, false)}>
              No, gracias
            </Button>
          </div>
        </div>
      </div>
    </section>
  ))
}
