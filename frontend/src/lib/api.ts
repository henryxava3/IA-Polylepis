'use client';
import { useCallback, useEffect, useState } from 'react';

export async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${url}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'No se pudo completar la solicitud. Comprueba el servidor local.');
  }
  return response.json();
}

export function useApi<T>(url: string, interval = 0) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion(v => v + 1), []);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await request<T>(url);
        if (active) setState({ data, loading: false });
      } catch (error) {
        if (active) setState({ error: (error as Error).message, loading: false });
      }
    }
    void load();
    const timer = interval ? setInterval(load, interval) : undefined;
    return () => { active = false; if (timer) clearInterval(timer); };
  }, [url, version, interval]);
  return { ...state, reload };
}

export type Health = { database: boolean; claude_configured: boolean; openalex_configured: boolean; gbif_configured: boolean; embedding_model: string };
export type Stats = { documents: number; fulltexts: number; abstracts: number; licensed: number; occurrences: number; countries: number; unknown_uncertainty: number; chunks: number; embedded: number; taxa: number; last_sync: string | null };
export type Paper = { id: number; title: string; year: number | null; authors: string[]; journal: string; language: string; doi: string | null; abstract: string | null; license: string | null; license_evidence: string | null; text_status: string; text_error?: string; sources: { source: string; url: string }[]; chunks?: { id: number; locator: string; text: string; page: number | null }[] };
export type Filters = { years: number[]; countries: string[]; species: string[] };
export type Run = { id: number; source: string; status: string; started_at: string; counts: Record<string, number>; error: string | null };
export type Citation = { number: number; id: number; document_id: number; title: string; doi: string | null; page: number | null; locator: string; license: string; quote: string };
export type Answer = { status: string; message: string; detail?: string; segments: { text: string; citations: number[] }[]; citations: Citation[]; retrieval: string; candidates: number; latency_ms: number };
export const count = (n?: number) => n === undefined ? '—' : new Intl.NumberFormat('es-PE').format(n);
export function safeLink(value?: string | null) { return value && /^https:\/\//i.test(value) ? value : undefined; }
