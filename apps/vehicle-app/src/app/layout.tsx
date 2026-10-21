import {HealthConsentGate} from '../components/HealthConsentGate';
import type { Metadata } from 'next';
import './globals.css';
import { VehicleContextProvider } from '../context/VehicleContext';
import { ReminderNotice } from '../components/ReminderNotice';
import { CockpitHeader } from '../components/CockpitHeader';
import {LocalizedFooter} from '../components/LocalizedFooter';
import {LanguageProvider} from '../i18n/LanguageProvider';
import { PRODUCT_NAME, PRODUCT_TAGLINE, PRODUCT_DESCRIPTION } from '../utils/brand';

export const metadata: Metadata = {
  title: `${PRODUCT_NAME} — ${PRODUCT_TAGLINE}`,
  description: PRODUCT_DESCRIPTION,
  applicationName: PRODUCT_NAME,
  icons: { icon: '/brand/attune-more/icon.svg', apple: '/brand/attune-more/icon-192.png' },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" className="dark">
      <body className="min-h-screen bg-cockpit-bg text-cockpit-text flex flex-col antialiased selection:bg-togg-turquoise selection:text-togg-darkBlue">
        <LanguageProvider><VehicleContextProvider>
          <CockpitHeader />
          <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 md:p-6 lg:p-8">
            <ReminderNotice />
            <HealthConsentGate>{children}</HealthConsentGate>
          </main>
          <LocalizedFooter/>
        </VehicleContextProvider></LanguageProvider>
      </body>
    </html>
  );
}
