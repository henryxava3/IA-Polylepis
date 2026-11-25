"""Run bounded, real-data imports through the local API. No synthetic seed data."""
import argparse
import json
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--sources', default='openalex,crossref,gbif,taxonomy,texts,embeddings')
parser.add_argument('--limit', type=int, default=100)
args = parser.parse_args()


def api(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('http://127.0.0.1:8000/api' + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


for attempt in range(30):
    try:
        if api('/health')['database']:
            break
    except (urllib.error.URLError, OSError):
        pass
    time.sleep(1)
else:
    raise SystemExit('El backend no está disponible. Inicia scripts/start-local.ps1.')

for source in args.sources.split(','):
    run = api('/ingest', {'source': source, 'limit': args.limit})
    print(f"{source}: ejecución {run['id']} iniciada", flush=True)
    for attempt in range(900):
        runs = api('/runs')
        status = next(r for r in runs if r['id'] == run['id'])
        if status['status'] != 'running':
            print(json.dumps(status, ensure_ascii=True), flush=True)
            break
        time.sleep(2)
    else:
        raise SystemExit('La ingesta sigue en curso después de 30 minutos. Revisar estación local.')
print(json.dumps(api('/stats'), ensure_ascii=True), flush=True)
