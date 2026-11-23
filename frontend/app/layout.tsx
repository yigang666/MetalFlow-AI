import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MetalFlow AI",
  description: "MetalFlow AI 本地 Sandbox 工作空间",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="site-header">
          <div className="shell flex flex-wrap items-center justify-between gap-3">
            <span className="wordmark"><span aria-hidden="true">M</span>MetalFlow AI</span>
            <span className="environment">本地 Sandbox</span>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
