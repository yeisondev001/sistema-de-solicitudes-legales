// Lo que devuelve la API de Python (servidor.py)

/** Colores de un tema de temas.py: INK, INK_SOFT, ACCENT… y si es oscuro */
export type Colores = Record<string, string> & { oscuro: boolean }

export interface Perfil {
  id: number
  usuario: string
  nombre: string
  es_admin: boolean
  email: string
  plan: 'beta' | 'prueba' | 'activo' | 'vencido'
  plantillas: boolean
  tema: string
  colores: Colores
  prueba: { dias: number; preguntas_hoy: number; tope: number } | null
}

export interface Entrada {
  primera_vez: boolean
  google: boolean
  pide_codigo: boolean
  falta_codigo: boolean
  dias_prueba: number
  colores: Colores
}

export interface Tema {
  clave: string
  nombre: string
  descripcion: string
  colores: Colores
}

export interface Conversacion {
  id: number
  titulo: string
  actualizada: number
}

export interface Fuente {
  id: number
  pagina: number
  texto: string
  extracto: string
  documento_id: number
  origen: 'boletin' | 'ley' | 'doctrina' | 'propio' | string
  titulo: string
  numero: string
  sala: string
  materia: string
  fuente_url: string
  referencia: string
}

export interface Turno {
  rol: 'usuario' | 'asistente'
  texto: string
  fuentes?: Fuente[]
  citadas?: number[]
  ia?: boolean
}

export interface Documento {
  id: number
  titulo: string
  numero: string
  sala: string
  materia: string
  fragmentos: number
}

export interface Audiencia {
  id: number
  dias: number
  fecha: string
  recurrente: string
  expediente: string
  tribunal: string
}
