import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AgentShield | AI agent security',
  description: 'A dashboard preview for AI-agent compatibility and website security.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
