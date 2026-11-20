// Lo que devuelve la API de Python (servidor.py)

/** Colores de un tema de temas.py: INK, INK_SOFT, ACCENT… y si es oscuro */
export type Colores = Record<string, string> & { oscuro: boolean }

export interface Perfil {
  id: number
  usuario: string
  nombre: string
  es_admin: boolean
  email: string
  plan: 'beta' | 'prueba' | 'basico' | 'activo' | 'vencido'
  plantillas: boolean
  tema: string
  letra: 'normal' | 'grande' | 'muy_grande'
  colores: Colores
  /** sus propios modelos y documentos: todos los planes menos el Aspirante */
  propios: boolean
  prueba: { dias: number; preguntas_hoy: number; tope: number } | null
  /** en el plan Aspirante: las consultas de hoy y el máximo por día */
  basico: { preguntas_hoy: number; tope: number } | null
  /** su oficina del plan Buffet (el plan de la cuenta es el de la oficina) */
  oficina: { id: number; nombre: string; es_dueno: boolean } | null
  /** la prueba terminó o el plan venció: solo puede ver la pantalla de pago */
  por_pagar: boolean
  /** aceptó recibir novedades y promociones por correo (la casilla al entrar o Mi cuenta) */
  promociones: boolean
}

/** La oficina vista desde adentro: el dueño ve además el uso de cada abogado y los correos que agregó */
export interface MiOficina {
  id: number
  nombre: string
  plan: 'activo' | 'vencido'
  es_dueno: boolean
  /** los que paga la oficina: uno por abogado, el dueño incluido */
  asientos: number
  abogados: {
    id: number
    nombre: string
    dueno: boolean
    /** solo para el dueño */
    email?: string
    ultimo?: string | null
    mes?: number
  }[]
  /** correos que agregó el dueño y todavía no aceptan */
  pendientes: string[]
}

/** Una oficina que agregó a este abogado y espera que acepte */
export interface Invitacion {
  id: number
  nombre: string
  dueno: string
}

/** Una oficina en el panel del administrador */
export interface OficinaAdmin {
  id: number
  nombre: string
  plan: 'activo' | 'vencido'
  asientos: number
  dueno_id: number
  dueno: string
  abogados: number
}

export interface Entrada {
  primera_vez: boolean
  google: boolean
  pide_codigo: boolean
  falta_codigo: boolean
  dias_prueba: number
  preguntas_prueba: number
  preguntas_basico: number
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
  /** lo subió el abogado: solo lo ve él (y su oficina, si lo comparte) */
  propio?: boolean
  /** uno de los suyos que comparte con su oficina */
  compartido?: boolean
  /** lo compartió un colega de su oficina: lo puede usar, no cambiar */
  oficina?: boolean
  autor?: string
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
  oficina_id: number | null
  /** nombre de su oficina; si tiene, el plan que vale es el de la oficina */
  oficina: string
}

export interface Audiencia {
  id: number
  dias: number
  fecha: string
  recurrente: string
  expediente: string
  tribunal: string
}

/** Quien lleva un expediente o una fecha: el abogado o un colega de su oficina */
export interface Responsable {
  id: number
  nombre: string
}

export type TipoFecha = 'audiencia' | 'plazo' | 'reunion' | 'otro'

/** Una fecha de la agenda: audiencia, plazo o reunión, de un expediente o suelta (fecha AAAA-MM-DD, hora HH:MM o vacía) */
export interface Fecha {
  id: number
  tipo: TipoFecha
  titulo: string
  fecha: string
  hora: string
  lugar: string
  notas: string
  responsable: Responsable | null
  de_oficina: boolean
  /** en la agenda: el expediente al que pertenece */
  expediente?: { id: number; cliente: string; asunto: string } | null
}

/** Un expediente en la lista: el caso y su próxima fecha */
export interface ExpedienteResumen {
  id: number
  cliente: string
  asunto: string
  numero: string
  tribunal: string
  contraparte: string
  estado: 'activo' | 'cerrado'
  responsable: Responsable | null
  /** es de la oficina (plan Buffet): lo ven todos sus abogados */
  de_oficina: boolean
  creado: number
  actualizado: number
  proxima: { fecha: string; hora: string; tipo: TipoFecha; titulo: string } | null
}

/** Un expediente por dentro: sus fechas, y las conversaciones y documentos que el abogado guardó en él */
export interface Expediente extends Omit<ExpedienteResumen, 'proxima'> {
  notas: string
  fechas: Fecha[]
  conversaciones: { id: number; titulo: string; actualizada: number; con_escrito: boolean }[]
  documentos: { id: number; nombre: string }[]
}
