CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS schema_migrations (
  version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS taxa (
  gbif_key bigint PRIMARY KEY, scientific_name text NOT NULL, canonical_name text NOT NULL,
  status text NOT NULL, accepted_key bigint, rank text NOT NULL, source_url text NOT NULL,
  retrieved_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS taxon_names (
  name text NOT NULL, taxon_key bigint NOT NULL REFERENCES taxa(gbif_key), kind text NOT NULL,
  source_url text NOT NULL, PRIMARY KEY(name, taxon_key, kind)
);
CREATE TABLE IF NOT EXISTS documents (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  doi text UNIQUE, title text NOT NULL, normalized_title text NOT NULL,
  year integer, authors jsonb NOT NULL DEFAULT '[]', language text, journal text,
  abstract text, license text, license_evidence text, pdf_url text,
  text_status text NOT NULL DEFAULT 'metadata', text_error text,
  content_hash text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  search_vector tsvector GENERATED ALWAYS AS
    (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(abstract,''))) STORED
);
CREATE INDEX IF NOT EXISTS documents_search_idx ON documents USING gin(search_vector);
CREATE INDEX IF NOT EXISTS documents_title_idx ON documents(normalized_title, year);
CREATE TABLE IF NOT EXISTS document_sources (
  source text NOT NULL, external_id text NOT NULL, document_id bigint NOT NULL REFERENCES documents(id),
  url text NOT NULL, retrieved_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(source, external_id)
);
CREATE TABLE IF NOT EXISTS chunks (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, document_id bigint NOT NULL REFERENCES documents(id),
  page integer CHECK (page > 0), locator text NOT NULL, text text NOT NULL,
  content_hash text NOT NULL, embedding vector(384), embedding_model text,
  UNIQUE(document_id, locator, content_hash)
);
CREATE INDEX IF NOT EXISTS chunks_document_idx ON chunks(document_id);
CREATE INDEX IF NOT EXISTS chunks_vector_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS occurrences (
  gbif_id bigint PRIMARY KEY, taxon_key bigint, original_name text NOT NULL,
  accepted_name text NOT NULL, country text, locality text, geom geometry(Point,4326) NOT NULL,
  uncertainty_m double precision CHECK (uncertainty_m > 0), issues jsonb NOT NULL DEFAULT '[]',
  license text, dataset_key text NOT NULL, source_url text NOT NULL, collected_year integer,
  basis_of_record text, retrieved_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS occurrences_geom_idx ON occurrences USING gist(geom);
CREATE TABLE IF NOT EXISTS ingestion_runs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, source text NOT NULL,
  status text NOT NULL DEFAULT 'running', started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz, counts jsonb NOT NULL DEFAULT '{}', error text
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_ingestion ON ingestion_runs ((1)) WHERE status='running';
CREATE TABLE IF NOT EXISTS gbif_downloads (
  download_key text PRIMARY KEY, doi text, status text NOT NULL,
  predicate jsonb NOT NULL, source_url text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS query_audit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL, model text, input_tokens integer NOT NULL DEFAULT 0,
  output_tokens integer NOT NULL DEFAULT 0, latency_ms integer NOT NULL, citation_count integer NOT NULL
);
INSERT INTO schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS relevance_status text NOT NULL DEFAULT 'included';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS exclusion_reason text;
INSERT INTO schema_migrations(version) VALUES (2) ON CONFLICT DO NOTHING;
