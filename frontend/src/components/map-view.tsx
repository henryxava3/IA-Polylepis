'use client';
import { useEffect, useRef, useState } from 'react';
import maplibregl, { type GeoJSONSource } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import 'leaflet/dist/leaflet.css';
import type * as Leaflet from 'leaflet';
import { ErrorNotice } from './common';

export type OccurrenceCollection = FeatureCollection<Point> & { total: number; truncated: boolean; provenance: string };

function CompatibleMap({ data }: { data: OccurrenceCollection }) {
  const container = useRef<HTMLDivElement>(null);
  const layer = useRef<Leaflet.GeoJSON | null>(null);
  const latest = useRef(data);
  const [error, setError] = useState('');
  useEffect(() => { latest.current = data; layer.current?.clearLayers().addData(data); }, [data]);
  useEffect(() => {
    let active = true;
    let instance: Leaflet.Map | undefined;
    import('leaflet').then(L => {
      if (!active || !container.current) return;
      instance = L.map(container.current, { preferCanvas: true, zoomControl: false }).setView([-14, -72], 3);
      L.control.zoom({position:'topright'}).addTo(instance);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(instance);
      layer.current = L.geoJSON(latest.current, {
        pointToLayer: (feature, location) => L.circleMarker(location, {radius:6, fillColor:feature.properties?.uncertainty_m ? '#315a46' : '#a56745', color:'#fff', weight:1.5, fillOpacity:0.85}),
        onEachFeature: (feature, item) => {
          const p = feature.properties || {};
          const panel = document.createElement('div'); panel.className = 'map-popup';
          const title = document.createElement('h3'); title.textContent = p.accepted_name; panel.append(title);
          for (const text of [p.locality || 'Localidad no declarada', `País: ${p.country || 'Sin dato'} · Colecta: ${p.collected_year || 'Sin año'}`, p.uncertainty_m ? `Incertidumbre: ${p.uncertainty_m} m` : 'Incertidumbre desconocida', 'Sin verificación independiente', `Licencia: ${p.license || 'No declarada'}`]) {
            const line = document.createElement('p'); line.textContent = text; panel.append(line);
          }
          for (const [label, url] of [['Ver registro GBIF ↗', `https://www.gbif.org/occurrence/${encodeURIComponent(p.gbif_id)}`], ['Conjunto de datos ↗', `https://www.gbif.org/dataset/${encodeURIComponent(p.dataset_key)}`]]) {
            const a = document.createElement('a'); a.textContent = label; a.href = url; a.target = '_blank'; a.rel = 'noreferrer'; panel.append(a);
          }
          item.bindPopup(panel);
          if (p.uncertainty_m && feature.geometry.type === 'Point') {
            const coordinates = feature.geometry.coordinates;
            const circle = L.circle([coordinates[1], coordinates[0]], {radius:p.uncertainty_m,color:'#315a46',weight:1,fillOpacity:0.1});
            item.on('popupopen', () => { if (instance) circle.addTo(instance); });
            item.on('popupclose', () => circle.remove());
          }
        },
      }).addTo(instance);
    }).catch(() => { if (active) setError('No se pudo iniciar el mapa compatible. Consulta la lista de registros.'); });
    return () => { active = false; instance?.remove(); layer.current = null; };
  }, []);
  return <div className="map-frame"><div className="map-canvas" ref={container} aria-label="Mapa compatible de registros de Polylepis" />{error && <div className="map-error"><ErrorNotice message={error} /></div>}<div className="map-legend"><span><i className="legend-known" />Incertidumbre declarada</span><span><i className="legend-unknown" />Sin incertidumbre declarada</span><small>Vista compatible sin WebGL · puntos individuales</small></div></div>;
}

export default function MapView({ data }: { data: OccurrenceCollection }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const latestData = useRef(data);
  const [error, setError] = useState('');
  const [compatible, setCompatible] = useState(false);
  useEffect(() => { latestData.current = data; if (map.current?.isStyleLoaded()) (map.current.getSource('occurrences') as GeoJSONSource)?.setData(data); }, [data]);
  useEffect(() => {
    if (!container.current) return;
    let instance: maplibregl.Map;
    try {
      instance = new maplibregl.Map({ container: container.current, center: [-73, -13], zoom: 3.25,
        style: { version: 8, sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, maxzoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' } }, layers: [{ id: 'basemap', type: 'raster', source: 'osm', paint: { 'raster-saturation': -0.7 } }] },
        attributionControl: { compact: false } });
      map.current = instance;
      instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      instance.on('load', () => {
        instance.addSource('occurrences', { type: 'geojson', data: latestData.current, cluster: true, clusterRadius: 38, clusterMaxZoom: 12 });
        instance.addLayer({ id: 'clusters', type: 'circle', source: 'occurrences', filter: ['has', 'point_count'], paint: { 'circle-color': '#244e3e', 'circle-radius': ['step', ['get', 'point_count'], 15, 30, 21, 100, 28], 'circle-opacity': 0.85, 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } });
        instance.addLayer({ id: 'points', type: 'circle', source: 'occurrences', filter: ['!', ['has', 'point_count']], paint: { 'circle-color': ['case', ['==', ['get', 'uncertainty_m'], null], '#a56745', '#315a46'], 'circle-radius': 5.5, 'circle-stroke-width': 1.5, 'circle-stroke-color': '#fff' } });
        instance.on('click', 'clusters', async e => {
          const feature = e.features?.[0]; if (!feature || feature.geometry.type !== 'Point') return;
          const zoom = await (instance.getSource('occurrences') as GeoJSONSource).getClusterExpansionZoom(feature.properties.cluster_id);
          instance.easeTo({ center: feature.geometry.coordinates as [number, number], zoom, duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 250 });
        });
        instance.on('click', 'points', e => {
          const feature = e.features?.[0]; if (!feature || feature.geometry.type !== 'Point') return;
          const p = feature.properties;
          const panel = document.createElement('div'); panel.className = 'map-popup';
          const heading = document.createElement('h3'); heading.textContent = p.accepted_name; panel.append(heading);
          const lines = [p.locality || 'Localidad no declarada', `País: ${p.country || 'Sin dato'} · Año de colecta: ${p.collected_year || 'Sin dato'}`, p.uncertainty_m ? `Incertidumbre declarada: ${p.uncertainty_m} m` : 'Incertidumbre desconocida', 'Sin verificación independiente', `Licencia: ${p.license || 'No declarada'}`, `Registro GBIF ${p.gbif_id}`];
          for (const line of lines) { const element = document.createElement('p'); element.textContent = line; panel.append(element); }
          const link = document.createElement('a'); link.href = `https://www.gbif.org/occurrence/${encodeURIComponent(p.gbif_id)}`; link.target = '_blank'; link.rel = 'noreferrer'; link.textContent = 'Ver registro y procedencia ↗'; panel.append(link);
          const dataset = document.createElement('a'); dataset.href = `https://www.gbif.org/dataset/${encodeURIComponent(p.dataset_key)}`; dataset.target = '_blank'; dataset.rel = 'noreferrer'; dataset.textContent = 'Conjunto de datos ↗'; panel.append(dataset);
          new maplibregl.Popup({ maxWidth: '320px' }).setLngLat(feature.geometry.coordinates as [number, number]).setDOMContent(panel).addTo(instance);
        });
        ['points', 'clusters'].forEach(layer => { instance.on('mouseenter', layer, () => { instance.getCanvas().style.cursor = 'pointer'; }); instance.on('mouseleave', layer, () => { instance.getCanvas().style.cursor = ''; }); });
      });
      instance.on('error', () => setError('No se pudo cargar parte del mapa. La capa base necesita conexión a Internet.'));
    } catch { queueMicrotask(() => setCompatible(true)); }
    return () => { instance?.remove(); map.current = null; };
  }, []);
  if (compatible) return <CompatibleMap data={data} />;
  return <div className="map-frame"><div ref={container} className="map-canvas" aria-label="Mapa de registros de Polylepis" />{error && <div className="map-error"><ErrorNotice message={error} /></div>}<div className="map-legend"><span><i className="legend-known" />Incertidumbre declarada</span><span><i className="legend-unknown" />Sin incertidumbre declarada</span><small>Los círculos agrupados reúnen varios registros.</small></div></div>;
}
