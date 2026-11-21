import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/inter';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'MoMo Shield · FraudOps Command Center', template: '%s · MoMo Shield' },
  description: 'A real-time mobile money fraud intelligence command center for Ghana.',
  applicationName: 'MoMo Shield',
  manifest: '/manifest.json',
};
export const viewport: Viewport = { width: 'device-width', initialScale: 1, maximumScale: 1, viewportFit: 'cover', themeColor: '#090d12' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className="dark"><body suppressHydrationWarning>{children}</body></html>;
}

// PWA installability extension: add valid 192x192 and 512x512 icons in public/ and list them in
// public/manifest.json; add a service worker at public/sw.js and register it from a client-side
// effect. This demo deliberately does not cache pages or intercept network requests.
