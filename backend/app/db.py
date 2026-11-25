from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import settings


@contextmanager
def connect():
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=5, options="-c timezone=UTC") as conn:
        yield conn


def migrate():
    with connect() as conn:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        if not settings.database_extensions:
            schema = schema.replace("CREATE EXTENSION IF NOT EXISTS postgis;", "")
            schema = schema.replace("CREATE EXTENSION IF NOT EXISTS vector;", "")
            schema = schema.replace("geometry(Point,4326)", "point").replace("vector(384)", "real[]")
            schema = schema.replace("CREATE INDEX IF NOT EXISTS chunks_vector_idx ON chunks USING hnsw (embedding vector_cosine_ops);", "")
        conn.execute(schema)
        conn.execute("UPDATE ingestion_runs SET status='interrupted', finished_at=now(), "
                     "error='El servidor se reinició durante la ingesta.' WHERE status='running'")
