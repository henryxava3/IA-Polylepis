# Polylepis

Estación local de investigación para reunir literatura, registros geográficos y evidencia verificable sobre el género *Polylepis*.

El proyecto implementa las fases 0 y 1 del plan inicial:

- Catálogo taxonómico basado en GBIF Backbone, con procedencia de nombres y sinónimos.
- Descubrimiento bibliográfico mediante OpenAlex y Crossref, con deduplicación y auditoría de ingestas.
- Biblioteca web con búsqueda, filtros y detalles de procedencia.
- Geovisor de ocurrencias GBIF con calidad e incertidumbre explícitas.
- Preparación local de fragmentos de textos con licencia abierta y búsqueda híbrida.
- Asistente preparado para Claude con validación local de citas. Requiere una clave API que no se incluye en este repositorio.

## Requisitos

- Windows con PostgreSQL 18 instalado, o Docker Desktop funcional.
- Node.js 24 o posterior.
- Python 3.12, administrado automáticamente por `uv`.

## Arranque local

```powershell
Copy-Item .env.example .env
.\scripts\start-local.ps1
```

Abre `http://localhost:3000`. La API y su documentación están en `http://localhost:8000/docs`.

El script crea una instancia PostgreSQL aislada en el puerto `54329`; no modifica el servicio de PostgreSQL existente. Para detenerla junto con la aplicación:

```powershell
.\scripts\stop-local.ps1
```

Si Docker está disponible, se puede usar `.\scripts\start-local.ps1 -Docker`.

## Configuración

Las variables están documentadas en `.env.example`. `.env` está excluido del control de versiones.

- `ANTHROPIC_API_KEY`: activa respuestas generadas por el asistente con Claude.
- `OPENALEX_API_KEY`: necesaria para paginación amplia de OpenAlex.
- `GBIF_USERNAME`, `GBIF_PASSWORD` y `CONTACT_EMAIL`: necesarias solo para solicitar descargas GBIF con DOI.

## Carga inicial

Con la aplicación iniciada:

```powershell
.\backend\.venv\Scripts\python.exe -u scripts\seed-local.py --limit 100
```

También puedes ejecutar cada fuente desde la página **Estación local**. El pipeline almacena PDFs únicamente cuando hay una licencia abierta verificable. Revisa [la metodología](docs/FASE-0.md) para conocer los límites del MVP y las fuentes.

## Verificación

```powershell
cd backend
$env:TEST_DATABASE_URL = 'postgresql://polylepis:polylepis_local@127.0.0.1:54329/polylepis'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests

cd ..\frontend
npm run typecheck
npm run lint
npm run build
```

## Estado

Es un MVP local: no publica datos, no programa actualizaciones automáticas y no extrae localidades desde artículos. La cobertura de literatura y la precisión geográfica siguen sin medirse y se declaran como tales dentro de la aplicación.
