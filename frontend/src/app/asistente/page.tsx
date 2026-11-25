'use client';
import { useState } from 'react';
import { ArrowUp, BookOpen, ArrowUpRight, MessageCircle, ShieldCheck } from 'lucide-react';
import { request, useApi, type Answer, type Health, type Stats } from '@/lib/api';
import { PageHeading, Loading } from '@/components/common';
import { Button } from '@/components/ui/button';
const suggestions = ['¿Qué se ha estudiado sobre la regeneración de Polylepis?', '¿Qué evidencia existe sobre los efectos del fuego?', '¿Qué vacíos hay en la literatura indexada?'];
export default function AssistantPage() {
  const { data: health } = useApi<Health>('/health');
  const { data: stats } = useApi<Stats>('/stats');
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [submitted, setSubmitted] = useState('');
  const [error, setError] = useState('');
  async function submit(e: React.FormEvent) {
    e.preventDefault(); if (question.trim().length < 5 || pending) return;
    setPending(true); setError(''); setAnswer(null); setSubmitted(question);
    try { setAnswer(await request<Answer>('/ask', { question: question.trim() })); }
    catch (e) { setError((e as Error).message); }
    finally { setPending(false); }
  }
  return <div className="page-wrap assistant-page"><PageHeading eyebrow="03 / CONVERSAR CON LA EVIDENCIA" title={<>Pregúntale a <em>Polylepis.</em></>} description="Una pregunta puede abrir nuevas conexiones. Cada respuesta debe volver a una fuente." />
    <div className="assistant-layout"><section className="assistant-main"><div className="assistant-intro"><span className="assistant-emblem"><MessageCircle size={28} strokeWidth={1.3} /></span><h2>Del artículo a tu pregunta.</h2><p>Consulta los textos autorizados de tu biblioteca.<br />Abre cada cita para leer el fragmento que la respalda.</p></div>
      <div className="suggestions">{suggestions.map(s => <button key={s} onClick={() => setQuestion(s)}>{s}<ArrowUpRight size={16} /></button>)}</div>
      <form className="ask-form" onSubmit={submit}><label htmlFor="question" className="sr-only">Tu pregunta sobre Polylepis</label><textarea id="question" minLength={5} maxLength={2000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="¿Qué te gustaría conocer sobre Polylepis?" rows={3} /><div><span>Solo literatura indexada · citas verificables</span><Button type="submit" disabled={pending || question.trim().length < 5}><span>{pending ? 'Consultando…' : 'Preguntar'}</span><ArrowUp size={17} /></Button></div></form>
      {pending && <Loading text="Buscando fragmentos y comprobando sus citas…" />}{error && <p className="notice notice-error" role="alert">{error}</p>}
      {answer && <section className="answer-panel" aria-live="polite"><div className="eyebrow">TU CONSULTA</div><h3>{submitted}</h3>{answer.status === 'answered' ? <><div className="answer-text">{answer.segments.map((segment, i) => <span key={i}>{segment.text}{segment.citations.map(n => <a className="citation-number" href={`#citation-${n}`} key={n}>[{n}]</a>)}</span>)}</div><div className="answer-citations"><h4>Volver a las fuentes</h4>{answer.citations.map(c => <details id={`citation-${c.number}`} key={c.number}><summary><span className="citation-chip">{c.number}</span><span>{c.title}<small>{c.locator} · {c.license.toUpperCase()}</small></span></summary><blockquote>{c.quote}</blockquote><div className="citation-actions">{c.doi && <a href={`https://doi.org/${c.doi}`} target="_blank" rel="noreferrer">Abrir DOI <ArrowUpRight size={13} /></a>}{c.page && <a href={`/api/documents/${c.document_id}/pdf#page=${c.page}`} target="_blank" rel="noreferrer">Abrir PDF · página {c.page}</a>}</div></details>)}</div></> : <div className="notice"><div><strong>{answer.message}</strong><p>{answer.detail}</p></div></div>}<div className="answer-meta">Recuperación: {answer.retrieval === 'hybrid' ? 'BM25 + vectores' : answer.retrieval === 'empty' ? 'sin corpus' : 'BM25'} · {answer.candidates} fragmentos recuperados</div></section>}
    </section><aside className="evidence-sidebar"><ShieldCheck size={22} strokeWidth={1.4} /><h3>La fuente primero.</h3><p>Si la biblioteca no contiene evidencia suficiente, el asistente lo dirá.</p><div className="evidence-rule" /><div className="evidence-stat"><BookOpen size={16} /><span>{stats?.chunks ?? '—'} fragmentos disponibles</span></div><p className="small">Los metadatos por sí solos no sustentan respuestas científicas.</p><div className={`connection-label ${health?.claude_configured ? '' : 'pending'}`}><span className="status-dot" />{health?.claude_configured ? 'Claude configurado' : 'Clave de Claude pendiente'}</div>{!health?.claude_configured && <p className="small">Configura ANTHROPIC_API_KEY en el archivo .env y reinicia el backend.</p>}<p className="small muted">La consulta y los fragmentos recuperados se envían a Claude. Tus archivos permanecen almacenados localmente.</p></aside></div>
  </div>;
}
