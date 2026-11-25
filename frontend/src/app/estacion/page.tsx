'use client';
import { useState } from 'react';
import { ArrowDownToLine, RefreshCw, Check, Circle, ExternalLink, Database, KeyRound } from 'lucide-react';
import { request, useApi, count, type Health, type Run, type Stats } from '@/lib/api';
import { PageHeading, ErrorNotice, Loading } from '@/components/common';
import { Button } from '@/components/ui/button';
const sources = [
  { id: 'taxonomy', number: '01', title: 'Referencia taxonómica', description: 'Nombres del género y sinónimos desde GBIF.', button: 'Sincronizar taxonomía' },
  { id: 'openalex', number: '02', title: 'OpenAlex', description: 'Descubre publicaciones y comprueba sus licencias.', button: 'Consultar OpenAlex' },
  { id: 'crossref', number: '03', title: 'Crossref', description: 'Complementa la biblioteca con metadatos y DOI.', button: 'Consultar Crossref' },
  { id: 'gbif', number: '04', title: 'Registros GBIF', description: 'Incorpora ocurrencias con coordenadas y procedencia.', button: 'Incorporar registros' },
  { id: 'texts', number: '05', title: 'Textos autorizados', description: 'Descarga PDFs permitidos y extrae fragmentos con página.', button: 'Preparar textos' },
  { id: 'embeddings', number: '06', title: 'Índice multilingüe', description: 'Calcula los vectores localmente. Descarga un modelo en el primer uso.', button: 'Construir índice' },
];
const statuses: Record<string, string> = { running: 'En curso', completed: 'Completada', partial: 'Parcial', failed: 'Falló', interrupted: 'Interrumpida' };
type Download = { download_key: string; status: string; doi: string | null; source_url: string };
export default function StationPage() {
  const health = useApi<Health>('/health', 10000);
  const runs = useApi<Run[]>('/runs', 4000);
  const { data: stats } = useApi<Stats>('/stats', 10000);
  const downloads = useApi<Download[]>('/gbif/downloads', 10000);
  const [pending, setPending] = useState(false); const [error, setError] = useState('');
  const [limit, setLimit] = useState(100); const [notice, setNotice] = useState('');
  const running = runs.data?.some(r => r.status === 'running');
  async function run(source: string) {
    setPending(true); setError(''); setNotice('');
    try { await request('/ingest', { source, limit }); runs.reload(); setNotice('La tarea está en marcha. Puedes seguir su estado en el historial.'); }
    catch (e) { setError((e as Error).message); } finally { setPending(false); }
  }
  async function download(refresh = false) {
    setPending(true); setError('');
    try { await request(refresh ? '/gbif/downloads/refresh' : '/gbif/download', {}); downloads.reload(); }
    catch (e) { setError((e as Error).message); } finally { setPending(false); }
  }
  return <div className="page-wrap"><PageHeading eyebrow="TU ESPACIO DE TRABAJO" title={<>Estación <em>local.</em></>} description="Construye tu archivo, comprueba las fuentes y sigue cada incorporación." /><div className="station-status"><div><Database size={19} /><span>PostgreSQL</span><strong>{health.data?.database ? 'Disponible' : 'Pendiente'}</strong></div><div><KeyRound size={19} /><span>Claude</span><strong>{health.data?.claude_configured ? 'Configurado' : 'Sin clave'}</strong></div><div><KeyRound size={19} /><span>OpenAlex</span><strong>{health.data?.openalex_configured ? 'Con clave' : 'Acceso básico'}</strong></div></div>
    {!health.data?.database && <div className="notice"><div><strong>Inicia la base de datos local</strong><p>Ejecuta scripts/start-local.ps1 desde la carpeta del proyecto. La interfaz seguirá disponible mientras preparas PostgreSQL.</p></div></div>}
    <div className="section-heading"><h2>Incorporar conocimiento</h2><label className="limit-label">Límite por consulta<select value={limit} onChange={e => setLimit(Number(e.target.value))}><option value={25}>25 registros</option><option value={100}>100 registros</option><option value={500}>500 registros</option><option value={1000}>1 000 registros</option></select></label></div><p className="small muted">Sigue el orden sugerido. El límite aplica a resultados consultados, antes del filtro de relevancia. Taxonomía e índice procesan el conjunto disponible. Sin clave OpenAlex se consulta solo la primera página.</p>
    {error && <ErrorNotice message={error} />}{notice && <p className="notice" role="status">{notice}</p>}
    <div className="source-list">{sources.map(source => <div key={source.id} className="source-row"><span className="source-number">{source.number}</span><div><h3>{source.title}</h3><p>{source.description}</p></div><Button variant="outline" size="sm" disabled={pending || running || !health.data?.database} onClick={() => run(source.id)}><ArrowDownToLine size={15} />{source.button}</Button></div>)}</div>
    <section className="coverage-block"><h2>Lo que contiene tu archivo</h2><div className="coverage-grid"><div><strong>{count(stats?.documents)}</strong><span>publicaciones con metadatos</span></div><div><strong>{stats?.documents ? `${Math.round(stats.fulltexts / stats.documents * 100)} %` : '—'}</strong><span>con texto completo local{stats?.documents ? ` (${stats.fulltexts}/${stats.documents})` : ''}</span></div><div><strong>{count(stats?.embedded)} / {count(stats?.chunks)}</strong><span>fragmentos con vector</span></div></div><p className="small muted">Cobertura global de la literatura: aún no medida. Geocodificación de artículos: fuera de esta fase. Los porcentajes describen exclusivamente tu archivo local.</p></section>
    <div className="section-heading"><h2>Historial de incorporaciones</h2><Button variant="ghost" size="sm" onClick={runs.reload}><RefreshCw size={15} />Actualizar</Button></div>{runs.loading ? <Loading /> : runs.error ? <ErrorNotice message={runs.error} /> : <div className="runs-list">{runs.data?.length === 0 && <p className="muted">Las ejecuciones aparecerán aquí con su resultado y posibles errores.</p>}{runs.data?.map(r => <div className="run-row" key={r.id}><span className={`run-icon ${r.status}`}>{r.status === 'completed' ? <Check size={16} /> : <Circle size={14} />}</span><div><strong>{sources.find(s => s.id === r.source)?.title || r.source}</strong><p>{new Date(r.started_at).toLocaleString('es-PE')} · {r.counts.processed ?? 0} procesados{r.counts.failed ? ` · ${r.counts.failed} fallos` : ''}</p>{r.error && <p className="error-text">{r.error}</p>}</div><span className="tag">{statuses[r.status] || r.status}</span></div>)}</div>}
    <section className="download-section"><h2>Una descarga citable de GBIF</h2><p>La consulta del mapa es exploratoria. Para obtener una descarga con DOI, configura GBIF_USERNAME, GBIF_PASSWORD y CONTACT_EMAIL en .env. El DOI identifica esa descarga; no se atribuye automáticamente a los registros ya consultados.</p><div className="detail-actions"><Button variant="outline" disabled={pending || !health.data?.gbif_configured} onClick={() => download()}>Solicitar descarga con DOI <ExternalLink size={14} /></Button><Button variant="ghost" disabled={pending} onClick={() => download(true)}>Comprobar estado</Button></div>{downloads.data?.map(d => <p key={d.download_key}><a className="text-link" href={d.source_url} target="_blank" rel="noreferrer">{d.download_key} ↗</a> · {d.status} · {d.doi || 'DOI aún no disponible'}</p>)}</section>
  </div>;
}
