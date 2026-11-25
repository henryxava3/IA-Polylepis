import io
import math
import re

from psycopg.types.json import Jsonb
from pypdf import PdfReader

from . import sources
from .config import settings
from .db import connect


def upsert_document(conn, item: dict) -> int:
    # External IDs win; a missing DOI may be enriched, conflicting DOIs never merge.
    existing = conn.execute("SELECT document_id AS id FROM document_sources WHERE source=%s "
                            "AND external_id=%s", (item["source"], item["external_id"])).fetchone()
    if not existing and item["doi"]:
        existing = conn.execute("SELECT id FROM documents WHERE doi=%s", (item["doi"],)).fetchone()
    if not existing:
        candidates = conn.execute("SELECT id FROM documents WHERE normalized_title=%s "
                                  "AND year IS NOT DISTINCT FROM %s AND (doi IS NULL OR %s::text IS NULL)",
                                  (sources.normalized(item["title"]), item["year"], item["doi"])).fetchall()
        if len(candidates) == 1:
            existing = candidates[0]
    if existing:
        doc_id = existing["id"]
        conn.execute("UPDATE documents SET doi=COALESCE(doi,%s), abstract=COALESCE(abstract,%s), "
                     "license=COALESCE(license,%s), license_evidence=COALESCE(license_evidence,%s), "
                     "pdf_url=COALESCE(pdf_url,%s), updated_at=now() WHERE id=%s",
                     (item["doi"], item["abstract"], item["license"], item["license_evidence"],
                      item["pdf_url"], doc_id))
    else:
        doc_id = conn.execute("INSERT INTO documents(doi,title,normalized_title,year,authors,language,"
                              "journal,abstract,license,license_evidence,pdf_url) "
                              "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                              (item["doi"], item["title"], sources.normalized(item["title"]),
                               item["year"], Jsonb(item["authors"]), item["language"], item["journal"],
                               item["abstract"], item["license"], item["license_evidence"], item["pdf_url"])
                              ).fetchone()["id"]
    conn.execute("INSERT INTO document_sources(source,external_id,document_id,url) VALUES(%s,%s,%s,%s) "
                 "ON CONFLICT(source,external_id) DO UPDATE SET retrieved_at=now()",
                 (item["source"], item["external_id"], doc_id, item["source_url"]))
    return doc_id


def split_text(text: str, size: int = 650, overlap: int = 100):
    text = re.sub(r"[\t ]+", " ", text).strip()
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        if len(part) >= 40:
            yield part
        if end == len(text):
            break
        start = end - overlap


def save_chunks(conn, doc_id: int, text: str, page: int | None):
    for part in split_text(text):
        conn.execute("INSERT INTO chunks(document_id,page,locator,text,content_hash) VALUES(%s,%s,%s,%s,%s) "
                     "ON CONFLICT DO NOTHING", (doc_id, page, f"Página PDF {page}" if page else "Resumen",
                                               part, sources.digest(part)))


def index_texts(limit: int):
    counts = {"processed": 0, "pdfs": 0, "failed": 0, "abstracts": 0}
    with connect() as conn:
        docs = conn.execute("SELECT * FROM documents WHERE relevance_status='included' AND license IS NOT NULL AND "
                            "text_status NOT IN ('fulltext','abstract') ORDER BY id LIMIT %s", (limit,)).fetchall()
    storage = settings.data_dir / "pdfs"
    storage.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        try:
            pages = []
            checksum = None
            if doc["pdf_url"]:
                payload = sources.download_pdf(doc["pdf_url"])
                checksum = sources.digest(payload.hex())
                reader = PdfReader(io.BytesIO(payload))
                if reader.is_encrypted or len(reader.pages) > 500:
                    raise sources.SourceError("PDF cifrado o mayor de 500 páginas; necesita revisión.")
                for page_number, page in enumerate(reader.pages, 1):
                    text = page.extract_text() or ""
                    if len(text.strip()) >= 40:
                        pages.append((page_number, text))
                if not pages:
                    raise sources.SourceError("PDF sin texto extraíble. OCR queda pendiente para otra fase.")
                (storage / f"{doc['id']}.pdf").write_bytes(payload)
            with connect() as conn:
                if pages:
                    for number, text in pages:
                        save_chunks(conn, doc["id"], text, number)
                    counts["pdfs"] += 1
                elif doc["abstract"]:
                    save_chunks(conn, doc["id"], doc["abstract"], None)
                    counts["abstracts"] += 1
                else:
                    continue
                conn.execute("UPDATE documents SET text_status=%s,text_error=NULL,content_hash=%s WHERE id=%s",
                             ("fulltext" if pages else "abstract", checksum, doc["id"]))
                counts["processed"] += 1
        except Exception as error:
            counts["failed"] += 1
            message = str(error) if isinstance(error, sources.SourceError) else "No se pudo extraer este PDF."
            with connect() as conn:
                # An authorized abstract remains useful even if the PDF host blocks downloads.
                if doc["abstract"]:
                    save_chunks(conn, doc["id"], doc["abstract"], None)
                    counts["abstracts"] += 1
                conn.execute("UPDATE documents SET text_status=%s,text_error=%s WHERE id=%s",
                             ("abstract" if doc["abstract"] else "error", message, doc["id"]))
    return counts


def sync_taxonomy():
    key = sources.genus_key()
    rows = [sources.get_json(f"https://api.gbif.org/v1/species/{key}")]
    offset = 0
    while True:
        data = sources.get_json(f"https://api.gbif.org/v1/species/{key}/children", {"limit": 100, "offset": offset})
        rows.extend(data.get("results", []))
        if data.get("endOfRecords") or not data.get("results"):
            break
        offset += len(data["results"])
    with connect() as conn:
        for row in rows:
            conn.execute("INSERT INTO taxa(gbif_key,scientific_name,canonical_name,status,accepted_key,rank,source_url) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(gbif_key) DO UPDATE SET "
                         "scientific_name=EXCLUDED.scientific_name,canonical_name=EXCLUDED.canonical_name,"
                         "status=EXCLUDED.status,accepted_key=EXCLUDED.accepted_key,retrieved_at=now()",
                         (row["key"], row["scientificName"], row.get("canonicalName", row["scientificName"]),
                          row.get("taxonomicStatus", "UNKNOWN"), row.get("acceptedKey"), row.get("rank", "UNKNOWN"),
                          f"https://www.gbif.org/species/{row['key']}"))
        for row in rows:
            if row.get("taxonomicStatus") == "ACCEPTED" and row.get("rank") == "SPECIES":
                synonyms = sources.get_json(f"https://api.gbif.org/v1/species/{row['key']}/synonyms", {"limit": 100})
                for synonym in synonyms.get("results", []):
                    conn.execute("INSERT INTO taxon_names(name,taxon_key,kind,source_url) VALUES(%s,%s,'synonym',%s) "
                                 "ON CONFLICT DO NOTHING", (synonym["scientificName"], row["key"],
                                                          f"https://www.gbif.org/species/{synonym['key']}"))
    return {"processed": len(rows), "genus_key": key}


def occurrence_values(row: dict):
    lat, lon = row.get("decimalLatitude"), row.get("decimalLongitude")
    if not isinstance(lat, (float, int)) or not isinstance(lon, (float, int)):
        return None
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    if row.get("genus") != "Polylepis" or row.get("occurrenceStatus") not in {"PRESENT", "DETECTED"}:
        return None
    uncertainty = row.get("coordinateUncertaintyInMeters")
    uncertainty = uncertainty if isinstance(uncertainty, (int, float)) and math.isfinite(uncertainty) and uncertainty > 0 else None
    return (row["key"], row.get("speciesKey") or row.get("taxonKey"),
            (row.get("verbatim") or {}).get("scientificName") or row.get("scientificName", "Polylepis"),
            row.get("acceptedScientificName") or row.get("scientificName", "Polylepis"),
            row.get("countryCode"), row.get("locality"), lon, lat, uncertainty,
            Jsonb(row.get("issues", [])), row.get("license"), row["datasetKey"],
            f"https://www.gbif.org/occurrence/{row['key']}", row.get("year"), row.get("basisOfRecord"))


def sync_occurrences(limit: int):
    counts = {"processed": 0, "skipped": 0}
    key = sources.genus_key()
    point_sql = "ST_SetSRID(ST_MakePoint(%s,%s),4326)" if settings.database_extensions else "point(%s,%s)"
    for raw in sources.gbif_records(limit, key):
        values = occurrence_values(raw)
        if not values:
            counts["skipped"] += 1
            continue
        with connect() as conn:
            conn.execute("INSERT INTO occurrences(gbif_id,taxon_key,original_name,accepted_name,country,locality,geom,"
                         "uncertainty_m,issues,license,dataset_key,source_url,collected_year,basis_of_record) "
                         f"VALUES(%s,%s,%s,%s,%s,%s,{point_sql},%s,%s,%s,%s,%s,%s,%s) "
                         "ON CONFLICT(gbif_id) DO UPDATE SET geom=EXCLUDED.geom,uncertainty_m=EXCLUDED.uncertainty_m,"
                         "issues=EXCLUDED.issues,license=EXCLUDED.license,accepted_name=EXCLUDED.accepted_name,"
                         "retrieved_at=now()", values)
        counts["processed"] += 1
    return counts


def run_ingestion(run_id: int, source: str, limit: int):
    counts = {"processed": 0}
    try:
        if source in {"openalex", "crossref"}:
            adapter = sources.openalex if source == "openalex" else sources.crossref
            for doc in adapter(limit):
                with connect() as conn:
                    upsert_document(conn, doc)
                counts["processed"] += 1
        elif source == "gbif":
            counts = sync_occurrences(limit)
        elif source == "taxonomy":
            counts = sync_taxonomy()
        elif source == "texts":
            counts = index_texts(limit)
        elif source == "embeddings":
            from .rag import index_embeddings
            counts = index_embeddings()
        with connect() as conn:
            conn.execute("UPDATE ingestion_runs SET status=%s,finished_at=now(),counts=%s WHERE id=%s",
                         ("partial" if counts.get("failed") else "completed", Jsonb(counts), run_id))
    except Exception as error:
        message = str(error) if isinstance(error, sources.SourceError) else f"Falló la ingesta ({type(error).__name__})."
        with connect() as conn:
            conn.execute("UPDATE ingestion_runs SET status='failed',finished_at=now(),counts=%s,error=%s WHERE id=%s",
                         (Jsonb(counts), message, run_id))
