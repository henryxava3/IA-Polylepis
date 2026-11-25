import type { Metadata } from 'next';
import { Shell } from '@/components/shell';
import './globals.css';
export const metadata: Metadata = { title: 'Polylepis · Archivo científico', description: 'Biblioteca, evidencia y territorio del género Polylepis. Estación local de investigación.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body><a className="skip-link" href="#main-content">Saltar al contenido</a><Shell>{children}</Shell></body></html>;
}
