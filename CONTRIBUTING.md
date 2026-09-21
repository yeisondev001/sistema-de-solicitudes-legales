# Guía de contribución

Gracias por contribuir al Sistema de Solicitudes Legales. El objetivo principal es preservar la fidelidad de los modelos jurídicos y mantener una experiencia sencilla para el personal que los utiliza.

## Principios de trabajo

- No cambie texto jurídico aprobado sin validar el cambio con el área responsable.
- Mantenga los campos variables explícitos y valide los obligatorios antes de generar un documento.
- No incorpore expedientes reales, datos personales ni documentos generados al repositorio.
- Reutilice los helpers de `generators/base.py` para conservar el formato institucional.

## Desarrollo local

```bash
python -m pip install -r requirements.txt
python main.py
```

## Antes de enviar un cambio

1. Ejecute `python -m compileall main.py generators`.
2. Genere un Word y un PDF de cada plantilla afectada con datos de prueba ficticios.
3. Revise que el documento contenga los encabezados, campos, cuerpo y firma esperados.
4. Confirme que no se añadieron archivos de descarga ni información confidencial.
5. Describa en el commit la plantilla o el flujo que fue modificado.

## Nuevas plantillas

Toda nueva plantilla debe incluir:

- Formulario y validaciones en `main.py`.
- Generador Word en `generators/`.
- Generador PDF en `generators/pdf_gen.py`.
- Exportación en `generators/__init__.py`.
- Una actualización de la lista de plantillas del README.
