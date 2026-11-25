'use client';
import dynamic from 'next/dynamic';
import { useState } from 'react';
import { MapPin, ExternalLink } from 'lucide-react';
import { PageHeading, ErrorNotice, Loading, Empty } from '@/components/common';
import { useApi, count, type Filters } from '@/lib/api';
import type { OccurrenceCollection } from '@/components/map-view';
const MapView = dynamic(() => import('@/components/map-view'), { ssr: false, loading: () => <Loading text="Preparando el geovisor…" /> });
const names: Record<string, string> = { PE: 'Perú', BO: 'Bolivia', EC: 'Ecuador', CO: 'Colombia', VE: 'Venezuela', AR: 'Argentina', CL: 'Chile' };
export default function MapPage() {
  const [country, setCountry] = useState(''); const [species, setSpecies] = useState('');
  const { data: filters } = useApi<Filters>('/filters');
  const records = useApi<OccurrenceCollection>(`/occurrences?${new URLSearchParams({ country, species })}`);
  return <div className="page-wrap"><PageHeading eyebrow="02 / EXPLORAR EL TERRITORIO" title={<>Un género, <em>muchos paisajes.</em></>} description="Registros de ocurrencia de GBIF, con su procedencia y calidad declarada." />
    <div className="map-filter-bar"><label><span>País</span><select value={country} onChange={e => setCountry(e.target.value)}><option value="">Todos los países</option>{filters?.countries.map(c => <option key={c} value={c}>{names[c] || c}</option>)}</select></label><label className="species-filter"><span>Especie según GBIF</span><select value={species} onChange={e => setSpecies(e.target.value)}><option value="">Todas las especies</option>{filters?.species.map(s => <option key={s}>{s}</option>)}</select></label><span className="record-total"><MapPin size={17} />{count(records.data?.total)} registros</span></div>
    {records.loading ? <Loading /> : records.error ? <ErrorNotice message={records.error} retry={records.reload} /> : records.data && <><MapView data={records.data} /><div className="map-caption"><span>Coordenadas originales de GBIF · WGS84</span><span>Consulta exploratoria · sin DOI de descarga</span></div>{records.data.truncated && <p className="notice">Se muestran los primeros 10 000 registros de {count(records.data.total)}. Reduce el conjunto con los filtros.</p>}
      {records.data.total === 0 ? <Empty title="Aún no hay registros para esta selección" description="Incorpora registros GBIF desde la estación local o amplía los filtros." setup /> : <details className="record-list"><summary>Consultar registros en una lista accesible (primeros 100)</summary>{records.data.features.slice(0, 100).map(f => <div className="record-row" key={f.id}><div><strong>{f.properties?.accepted_name}</strong><p>{f.properties?.locality || 'Localidad no declarada'} · {f.properties?.country}</p><small>{f.properties?.confidence} · {f.properties?.license || 'Licencia no declarada'}</small></div><a href={`https://www.gbif.org/occurrence/${f.id}`} target="_blank" rel="noreferrer" aria-label={`Ver registro GBIF ${f.id}`}><ExternalLink size={17} /></a></div>)}</details>}</>}
  </div>;
}
