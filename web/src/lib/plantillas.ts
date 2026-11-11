// Los formularios de Redacción: qué campos lleva cada plantilla y cómo se agrupan.
// Los valores iniciales, los campos obligatorios y el documento salen de redaccion.py.

export type Listas = Record<
  | 'tribunales_inmobiliaria'
  | 'tribunales_civil'
  | 'salas_inmobiliaria'
  | 'asuntos_inmobiliaria'
  | 'tipos_audiencia_provincial'
  | 'reclamantes_saneamiento',
  string[]
>

export type Datos = Record<string, string | string[]>

/**
 * texto · largo (varios renglones) · fecha (DD/MM/AAAA) · cedula · lista (anexos, demandados)
 * materia · y los que cambian con la materia: asunto, tribunal y sala · combo (lista fija con opciones)
 */
export type TipoCampo = 'texto' | 'largo' | 'fecha' | 'cedula' | 'lista' | 'materia' | 'asunto' | 'tribunal' | 'sala' | 'combo'

export interface Campo {
  clave: string
  etiqueta: string
  tipo?: TipoCampo
  requerido?: boolean
  pista?: string
  /** para combo: de qué lista salen las opciones */
  opciones?: keyof Listas
  /** campo angosto (iniciales, salón…) */
  corto?: boolean
  /** para lista: el texto del botón de agregar */
  agregar?: string
  /** para tribunal sin materia elegida */
  etiquetaOtra?: string
}

export interface Bloque {
  titulo: string
  sub: string
  /** cada fila va en una línea; en el celular, uno debajo del otro */
  filas: Campo[][]
}

const firma = (cc = false): Bloque => ({
  titulo: 'Firma',
  sub: cc ? 'Quien suscribe y copia' : 'Quien suscribe la solicitud',
  filas: [
    [
      { clave: 'firmante_nombre', etiqueta: 'Nombre del firmante', requerido: true },
      { clave: 'firmante_cargo', etiqueta: 'Cargo del firmante' },
    ],
    cc
      ? [{ clave: 'iniciales', etiqueta: 'Iniciales', corto: true }, { clave: 'cc', etiqueta: 'Cc.', pista: 'Dirección General.' }]
      : [{ clave: 'iniciales', etiqueta: 'Iniciales', corto: true }],
  ],
})

export const FORMULARIOS: Record<string, Bloque[]> = {
  informe: [
    {
      titulo: 'Encabezado',
      sub: 'Destinatario y asunto',
      filas: [
        [{ clave: 'fecha_carta', etiqueta: 'Fecha de la carta', tipo: 'fecha', requerido: true }, { clave: 'asunto', etiqueta: 'Asunto', requerido: true }],
        [{ clave: 'destinatario', etiqueta: 'Destinatario', requerido: true }, { clave: 'cargo_destinatario', etiqueta: 'Cargo del destinatario' }],
        [{ clave: 'atencion_nombre', etiqueta: 'Nombre (Atención)' }, { clave: 'atencion_cargo', etiqueta: 'Cargo (Atención)' }],
      ],
    },
    {
      titulo: 'Inmueble',
      sub: 'Inscripción catastral, anexos y propietario',
      filas: [
        [{ clave: 'anexos', etiqueta: 'Anexos', tipo: 'lista', requerido: true, pista: 'Ej: Acto No. 02/2026.', agregar: 'Agregar anexo' }],
        [{ clave: 'inscripcion_no', etiqueta: 'No. Inscripción Catastral (cuerpo)', requerido: true }],
        [{ clave: 'propietario', etiqueta: 'Nombre del propietario / propietarios', tipo: 'largo', requerido: true }],
      ],
    },
    {
      titulo: 'Audiencia',
      sub: 'Fecha, lugar y expediente',
      filas: [
        [
          { clave: 'fecha_audiencia', etiqueta: 'Fecha de audiencia', tipo: 'fecha', requerido: true },
          { clave: 'salon', etiqueta: 'Salón', corto: true },
          { clave: 'piso', etiqueta: 'Piso' },
        ],
        [{ clave: 'lugar', etiqueta: 'Lugar' }, { clave: 'expediente', etiqueta: 'No. Expediente', requerido: true }],
        [{ clave: 'cliente', etiqueta: 'Nombre del cliente', tipo: 'largo', requerido: true }],
      ],
    },
    firma(),
  ],

  archivo: [
    {
      titulo: 'Encabezado',
      sub: 'Destinatario y asunto',
      filas: [
        [{ clave: 'fecha_carta', etiqueta: 'Fecha de la carta', tipo: 'fecha', requerido: true }, { clave: 'asunto', etiqueta: 'Asunto', tipo: 'asunto', requerido: true }],
        [{ clave: 'destinatario', etiqueta: 'Destinatario (A)', requerido: true }, { clave: 'cargo_destinatario', etiqueta: 'Cargo del destinatario' }],
      ],
    },
    {
      titulo: 'Expediente',
      sub: 'Cliente, inmueble y tribunal',
      filas: [
        [
          { clave: 'nombre_cliente', etiqueta: 'Nombre del cliente', tipo: 'largo', requerido: true },
          { clave: 'cedula', etiqueta: 'Cédula de identidad', tipo: 'cedula', requerido: true, pista: '000-0000000-0' },
        ],
        [{ clave: 'descripcion_inmueble', etiqueta: 'Descripción del inmueble', tipo: 'largo', requerido: true, pista: 'Parcela No. X, del Distrito Catastral No. X…' }],
        [{ clave: 'tipo_proceso', etiqueta: 'Tipo de proceso', requerido: true, pista: 'deslinde / desalojo…' }],
        [{ clave: 'materia', etiqueta: 'Materia', tipo: 'materia' }],
        [{ clave: 'tribunal', etiqueta: 'Tribunal', tipo: 'tribunal', requerido: true, etiquetaOtra: 'Tribunal / Sala' }],
        [{ clave: 'sala', etiqueta: 'Sala', tipo: 'sala' }],
      ],
    },
    firma(),
  ],

  reporte: [
    {
      titulo: 'Expediente',
      sub: 'Tribunal, partes y parcela',
      filas: [
        [{ clave: 'expediente', etiqueta: 'No. Expediente', requerido: true }],
        [{ clave: 'materia', etiqueta: 'Materia', tipo: 'materia' }],
        [{ clave: 'asunto', etiqueta: 'Asunto', tipo: 'asunto', requerido: true }],
        [{ clave: 'tribunal', etiqueta: 'Tribunal', tipo: 'tribunal', requerido: true }],
        [{ clave: 'sala', etiqueta: 'Sala', tipo: 'sala' }],
        [{ clave: 'parcela', etiqueta: 'Parcela / Designación', requerido: true }],
        [{ clave: 'agrimensor', etiqueta: 'Agrimensor' }],
      ],
    },
    {
      titulo: 'Partes',
      sub: 'Demandante y demandado(s)',
      filas: [
        [{ clave: 'demandantes', etiqueta: 'Demandante(s)', tipo: 'largo', requerido: true }],
        [{ clave: 'demandados', etiqueta: 'Demandado(s)', tipo: 'lista', requerido: true, pista: 'Nombre del demandado', agregar: 'Agregar demandado' }],
      ],
    },
    {
      titulo: 'Audiencia',
      sub: 'Fecha, fallo y próxima audiencia',
      filas: [
        [
          { clave: 'fecha_audiencia', etiqueta: 'Fecha de la audiencia', tipo: 'fecha', requerido: true },
          { clave: 'caja_no', etiqueta: 'Caja No.', corto: true },
          { clave: 'rol', etiqueta: 'Rol', corto: true },
        ],
        [{ clave: 'fallo', etiqueta: 'Fallo', tipo: 'largo', requerido: true, pista: 'Ej: Aplazada a los fines de que…' }],
        [
          { clave: 'fecha_proxima', etiqueta: 'Fecha próxima audiencia', tipo: 'fecha', requerido: true },
          { clave: 'abogados', etiqueta: 'Abogado(s) que compareció', tipo: 'largo', requerido: true },
        ],
      ],
    },
  ],

  cobros: [
    {
      titulo: 'Encabezado',
      sub: 'Destinatario y asunto',
      filas: [
        [{ clave: 'fecha_carta', etiqueta: 'Fecha de la carta', tipo: 'fecha', requerido: true }, { clave: 'asunto', etiqueta: 'Asunto', tipo: 'asunto', requerido: true }],
        [{ clave: 'destinatario', etiqueta: 'Destinatario (A LA)', requerido: true }, { clave: 'cargo_destinatario', etiqueta: 'Cargo del destinatario' }],
      ],
    },
    {
      titulo: 'Cliente',
      sub: 'Datos del cliente e inmueble',
      filas: [
        [{ clave: 'nombre_cliente', etiqueta: 'Nombre del cliente', tipo: 'largo', requerido: true, pista: 'Nombre completo tal como aparece en el expediente' }],
        [{ clave: 'materia', etiqueta: 'Materia', tipo: 'materia' }],
        [{ clave: 'tipo_proceso', etiqueta: 'Tipo de proceso', requerido: true, pista: 'Saneamiento / Deslinde…' }],
        [{ clave: 'parcela', etiqueta: 'Parcela / Designación', requerido: true, pista: 'Designación Posesional No. …' }],
        [{ clave: 'municipio', etiqueta: 'Municipio', requerido: true }, { clave: 'provincia', etiqueta: 'Provincia', requerido: true }],
        [{ clave: 'expediente', etiqueta: 'No. Expediente', requerido: true }, { clave: 'cedula', etiqueta: 'Cédula', tipo: 'cedula', requerido: true, pista: '000-0000000-0' }],
      ],
    },
    {
      titulo: 'Proceso legal',
      sub: 'Tribunal, sentencia y tribunal original',
      filas: [
        [{ clave: 'tribunal', etiqueta: 'Tribunal', tipo: 'tribunal', requerido: true }],
        [{ clave: 'sala', etiqueta: 'Sala', tipo: 'sala' }],
        [{ clave: 'sentencia', etiqueta: 'No. Sentencia', requerido: true }, { clave: 'fecha_sentencia', etiqueta: 'Fecha sentencia', requerido: true, pista: '01 Julio del 2022' }],
        [{ clave: 'tribunal_original', etiqueta: 'Tribunal que dictó la sentencia', tipo: 'largo', requerido: true }],
      ],
    },
    firma(),
  ],

  inspeccion: [
    {
      titulo: 'Encabezado',
      sub: 'Destinatario, atención y asunto',
      filas: [
        [{ clave: 'fecha_carta', etiqueta: 'Fecha de la carta', tipo: 'fecha', requerido: true }, { clave: 'asunto', etiqueta: 'Asunto', requerido: true }],
        [{ clave: 'destinatario', etiqueta: 'Destinatario (A)', requerido: true }, { clave: 'cargo_destinatario', etiqueta: 'Cargo del destinatario' }],
        [{ clave: 'atencion_nombre', etiqueta: 'Atención (nombre)' }, { clave: 'atencion_cargo', etiqueta: 'Atención (cargo)' }],
      ],
    },
    {
      titulo: 'Contenido',
      sub: 'Cuerpo de la solicitud',
      filas: [
        [{ clave: 'cuerpo_1', etiqueta: 'Párrafo 1 — Cuerpo principal', tipo: 'largo', requerido: true, pista: 'Muy cortésmente, por medio de la presente, solicitamos que…' }],
        [{ clave: 'cuerpo_2', etiqueta: 'Párrafo 2 — Adicional (opcional)', tipo: 'largo', pista: 'Es oportuno mencionar que…' }],
      ],
    },
    firma(true),
  ],

  audiencia_provincial: [
    {
      titulo: 'Traslado',
      sub: 'Provincia y duración de la comisión',
      filas: [
        [
          { clave: 'fecha_informe', etiqueta: 'Fecha del informe', tipo: 'fecha', requerido: true },
          { clave: 'provincia', etiqueta: 'Provincia', requerido: true },
          { clave: 'municipio', etiqueta: 'Municipio (opcional)' },
        ],
        [
          { clave: 'fecha_desde', etiqueta: 'Fecha de traslado', tipo: 'fecha', requerido: true },
          { clave: 'fecha_hasta', etiqueta: 'Fecha de retorno (solo si fueron dos días)', tipo: 'fecha' },
        ],
      ],
    },
    {
      titulo: 'Audiencia',
      sub: 'Datos que aparecen en la referencia y el cuerpo',
      filas: [
        [{ clave: 'tribunal', etiqueta: 'Tribunal', tipo: 'largo', requerido: true }],
        [{ clave: 'tipo_proceso', etiqueta: 'Tipo de proceso', tipo: 'combo', opciones: 'tipos_audiencia_provincial', requerido: true }],
        [{ clave: 'inmueble', etiqueta: 'Inmueble', tipo: 'largo', requerido: true, pista: 'Parcela, D. C., resultantes, municipio y provincia…' }],
        [
          { clave: 'demandante', etiqueta: 'Demandante / requirente', tipo: 'largo', requerido: true },
          { clave: 'expediente', etiqueta: 'No. Expediente (opcional)' },
        ],
      ],
    },
    {
      titulo: 'Resultado',
      sub: 'Lo ocurrido en la audiencia',
      filas: [
        [{ clave: 'resultado', etiqueta: 'Resultado de la audiencia', tipo: 'largo', requerido: true, pista: 'Ej.: se aplazó para el 7 de diciembre a los fines de…' }],
      ],
    },
  ],

  conclusiones_saneamiento: [
    {
      titulo: 'Datos variables',
      sub: 'Los únicos datos editables del modelo de conclusiones',
      filas: [
        [{ clave: 'expediente', etiqueta: 'No. de expediente', requerido: true }],
        [{ clave: 'reclamante', etiqueta: 'Reclamante', tipo: 'combo', opciones: 'reclamantes_saneamiento', requerido: true }],
        [{ clave: 'inmueble', etiqueta: 'Inmueble', tipo: 'largo', requerido: true, pista: 'SANEAMIENTO PARCELA NO. …' }],
      ],
    },
  ],
}

export const MATERIAS = [
  { valor: 'MATERIA INMOBILIARIA', nombre: 'Inmobiliaria' },
  { valor: 'MATERIA CIVIL', nombre: 'Civil' },
  { valor: '', nombre: 'Otra' },
]
