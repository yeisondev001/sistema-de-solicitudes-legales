# Guía de contribución

Gracias por contribuir a Papiniano (antes Sistema de Solicitudes Legales). Lo que más importa: que las respuestas y
los escritos sean fieles a las fuentes, que los datos de los clientes estén protegidos y que la app siga siendo fácil
para abogados que no son técnicos.

## Principios de trabajo

- Lea primero [ESTADO_DEL_PROYECTO.md](ESTADO_DEL_PROYECTO.md): ahí está por dónde va el trabajo y qué falta.
- No cambie texto jurídico aprobado (modelos de escritos, plantillas) sin validarlo con un abogado.
- No suba expedientes reales, cédulas, escritos con datos reales, documentos generados ni ningún dato personal.
- No mande datos personales de clientes a la IA (Ley 172-13): van como datos por llenar.
- Nunca suba claves, contraseñas ni cadenas de conexión: van en las variables del servidor.

## Desarrollo local

```bash
python -m pip install -r requirements.txt
uvicorn servidor:app --reload --port 8000
```

En otra terminal:

```bash
cd web && npm install && npx vite --port 5180
```

## Antes de enviar un cambio

1. En `web/`, corra `npx tsc -b` y `npm run build`: no deben dar errores.
2. Pruebe el cambio en la app (computadora y celular) con datos ficticios.
3. Si toca la base de datos, pruébelo también contra una base que ya tenga las tablas de antes (las migraciones
   están en `cuentas.py`; ojo: la tabla `expedientes` es la del historial de reportes y la de los expedientes nuevos es
   `casos`).
4. Confirme que no se añadieron archivos descargados ni información confidencial.
5. Actualice `ESTADO_DEL_PROYECTO.md` si cambia algo que el próximo debe saber.

## Plantillas institucionales (sala Redacción)

Una plantilla nueva lleva su generador Word en `generators/`, su PDF en `generators/pdf_gen.py`, su exportación en
`generators/__init__.py`, lo que necesita (valores, obligatorios, nombre del archivo) en `redaccion.py` y su formulario
en `web/src/lib/plantillas.ts`. Genere un Word y un PDF con datos ficticios y revise
encabezados, campos, cuerpo y firma.
