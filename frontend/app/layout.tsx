import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HajiHaz AI",
  description: "Personal AI system with RAG-backed chat and knowledge management."
};

const PRE_HYDRATION_SANITIZER = `
(() => {
  const targets = [document.documentElement, document.body];
  const extensionAttributes = [
    "cz-shortcut-listen",
    "data-new-gr-c-s-check-loaded",
    "data-gr-ext-installed",
    "data-lt-installed",
    "data-gramm",
    "data-lastpass-icon-root",
    "data-1p-ignore",
    "inmaintabuse"
  ];

  for (const target of targets) {
    if (!target) continue;
    for (const attribute of extensionAttributes) {
      if (target.hasAttribute(attribute)) {
        target.removeAttribute(attribute);
      }
    }
  }
})();
`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <script dangerouslySetInnerHTML={{ __html: PRE_HYDRATION_SANITIZER }} />
        {children}
      </body>
    </html>
  );
}
