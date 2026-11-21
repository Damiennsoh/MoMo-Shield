import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/inter';
import { PwaRegistration } from '@/components/PwaRegistration';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'MoMo Shield · FraudOps Command Center', template: '%s · MoMo Shield' },
  description: 'A mobile money fraud operations command center for reviewing live sandbox telemetry, risk decisions, and alerts.',
  applicationName: 'MoMo Shield',
  manifest: '/manifest.json',
};
export const viewport: Viewport = { width: 'device-width', initialScale: 1, viewportFit: 'cover', themeColor: '#0b1220' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body suppressHydrationWarning><PwaRegistration />{children}</body></html>;
}
