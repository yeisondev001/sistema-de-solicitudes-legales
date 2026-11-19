import { useEffect, useRef, useState } from 'react'

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

/** la mejor voz en español: dominicana, latinoamericana o la de España, en ese orden */
function vozEspanol(): SpeechSynthesisVoice | undefined {
  const voces = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith('es'))
  for (const preferida of ['es-do', 'es-us', 'es-mx', 'es-419', 'es-es']) {
    const v = voces.find((x) => x.lang.toLowerCase() === preferida)
    if (v) return v
  }
  return voces[0]
}

/** Lee el texto en voz alta (corta lo que estaba leyendo). alTerminar avisa cuando acaba o se corta. */
export function hablar(texto: string, alTerminar?: () => void) {
  if (!hayVoz()) return
  const s = window.speechSynthesis
  s.cancel()
  const frase = new SpeechSynthesisUtterance(paraLeer(texto))
  frase.lang = 'es-DO'
  const voz = vozEspanol()
  if (voz) frase.voice = voz
  frase.rate = 1
  frase.onend = () => alTerminar?.()
  frase.onerror = () => alTerminar?.()
  s.speak(frase)
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
