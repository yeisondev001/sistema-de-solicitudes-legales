# Pantallas de la app (React)

Las pantallas nuevas de la oficina: React + TypeScript + Vite + Tailwind + shadcn/ui.
Todo lo de fondo (cuentas, búsqueda, IA, prestaciones, Word y PDF) sigue en Python, en `../servidor.py`.

## En local

En dos terminales, desde la carpeta del repo:

```bash
uvicorn servidor:app --reload --port 8000
```

```bash
cd web && npm install && npx vite --port 5180
```

Abrir http://localhost:5180. Vite le pasa a Python todo lo que empieza con `/api`.

## Para el servidor

`npm run build` deja las pantallas armadas en `web/dist`; `servidor.py` las entrega.

## Dónde está cada cosa

- `src/pages/`: una pantalla por sala (entrada, escritorio, asistente, biblioteca).
- `src/components/oficina.tsx`: el menú de salas, la cuenta y la prueba gratis.
- `src/components/ui/`: las piezas de shadcn/ui (se pueden cambiar; son código del proyecto).
- `src/index.css`: los colores (variables `--t-*`, las mismas de `temas.py`) y las letras.
