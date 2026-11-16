import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Projeto Felix - Gestão de Cupons NFP",
  description: "Monitoramento e processamento automatizado de cupons da Nota Fiscal Paulista",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body
        suppressHydrationWarning
        className="min-h-screen bg-slate-950 text-slate-100 flex flex-col antialiased"
      >
        {children}
      </body>
    </html>
  );
}

