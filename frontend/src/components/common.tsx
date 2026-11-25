import { AlertCircle, ArrowRight, Database, LoaderCircle } from 'lucide-react';
import Link from 'next/link';
import { Button } from './ui/button';
export function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice notice-error" role="alert"><AlertCircle size={19} /><div><strong>No pudimos cargar estos datos</strong><p>{message}</p>{retry && <Button variant="outline" size="sm" onClick={retry}>Reintentar</Button>}</div></div>;
}
export function Loading({ text = 'Consultando el archivo local…' }: { text?: string }) { return <div className="loading" role="status"><LoaderCircle size={20} className="spin" />{text}</div>; }
export function Empty({ title, description, setup = false }: { title: string; description: string; setup?: boolean }) {
  return <div className="empty"><Database size={34} strokeWidth={1.2} /><h3>{title}</h3><p>{description}</p>{setup && <Link href="/estacion" className="text-link">Preparar mi biblioteca <ArrowRight size={16} /></Link>}</div>;
}
export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: React.ReactNode; description: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}
