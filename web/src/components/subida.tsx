import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { ErrorApi, subirDocumento } from '@/lib/api'

const MAX_MB = 20

/**
 * Subir documentos propios al buscador (PDF digital o Word). Devuelve la función que abre el
 * selector de archivos y el campo escondido que hay que poner en la pantalla.
 */
export function useSubida(alTerminar?: () => void) {
  const campo = useRef<HTMLInputElement>(null)
  const [subiendo, setSubiendo] = useState(0)

  async function subir(archivos: File[]) {
    for (const archivo of archivos) {
      if (archivo.size > MAX_MB * 1024 * 1024) {
        toast.error(`«${archivo.name}» pesa más de ${MAX_MB} MB.`)
        continue
      }
      setSubiendo((n) => n + 1)
      const aviso = toast.loading(`Leyendo «${archivo.name}»…`)
      try {
        const r = await subirDocumento(archivo)
        toast.success(`«${r.titulo}» agregado al buscador${r.numero ? ` — ${r.numero}` : ''} (${r.paginas} pág.).`, { id: aviso })
      } catch (e) {
        toast.error((e as ErrorApi).message, { id: aviso })
      } finally {
        setSubiendo((n) => n - 1)
      }
    }
    alTerminar?.()
  }

  const entrada = (
    <input
      ref={campo}
      type="file"
      multiple
      accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      className="hidden"
      onChange={(e) => {
        const archivos = [...(e.target.files ?? [])]
        e.target.value = ''
        if (archivos.length) subir(archivos)
      }}
    />
  )

  return { abrir: () => campo.current?.click(), entrada, subiendo: subiendo > 0 }
}
