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
  letra: 'normal' | 'grande' | 'muy_grande'
  colores: Colores
  prueba: { dias: number; preguntas_hoy: number; tope: number } | null
}

export interface Entrada {
  primera_vez: boolean
  google: boolean
  pide_codigo: boolean
  falta_codigo: boolean
  dias_prueba: number
  preguntas_prueba: number
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
  /** en esta respuesta Papiniano escribió o cambió el escrito de al lado */
  escrito?: 'nuevo' | 'cambiado'
  /** los modelos que Papiniano ofrece para el escrito que le pidieron (ver modelos/ en el servidor) */
  modelos?: Modelo[]
  /** lo que pidió el abogado, para redactarlo sin modelo si no quiere ninguno */
  pedido?: string
  /** puso un modelo en la hoja: se le piden los datos por llenar */
  pedir_datos?: boolean
}

/** Un modelo de escrito: un escrito real convertido en formato, sin datos del caso */
export interface Modelo {
  clave: string
  nombre: string
  grupo: string
  materia: string
  tribunal: string
  /** en qué caso se usa */
  cuando: string
  /** lo subió el abogado: solo lo ve él */
  propio?: boolean
}

/** El escrito de una conversación (texto simple; ver lib/escrito.ts) */
export interface Escrito {
  texto: string
  /** si hay una versión anterior a la que volver */
  deshacer: boolean
}

export interface Documento {
  id: number
  titulo: string
  numero: string
  sala: string
  materia: string
  fragmentos: number
}

/** Un Reporte de Audiencia guardado en el historial de expedientes */
export interface EntradaHistorial {
  id: number
  numero: number
  tribunal: string
  fecha_audiencia: string
  expediente: string
  recurrente: string
  recurrido: string
  agrimensor: string
  objeto: string
  parcela: string
  fallo: string
  fecha_proxima: string
  datos: Record<string, string | string[]>
}

export interface Usuario {
  id: number
  usuario: string
  nombre: string
  es_admin: boolean
  activo: boolean
  email: string
  plan: Perfil['plan']
  prueba_hasta: number | null
  plantillas: boolean
}

export interface Audiencia {
  id: number
  dias: number
  fecha: string
  recurrente: string
  expediente: string
  tribunal: string
}
