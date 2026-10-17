import Link from 'next/link';
import {HealthConsentGate} from '../components/HealthConsentGate';
import type { Metadata } from 'next';
import './globals.css';
import { VehicleContextProvider } from '../context/VehicleContext';
import { ReminderNotice } from '../components/ReminderNotice';
import { CockpitHeader } from '../components/CockpitHeader';

export const metadata: Metadata = {
  title: 'Attune.more — Togg Kişiselleştirilmiş Sağlık ve İyi Oluş',
  description: 'Togg için yapay zekâ destekli kişiselleştirilmiş sağlık ve iyi oluş deneyimi.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" className="dark">
      <body className="min-h-screen bg-cockpit-bg text-cockpit-text flex flex-col antialiased selection:bg-togg-turquoise selection:text-togg-darkBlue">
        <VehicleContextProvider>
          <CockpitHeader />
          <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 md:p-6 lg:p-8">
            <ReminderNotice />
            <HealthConsentGate>{children}</HealthConsentGate>
          </main>
          <footer className="border-t border-cockpit-border/40 py-3 px-6 text-center text-xs text-slate-500 bg-cockpit-surface/50">
            <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 max-w-[1600px] mx-auto text-[11px]">
              <span className="font-semibold text-slate-300 tracking-wide">Attune<span className="text-togg-turquoise">.more</span></span>
              <span>•</span>
              <span className="text-slate-400">Togg Kişiselleştirilmiş Sağlık Deneyimi</span>
              <span>•</span>
              <span className="text-slate-500">Tıbbi teşhis içermez; ön değerlendirme ve değişim takibi amaçlıdır.</span>

            </div>
            <div className="mt-2"><Link href="/privacy" className="inline-flex min-h-touch items-center px-3 text-togg-turquoise underline underline-offset-4 focus-visible:outline focus-visible:outline-2">Gizlilik &amp; İzinler</Link></div>
          </footer>
        </VehicleContextProvider>
      </body>
    </html>
  );
}
