'use client';
import { useState } from 'react';
import Link from 'next/link';
import { Search, ArrowUpRight, ArrowRight, BookOpen, FileCheck2, MapPin, Layers, ChevronLeft, ChevronRight, X, ExternalLink } from 'lucide-react';
import { useApi, count, safeLink, type Paper, type Stats, type Filters } from '@/lib/api';
import { Empty, ErrorNotice, Loading, PageHeading } from '@/components/common';
import { Button } from '@/components/ui/button';

function PaperDetails({ id, close }: { id: number; close: () => void }) {
  const { data, loading, error } = useApi<Paper>(`/documents/${id}`);
  return <dialog open className="paper-dialog" aria-label="Detalle del documento" onKeyDown={e => { if (e.key === 'Escape') close(); }}><div className="dialog-head"><span className="eyebrow">DOCUMENTO DEL ARCHIVO</span><Button autoFocus variant="ghost" size="icon" aria-label="Cerrar detalle" onClick={close}><X /></Button></div>{loading ? <Loading /> : error ? <ErrorNotice message={error} /> : data && <>
    <h2>{data.title}</h2><p className="muted">{data.authors.join(' · ')} · {data.year ?? 'Sin año'}</p>
    <div className="detail-actions">{data.doi && <a className="button button-outline" href={`https://doi.org/${data.doi}`} target="_blank" rel="noreferrer">Abrir DOI <ExternalLink size={15} /></a>}{data.text_status === 'fulltext' && <a className="button button-primary" href={`/api/documents/${id}/pdf`} target="_blank" rel="noreferrer">PDF local autorizado <ArrowUpRight size={15} /></a>}</div>
    <h3>Resumen</h3><p className="abstract-text">{data.abstract || 'No se almacena un resumen cuando sus derechos de reutilización no están confirmados.'}</p>
    <div className="provenance"><strong>Procedencia y derechos</strong><p>Licencia: {data.license?.toUpperCase() || 'Sin autorización de texto confirmada'}</p>{data.sources.map(s => <a key={s.source} href={safeLink(s.url)} target="_blank" rel="noreferrer">{s.source} <ArrowUpRight size={13} /></a>)}</div>
    {data.text_error && <p className="notice">{data.text_error}</p>}
    <h3>Fragmentos disponibles · {data.chunks?.length || 0}</h3>{data.chunks?.map(c => <details key={c.id} className="fragment"><summary>{c.locator} · fragmento {c.id}</summary><blockquote>{c.text}</blockquote></details>)}
  </>}</dialog>;
}

export default function Library() {
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [year, setYear] = useState('');
  const [access, setAccess] = useState('all');
  const [source, setSource] = useState('all');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const { data: stats } = useApi<Stats>('/stats');
  const { data: filters } = useApi<Filters>('/filters');
  const params = new URLSearchParams({ q: search, access, source, page: String(page) });
  if (year) params.set('year', year);
  const papers = useApi<{ items: Paper[]; total: number; page_size: number }>(`/documents?${params}`);
  const metrics = [{ label: 'PUBLICACIONES', value: stats?.documents, icon: BookOpen }, { label: 'TEXTOS COMPLETOS LOCALES', value: stats?.fulltexts, icon: FileCheck2 }, { label: 'REGISTROS GEOGRÁFICOS', value: stats?.occurrences, icon: MapPin }, { label: 'FRAGMENTOS CON EVIDENCIA', value: stats?.chunks, icon: Layers }];
  return <div className="page-wrap">
    <PageHeading eyebrow="01 / EXPLORAR EL CONOCIMIENTO" title={<>Biblioteca de <em>Polylepis</em></>} description="La literatura del género, reunida para descubrir, conectar y preguntar." action={<Link href="/asistente" className="button button-outline">Pregúntale a Polylepis <ArrowUpRight size={17} /></Link>} />
    <div className="metrics">{metrics.map(m => <div className="metric" key={m.label}><div className="metric-label">{m.label}<m.icon size={16} strokeWidth={1.5} /></div><div className="metric-value">{count(m.value)}</div></div>)}</div>
    <section className="library-section" aria-label="Buscar publicaciones"><div className="section-heading"><h2>Explorar publicaciones</h2><span className="small muted">OpenAlex <span className="tiny-dot">·</span> Crossref</span></div>
      <form className="search-form" onSubmit={e => { e.preventDefault(); setSearch(query); setPage(1); }}><Search size={21} strokeWidth={1.6} /><label className="sr-only" htmlFor="library-query">Buscar publicaciones</label><input id="library-query" value={query} onChange={e => setQuery(e.target.value)} placeholder="Busca por título, especie o tema…" /><Button type="submit">Buscar <ArrowRight size={16} /></Button></form>
      <div className="filter-row"><label><span>Año</span><select value={year} onChange={e => { setYear(e.target.value); setPage(1); }}><option value="">Todos los años</option>{filters?.years.map(y => <option key={y}>{y}</option>)}</select></label><label><span>Disponibilidad</span><select value={access} onChange={e => { setAccess(e.target.value); setPage(1); }}><option value="all">Todos los documentos</option><option value="fulltext">Texto completo local</option><option value="licensed">Licencia abierta verificada</option></select></label><label><span>Fuente</span><select value={source} onChange={e => { setSource(e.target.value); setPage(1); }}><option value="all">Todas las fuentes</option><option value="openalex">OpenAlex</option><option value="crossref">Crossref</option></select></label><span className="result-count">{papers.data ? `${count(papers.data.total)} publicaciones` : 'Consultando…'}</span></div>
      {papers.loading ? <Loading /> : papers.error ? <ErrorNotice message={papers.error} retry={papers.reload} /> : papers.data?.items.length === 0 ? <Empty title={search || year || access !== 'all' || source !== 'all' ? 'No hay coincidencias' : 'Tu archivo empieza aquí'} description={search || year || access !== 'all' || source !== 'all' ? 'Prueba otra búsqueda o amplía los filtros.' : 'Conecta las fuentes para incorporar publicaciones reales y construir tu biblioteca local.'} setup={!stats?.documents} /> : <div className="paper-list">{papers.data?.items.map((paper, index) => <article className="paper-row" key={paper.id}><div className="paper-index">{String((page - 1) * 20 + index + 1).padStart(2, '0')}</div><div className="paper-content"><div className="paper-meta"><span>{paper.year ?? 'SIN AÑO'}</span><span className="meta-separator" />{paper.journal || 'Publicación científica'}{paper.language && <span className="language-badge">{paper.language}</span>}</div><h3><button onClick={() => setSelected(paper.id)}>{paper.title}</button></h3><p className="paper-authors">{paper.authors.slice(0, 3).join(', ') || 'Autoría no disponible'}{paper.authors.length > 3 ? ' y otros' : ''}</p><div className="paper-tags"><span className={`tag ${paper.text_status === 'fulltext' ? 'tag-green' : ''}`}>{paper.text_status === 'fulltext' ? 'Texto completo' : paper.text_status === 'abstract' ? 'Resumen indexado' : 'Metadatos'}</span>{paper.license && <span className="license-label">{paper.license.toUpperCase()}</span>}<span className="paper-source">{paper.sources?.map(s => s.source).join(' + ')}</span></div></div><button className="paper-open" aria-label={`Ver documento: ${paper.title}`} onClick={() => setSelected(paper.id)}><ArrowUpRight size={22} strokeWidth={1.5} /></button></article>)}</div>}
      {!!papers.data?.total && <div className="pagination"><span>Página {page} de {Math.ceil(papers.data.total / 20)}</span><div><Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} />Anterior</Button><Button variant="outline" size="sm" disabled={page * 20 >= papers.data.total} onClick={() => setPage(page + 1)}>Siguiente<ChevronRight size={16} /></Button></div></div>}
    </section>
    <div className="editorial-note"><span className="editorial-number">↗</span><div><h3>La evidencia tiene un lugar.</h3><p>Explora los registros del género y consulta su procedencia en el geovisor.</p></div><Link className="text-link" href="/mapa">Explorar el mapa <ArrowRight size={17} /></Link></div>
    {selected !== null && <><button className="dialog-scrim" aria-label="Cerrar documento" onClick={() => setSelected(null)} /><PaperDetails id={selected} close={() => setSelected(null)} /></>}
  </div>;
}
