"""Reversibly quarantine non-literature and epithet false positives from initial discovery."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db import connect, migrate
from app.sources import get_json, relevant

migrate()
with connect() as conn:
    rows = conn.execute("SELECT d.id,d.title,d.abstract,s.external_id FROM documents d LEFT JOIN document_sources s "
                        "ON s.document_id=d.id AND s.source='openalex' WHERE d.relevance_status='included'").fetchall()
for row in rows:
    reason = None
    if not relevant(row['title'], row['abstract'] or ''):
        reason = 'El término polylepis corresponde a otro género, no al género altoandino.'
    elif row['external_id']:
        raw = get_json('https://api.openalex.org/works/' + row['external_id'].rsplit('/', 1)[-1], {'select': 'id,type'})
        if raw.get('type') not in {'article','review','book-chapter','dissertation','report','book','preprint'}:
            reason = 'Tipo documental excluido del MVP: ' + raw.get('type', 'unknown')
    if reason:
        with connect() as conn:
            conn.execute("UPDATE documents SET relevance_status='excluded',exclusion_reason=%s WHERE id=%s", (reason, row['id']))
        print(f"Excluded {row['id']}: {reason}", flush=True)
print('Review finished.', flush=True)
