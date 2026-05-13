"use client";

import { useEffect } from "react";

type GlobalErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalErrorPage({ error, reset }: GlobalErrorPageProps) {
  useEffect(() => {
    console.error("HajiHaz global frontend error", error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <main className="page-shell">
          <section className="panel-card">
            <span className="eyebrow">Global frontend error</span>
            <h1>The app crashed during page load</h1>
            <p className="error-text">
              {error.message || "The page hit a client-side error. Refresh once and try again."}
            </p>
            {error.digest ? <p className="helper-text">Reference: {error.digest}</p> : null}
            <button className="primary-button" onClick={() => reset()}>
              Reload app
            </button>
          </section>
        </main>
      </body>
    </html>
  );
}
