from .informe    import generar as generar_informe_tecnico
from .archivo    import generar as generar_copia_certificada
from .reporte    import generar as generar_reporte_audiencia
from .cobros     import generar as generar_solicitud_cobros
from .inspeccion import generar as generar_solicitud_inspeccion
from .audiencia_provincial import generar as generar_informe_audiencia_provincial
from .conclusiones_saneamiento import generar as generar_conclusiones_saneamiento
from .base       import nombre_archivo
from .pdf_gen    import (
    pdf_informe_tecnico,
    pdf_copia_certificada,
    pdf_reporte_audiencia,
    pdf_solicitud_cobros,
    pdf_solicitud_inspeccion,
    pdf_informe_audiencia_provincial,
    pdf_conclusiones_saneamiento,
)
