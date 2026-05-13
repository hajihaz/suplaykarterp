"use client";

import { useEffect } from "react";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error("HajiHaz frontend error", error);
  }, [error]);

  return (
    <main className="page-shell">
      <section className="panel-card">
        <span className="eyebrow">Frontend error</span>
        <h1>Something broke in the browser</h1>
        <p className="error-text">
          {error.message || "The page hit a client-side error. Refresh once and try again."}
        </p>
        {error.digest ? <p className="helper-text">Reference: {error.digest}</p> : null}
        <button className="primary-button" onClick={() => reset()}>
          Try again
        </button>
      </section>
    </main>
  );
}
