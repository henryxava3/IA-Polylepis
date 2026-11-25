'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { BookOpen, Map, MessageCircle, GitBranch, SlidersHorizontal, ArrowUpRight, TreePine, Moon, Sun, Menu, X, CircleHelp } from 'lucide-react';
import { useApi, type Health } from '@/lib/api';
import { messages } from '@/lib/i18n';
import { Button } from './ui/button';

const text = messages.es;
const nav = [
  { href: '/', label: text.library, icon: BookOpen },
  { href: '/mapa', label: text.map, icon: Map },
  { href: '/asistente', label: text.assistant, icon: MessageCircle },
  { href: '/taxonomia', label: text.taxonomy, icon: GitBranch },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { data: health } = useApi<Health>('/health', 15000);
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(false);
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; }, [dark]);
  return <div className="app-shell">
    <div className="mobile-top"><Link className="brand-small" href="/"><TreePine size={22} /> polylepis</Link><Button variant="ghost" size="icon" aria-label={open ? 'Cerrar navegación' : 'Abrir navegación'} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</Button></div>
    {open && <button className="nav-scrim" aria-label="Cerrar menú" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <Link href="/" className="brand" onClick={() => setOpen(false)}><span className="brand-symbol"><TreePine size={29} strokeWidth={1.35} /></span><span>polylepis<small>OBSERVATORIO DEL GÉNERO</small></span></Link>
      <div className="sidebar-group-label">EXPLORAR</div>
      <nav aria-label="Navegación principal">{nav.map(item => <Link key={item.href} className={`nav-item ${path === item.href ? 'active' : ''}`} aria-current={path === item.href ? 'page' : undefined} href={item.href} onClick={() => setOpen(false)}><item.icon size={19} strokeWidth={1.7} /><span>{item.label}</span>{path === item.href && <span className="nav-dot" />}</Link>)}</nav>
      <div className="sidebar-note"><span className="mini-rule" /><p>Conocimiento que conecta<br />los bosques de los Andes.</p><span className="note-coordinates">LITERATURA · TERRITORIO · EVIDENCIA</span></div>
      <div className="sidebar-bottom"><Link className={`nav-item ${path === '/metodologia' ? 'active' : ''}`} href="/metodologia" onClick={() => setOpen(false)}><CircleHelp size={18} />{text.methodology}</Link><Link className={`nav-item ${path === '/estacion' ? 'active' : ''}`} href="/estacion" onClick={() => setOpen(false)}><SlidersHorizontal size={18} />{text.local}</Link><div className="local-status"><span className={`status-dot ${health?.database ? 'online' : ''}`} /><span>{health?.database ? 'Datos en tu laptop' : 'Base de datos pendiente'}</span><Button variant="ghost" size="icon" onClick={() => setDark(!dark)} aria-label={dark ? 'Activar tema claro' : 'Activar tema oscuro'}>{dark ? <Sun size={17} /> : <Moon size={17} />}</Button></div></div>
    </aside>
    <main id="main-content" className="main-content"><header className="topbar"><span>ARCHIVO CIENTÍFICO <span className="topbar-divider">/</span> <em>Polylepis</em> · Rosaceae</span><Link href="/metodologia">Nuestro enfoque <ArrowUpRight size={14} /></Link></header>{children}<footer className="page-footer"><span>Polylepis · Un archivo vivo de los Andes</span><span>Edición local <span className="tiny-dot">·</span> Fases 0–1</span></footer></main>
  </div>;
}
