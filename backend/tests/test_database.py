import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from app.ingestion import upsert_document, save_chunks


@pytest.fixture
def conn():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Define TEST_DATABASE_URL para las pruebas aisladas de PostgreSQL.')
    with psycopg.connect(url, row_factory=dict_row) as connection:
        schema_name = 'test_' + uuid4().hex
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema_name)))
        connection.execute(sql.SQL('SET LOCAL search_path TO {}, public').format(sql.Identifier(schema_name)))
        schema = (Path(__file__).parents[1] / 'app/schema.sql').read_text(encoding='utf-8')
        schema = schema.replace('CREATE EXTENSION IF NOT EXISTS postgis;', '').replace('CREATE EXTENSION IF NOT EXISTS vector;', '')
        schema = schema.replace('geometry(Point,4326)', 'point').replace('vector(384)', 'real[]')
        schema = schema.replace('CREATE INDEX IF NOT EXISTS chunks_vector_idx ON chunks USING hnsw (embedding vector_cosine_ops);', '')
        connection.execute(schema)
        yield connection
        connection.rollback()


def paper(source='openalex', external_id='test-1', doi='10.1234/synthetic-test'):
    return {'source': source, 'external_id': external_id, 'source_url': 'https://example.org/test',
            'doi': doi, 'title': 'SYNTHETIC Polylepis TEST ONLY', 'year': 2000, 'authors': ['Test fixture'],
            'language': 'es', 'journal': 'Test only', 'abstract': None, 'license': None,
            'license_evidence': None, 'pdf_url': None}


def test_ingestion_is_idempotent_and_merges_provenance(conn):
    first = upsert_document(conn, paper())
    assert upsert_document(conn, paper()) == first
    assert upsert_document(conn, paper('crossref', 'test-2')) == first
    assert conn.execute('SELECT count(*) AS n FROM documents').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM document_sources').fetchone()['n'] == 2


def test_conflicting_dois_do_not_merge_on_title(conn):
    assert upsert_document(conn, paper()) != upsert_document(conn, paper('crossref', 'test-2', '10.1234/other-synthetic'))


def test_doi_enrichment(conn):
    first = upsert_document(conn, paper(doi=None))
    assert upsert_document(conn, paper('crossref', 'second')) == first
    assert conn.execute('SELECT doi FROM documents WHERE id=%s', (first,)).fetchone()['doi'] == '10.1234/synthetic-test'


def test_chunks_idempotent_and_parameterized(conn):
    doc_id = upsert_document(conn, paper())
    text = "SYNTHETIC TEST: '); DROP TABLE documents; -- " * 5
    save_chunks(conn, doc_id, text, 4)
    save_chunks(conn, doc_id, text, 4)
    assert conn.execute('SELECT count(*) AS n FROM chunks').fetchone()['n'] == 1
    assert conn.execute('SELECT text,page FROM chunks').fetchone() == {'text': text.strip(), 'page': 4}
