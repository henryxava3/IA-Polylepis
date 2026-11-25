import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Literal

import httpx
import psycopg
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import settings
from .db import connect, migrate
from .ingestion import run_ingestion
from .rag import ask
from .sources import SourceError, genus_key, get_json

logger = logging.getLogger("polylepis")
rate = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        migrate()
        app.state.db_ready = True
    except psycopg.Error:
        app.state.db_ready = False
        logger.warning(json.dumps({"event": "database_unavailable", "action": "start_local_postgres"}))
    yield


app = FastAPI(title="Polylepis · API local", version="0.1.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "api", "testserver"])


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in {"http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"}:
            return JSONResponse({"detail": "Origen no autorizado para modificar la estación local."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Solicitud externa no autorizada."}, status_code=403)
        now = time.monotonic()
        bucket = rate[request.url.path]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= 10:
            return JSONResponse({"detail": "Espera un minuto antes de volver a intentarlo."}, status_code=429)
        bucket.append(now)
    return await call_next(request)


@app.exception_handler(psycopg.Error)
async def database_error(request: Request, error):
    return JSONResponse({"detail": "PostgreSQL no está disponible. Inicia Docker y ejecuta el script de arranque."}, status_code=503)


@app.exception_handler(SourceError)
async def source_error(request: Request, error):
    return JSONResponse({"detail": str(error)}, status_code=502)


@app.get("/api/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1 FROM schema_migrations LIMIT 1")
        database = True
    except psycopg.Error:
        database = False
    return {"status": "ready" if database else "database_unavailable", "database": database,
            "claude_configured": bool(settings.anthropic_api_key), "openalex_configured": bool(settings.openalex_api_key),
            "gbif_configured": bool(settings.gbif_username and settings.gbif_password),
            "embedding_model": settings.embedding_model, "local": True,
            "storage_mode": "postgis-pgvector" if settings.database_extensions else "postgres-native"}


@app.get("/api/stats")
def stats():
    with connect() as conn:
        docs = conn.execute("SELECT count(*) AS documents,count(*) FILTER(WHERE text_status='fulltext') AS fulltexts,"
                            "count(*) FILTER(WHERE text_status='abstract') AS abstracts,count(*) FILTER(WHERE license IS NOT NULL) AS licensed "
                            "FROM documents WHERE relevance_status='included'").fetchone()
        geo = conn.execute("SELECT count(*) AS occurrences,count(DISTINCT country) AS countries,"
                           "count(*) FILTER(WHERE uncertainty_m IS NULL) AS unknown_uncertainty FROM occurrences").fetchone()
        chunks = conn.execute("SELECT count(*) AS chunks,count(*) FILTER(WHERE embedding IS NOT NULL) AS embedded FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.relevance_status='included'").fetchone()
        taxon = conn.execute("SELECT count(*) AS taxa FROM taxa WHERE rank='SPECIES' AND status='ACCEPTED'").fetchone()
        last = conn.execute("SELECT max(finished_at) AS last_sync FROM ingestion_runs WHERE status IN ('completed','partial')").fetchone()
    return {**docs, **geo, **chunks, **taxon, **last, "global_coverage": None, "geocoding_coverage": None}


@app.get("/api/documents")
def documents(q: str = Query("", max_length=200), year: int | None = None, access: Literal["all", "fulltext", "licensed"] = "all",
              source: Literal["all", "openalex", "crossref"] = "all", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    conditions, params = ["d.relevance_status='included'"], []
    if q.strip():
        conditions.append("(d.search_vector @@ websearch_to_tsquery('simple', %s) OR d.title ILIKE %s)")
        params.extend([q, "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"])
    if year:
        conditions.append("d.year=%s")
        params.append(year)
    if access == "fulltext":
        conditions.append("d.text_status='fulltext'")
    elif access == "licensed":
        conditions.append("d.license IS NOT NULL")
    if source != "all":
        conditions.append("EXISTS(SELECT 1 FROM document_sources s WHERE s.document_id=d.id AND s.source=%s)")
        params.append(source)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with connect() as conn:
        total = conn.execute("SELECT count(*) AS n FROM documents d" + where, params).fetchone()["n"]
        rows = conn.execute("SELECT d.*, (SELECT jsonb_agg(jsonb_build_object('source',s.source,'url',s.url)) "
                            "FROM document_sources s WHERE s.document_id=d.id) AS sources FROM documents d" + where +
                            " ORDER BY d.year DESC NULLS LAST,d.id DESC LIMIT %s OFFSET %s",
                            params + [page_size, (page - 1) * page_size]).fetchall()
    for row in rows:
        row.pop("search_vector", None)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@app.get("/api/documents/{doc_id}")
def document(doc_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=%s", (doc_id,)).fetchone()
        if not row or row['relevance_status'] != 'included':
            raise HTTPException(404, "Documento no encontrado.")
        row.pop("search_vector", None)
        row["sources"] = conn.execute("SELECT * FROM document_sources WHERE document_id=%s", (doc_id,)).fetchall()
        row["chunks"] = conn.execute("SELECT id,page,locator,text FROM chunks WHERE document_id=%s ORDER BY page NULLS FIRST,id", (doc_id,)).fetchall()
    return row


@app.get("/api/documents/{doc_id}/pdf")
def pdf(doc_id: int):
    with connect() as conn:
        doc = conn.execute("SELECT license,text_status FROM documents WHERE id=%s", (doc_id,)).fetchone()
    path = settings.data_dir / "pdfs" / f"{doc_id}.pdf"
    if not doc or not doc["license"] or doc["text_status"] != "fulltext" or not path.is_file():
        raise HTTPException(404, "No hay un PDF autorizado disponible localmente.")
    return FileResponse(path, media_type="application/pdf", filename=f"polylepis-{doc_id}.pdf")


@app.get("/api/occurrences")
def occurrences(country: str = Query("", max_length=2), species: str = Query("", max_length=200), limit: int = Query(10000, ge=1, le=50000)):
    conditions, params = [], []
    if country:
        conditions.append("country=%s")
        params.append(country)
    if species:
        conditions.append("accepted_name=%s")
        params.append(species)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with connect() as conn:
        total = conn.execute("SELECT count(*) AS n FROM occurrences" + where, params).fetchone()["n"]
        coordinates = "ST_X(geom) AS lon,ST_Y(geom) AS lat" if settings.database_extensions else "geom[0] AS lon,geom[1] AS lat"
        rows = conn.execute(f"SELECT *,{coordinates} FROM occurrences" + where + " ORDER BY gbif_id LIMIT %s", params + [limit]).fetchall()
    features = []
    for row in rows:
        lon, lat = row.pop("lon"), row.pop("lat")
        row.pop("geom")
        row["retrieved_at"] = row["retrieved_at"].isoformat()
        row["confidence"] = "incertidumbre declarada" if row["uncertainty_m"] else "incertidumbre desconocida"
        features.append({"type": "Feature", "id": row["gbif_id"], "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": row})
    return {"type": "FeatureCollection", "features": features, "total": total, "truncated": total > limit,
            "provenance": "GBIF occurrence search; sin DOI de descarga y sin verificación independiente"}


@app.get("/api/filters")
def filters():
    with connect() as conn:
        return {"years": [r["year"] for r in conn.execute("SELECT DISTINCT year FROM documents WHERE year IS NOT NULL AND relevance_status='included' ORDER BY year DESC")],
                "countries": [r["country"] for r in conn.execute("SELECT DISTINCT country FROM occurrences WHERE country IS NOT NULL ORDER BY country")],
                "species": [r["accepted_name"] for r in conn.execute("SELECT DISTINCT accepted_name FROM occurrences ORDER BY accepted_name")]}


@app.get("/api/taxa")
def taxa():
    with connect() as conn:
        return conn.execute("SELECT t.*,COALESCE((SELECT jsonb_agg(n.name) FROM taxon_names n WHERE n.taxon_key=t.gbif_key),'[]') AS synonyms "
                            "FROM taxa t ORDER BY canonical_name").fetchall()


class IngestRequest(BaseModel):
    source: Literal["openalex", "crossref", "gbif", "taxonomy", "texts", "embeddings"]
    limit: int = Field(100, ge=1, le=10000)


@app.post("/api/ingest", status_code=202)
def ingest(body: IngestRequest, background: BackgroundTasks):
    try:
        with connect() as conn:
            run = conn.execute("INSERT INTO ingestion_runs(source) VALUES(%s) RETURNING id", (body.source,)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Ya hay una ingesta en curso. Espera a que termine.") from None
    background.add_task(run_ingestion, run["id"], body.source, body.limit)
    return {"id": run["id"], "status": "running"}


@app.get("/api/runs")
def runs():
    with connect() as conn:
        return conn.execute("SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 30").fetchall()


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2000)


@app.post("/api/ask")
def assistant(body: AskRequest):
    return ask(body.question)


@app.post("/api/gbif/download", status_code=202)
def request_download():
    if not (settings.gbif_username and settings.gbif_password and settings.contact_email):
        raise HTTPException(400, "Configura usuario, contraseña GBIF y CONTACT_EMAIL en .env.")
    predicate = {"type": "and", "predicates": [{"type": "equals", "key": "TAXON_KEY", "value": str(genus_key())},
                  {"type": "equals", "key": "HAS_COORDINATE", "value": "true"},
                  {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "PRESENT"}]}
    with httpx.Client(timeout=45) as http:
        response = http.post("https://api.gbif.org/v1/occurrence/download/request",
                             auth=(settings.gbif_username, settings.gbif_password),
                             json={"creator": settings.gbif_username, "notificationAddresses": [settings.contact_email],
                                   "sendNotification": False, "format": "SIMPLE_CSV", "predicate": predicate})
    if response.status_code not in {200, 201, 202}:
        raise HTTPException(502, f"GBIF rechazó la solicitud: HTTP {response.status_code}.")
    key = response.text.strip().strip('"')
    if not key.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(502, "GBIF devolvió una clave de descarga inesperada.")
    with connect() as conn:
        conn.execute("INSERT INTO gbif_downloads(download_key,status,predicate,source_url) VALUES(%s,'PREPARING',%s,%s) ON CONFLICT DO NOTHING",
                     (key, Jsonb(predicate), f"https://www.gbif.org/occurrence/download/{key}"))
    return {"key": key, "message": "Solicitud creada; aún no tiene DOI confirmado."}


@app.get("/api/gbif/downloads")
def downloads():
    with connect() as conn:
        return conn.execute("SELECT * FROM gbif_downloads ORDER BY created_at DESC").fetchall()


@app.post("/api/gbif/downloads/refresh")
def refresh_downloads():
    with connect() as conn:
        rows = conn.execute("SELECT download_key FROM gbif_downloads WHERE status NOT IN ('SUCCEEDED','FAILED','CANCELLED')").fetchall()
        for row in rows:
            data = get_json("https://api.gbif.org/v1/occurrence/download/" + row["download_key"])
            conn.execute("UPDATE gbif_downloads SET status=%s,doi=%s WHERE download_key=%s",
                         (data.get("status", "UNKNOWN"), data.get("doi"), row["download_key"]))
    return {"updated": len(rows)}
