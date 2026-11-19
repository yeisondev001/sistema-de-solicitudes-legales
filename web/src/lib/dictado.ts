import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

/**
 * Dictado por voz con el reconocimiento que trae el navegador (Chrome, Edge, Safari): gratis y sin servicios
 * nuestros. Ojo: Chrome manda el audio a Google para pasarlo a texto; por eso se avisa que no se dicten nombres
 * ni cédulas, igual que al escribir (Ley 172-13). Firefox no lo tiene: el botón no sale.
 */
// el reconocimiento no está en los tipos de TypeScript
type Reconocedor = {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null
  onend: (() => void) | null
  onerror: ((e: { error: string }) => void) | null
}

function crear(): Reconocedor | null {
  const w = window as unknown as Record<string, new () => Reconocedor>
  const Clase = w.SpeechRecognition ?? w.webkitSpeechRecognition
  return Clase ? new Clase() : null
}

export const hayDictado = () =>
  typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

/** alAgregar recibe cada frase ya reconocida, para sumarla a lo que hay escrito */
export function useDictado(alAgregar: (frase: string) => void, alError?: (mensaje: string) => void) {
  const [escuchando, setEscuchando] = useState(false)
  const rec = useRef<Reconocedor | null>(null)
  const agregar = useRef(alAgregar)
  useEffect(() => {
    agregar.current = alAgregar
  })
  useEffect(() => () => rec.current?.stop(), [])

  function iniciar() {
    const r = crear()
    if (!r) return
    r.lang = 'es-DO'
    r.continuous = true
    r.interimResults = false
    r.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) agregar.current(e.results[i][0].transcript.trim())
      }
    }
    r.onend = () => setEscuchando(false)
    r.onerror = (e) => {
      setEscuchando(false)
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        alError?.('Permita el micrófono en el navegador (el candado junto a la dirección) y vuelva a intentarlo.')
      } else if (e.error !== 'no-speech' && e.error !== 'aborted') {
        alError?.('No se pudo usar el micrófono. Intente de nuevo.')
      }
    }
    rec.current = r
    r.start()
    setEscuchando(true)
  }

  function parar() {
    rec.current?.stop()
    setEscuchando(false)
  }

  return { disponible: hayDictado(), escuchando, alternar: () => (escuchando ? parar() : iniciar()) }
}

// ── Que Papiniano hable: las voces que trae el equipo (no se manda nada afuera) ─────

export const hayVoz = () => typeof window !== 'undefined' && 'speechSynthesis' in window

/** el texto sin las marcas de Markdown ni los [1] de las citas, para leerlo en voz alta */
function paraLeer(texto: string): string {
  return texto
    .replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, '')
    .replace(/\*\*|__|`|^#+\s*|^>\s?|^\s*[-*]\s+/gm, '')
    .replace(/\|/g, ' ')
    .replace(/\[([^\]]+)\]/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * La mejor voz en español: dominicana, latinoamericana o la de España, y antes las de Google o las «naturales»
 * (suenan mejor). Chrome carga las voces un momento después de abrir la página: si todavía no hay, se espera.
 */
function vozEspanol(voces: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  const es = voces.filter((v) => v.lang.toLowerCase().replace('_', '-').startsWith('es'))
  const puntos = (v: SpeechSynthesisVoice) => {
    const lang = v.lang.toLowerCase().replace('_', '-')
    const region = ['es-do', 'es-us', 'es-mx', 'es-419', 'es-es'].indexOf(lang)
    const calidad = /google|natural|online/i.test(v.name) ? 0 : 10
    return calidad + (region === -1 ? 9 : region)
  }
  return es.sort((a, b) => puntos(a) - puntos(b))[0]
}

function conVoces(hacer: (voces: SpeechSynthesisVoice[]) => void) {
  const s = window.speechSynthesis
  const voces = s.getVoices()
  if (voces.length) {
    hacer(voces)
    return
  }
  let hecho = false
  const listo = () => {
    if (hecho) return
    hecho = true
    s.removeEventListener('voiceschanged', listo)
    hacer(s.getVoices())
  }
  s.addEventListener('voiceschanged', listo)
  setTimeout(listo, 1500)   // algunos navegadores no avisan: se habla igual con lo que haya
}

/** Lee el texto en voz alta (corta lo que estaba leyendo). alTerminar avisa cuando acaba o se corta. */
export function hablar(texto: string, alTerminar?: () => void) {
  if (!hayVoz()) return
  const s = window.speechSynthesis
  s.cancel()
  conVoces((voces) => {
    const voz = vozEspanol(voces)
    if (!voz) {
      // leer español con una voz en inglés suena mal: mejor avisar
      toast.error('Este navegador no tiene una voz en español. Use Google Chrome o agregue una voz en español en '
        + 'la configuración de voz de su equipo (Windows: Configuración › Hora e idioma › Voz).')
      alTerminar?.()
      return
    }
    const frase = new SpeechSynthesisUtterance(paraLeer(texto))
    frase.voice = voz
    frase.lang = voz.lang
    frase.rate = 1
    frase.onend = () => alTerminar?.()
    frase.onerror = () => alTerminar?.()
    s.speak(frase)
  })
}

/** Si el equipo tiene alguna voz en español (si no, lee con acento de otro idioma) */
export function hayVozEspanol(): boolean {
  return hayVoz() && Boolean(vozEspanol(window.speechSynthesis.getVoices()))
}

export function callar() {
  if (hayVoz()) window.speechSynthesis.cancel()
}

/** Para un botón «Escuchar / Detener»: cuál texto se está leyendo */
export function useVoz() {
  const [leyendo, setLeyendo] = useState<string | null>(null)
  useEffect(() => () => callar(), [])
  return {
    disponible: hayVoz(),
    leyendo,
    alternar(clave: string, texto: string) {
      if (leyendo === clave) {
        callar()
        setLeyendo(null)
      } else {
        setLeyendo(clave)
        hablar(texto, () => setLeyendo((l) => (l === clave ? null : l)))
      }
    },
  }
}

const CLAVE_VOZ = 'papiniano.voz'

/**
 * «Que Papiniano me hable»: encendido, lee solo cada respuesta nueva (en el chat) y cada pregunta (en
 * Redacción). Se recuerda en este equipo y vale para las dos salas.
 */
export function useVozAutomatica() {
  const [encendida, setEncendida] = useState(() => {
    try {
      return localStorage.getItem(CLAVE_VOZ) === '1'
    } catch {
      return false
    }
  })
  useEffect(() => () => callar(), [])
  return {
    disponible: hayVoz(),
    encendida,
    alternar() {
      const nuevo = !encendida
      setEncendida(nuevo)
      if (!nuevo) callar()
      try {
        localStorage.setItem(CLAVE_VOZ, nuevo ? '1' : '0')
      } catch {
        // sin almacenamiento: vale mientras la página esté abierta
      }
    },
  }
}
