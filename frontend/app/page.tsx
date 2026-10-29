import './globals.css';

export const metadata = {
  title: 'AgentShield',
  description: 'AI-agent compatibility and security platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

