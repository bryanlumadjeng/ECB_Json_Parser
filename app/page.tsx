"use client";

import { useState } from "react";
import UploadForm from "@/components/UploadForm";
import ProgressTracker from "@/components/ProgressTracker";
import ReportViewer, { Report } from "@/components/ReportViewer";

type AppState = "upload" | "processing" | "results" | "error";

export default function Home() {
  const [state, setState] = useState<AppState>("upload");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (formData: FormData) => {
    setState("processing");
    setError(null);

    try {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        body: formData,
      });

      const text = await res.text();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let data: any;
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error(text.trim() || `Server error ${res.status}`);
      }

      if (!res.ok) {
        throw new Error(data?.error ?? data?.detail ?? `Server error ${res.status}`);
      }

      setReport(data);
      setState("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
      setState("error");
    }
  };

  const reset = () => {
    setState("upload");
    setReport(null);
    setError(null);
  };

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <div style={styles.headerInner}>
          <div style={styles.logo}>ECB Model Evaluator</div>
          <nav style={styles.nav}>
            <span style={styles.navTag}>ECB Supervisory Guide — July 2025</span>
          </nav>
        </div>
      </header>

      <main style={styles.main}>
        {state === "upload" && (
          <div>
            <div style={styles.hero}>
              <h1 style={styles.heroTitle}>Internal Model Documentation Evaluator</h1>
              <p style={styles.heroSub}>
                Upload your model documentation and receive a structured gap analysis
                against ECB supervisory requirements for internal models.
              </p>
            </div>
            <UploadForm onSubmit={handleSubmit} loading={false} />
          </div>
        )}

        {state === "processing" && <ProgressTracker />}

        {state === "results" && report && (
          <ReportViewer report={report} onReset={reset} />
        )}

        {state === "error" && (
          <div style={styles.errorBox}>
            <h2 style={styles.errorTitle}>Evaluation Failed</h2>
            <p style={styles.errorMsg}>{error}</p>
            <button onClick={reset} style={styles.retryBtn}>Try Again</button>
          </div>
        )}
      </main>

      <footer style={styles.footer}>
        <p>ECB Supervisory Guide for Internal Models (July 2025) &mdash; For regulatory self-assessment only</p>
      </footer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", flexDirection: "column" },
  header: { background: "#1a1a2e", color: "#fff", padding: "0 24px" },
  headerInner: { maxWidth: 960, margin: "0 auto", height: 56, display: "flex",
                 alignItems: "center", justifyContent: "space-between" },
  logo: { fontWeight: 800, fontSize: 18, letterSpacing: -0.5 },
  nav: { display: "flex", gap: 16, alignItems: "center" },
  navTag: { fontSize: 12, padding: "3px 10px", background: "#2563eb", borderRadius: 12,
            fontWeight: 600 },
  main: { flex: 1, padding: "40px 24px" },
  hero: { textAlign: "center", marginBottom: 32, maxWidth: 640, margin: "0 auto 32px" },
  heroTitle: { fontSize: 30, fontWeight: 800, marginBottom: 12, lineHeight: 1.2 },
  heroSub: { fontSize: 16, color: "#555", lineHeight: 1.6 },
  errorBox: { background: "#fff", borderRadius: 12, padding: 40, maxWidth: 500, margin: "0 auto",
              textAlign: "center", boxShadow: "0 2px 12px rgba(0,0,0,0.08)" },
  errorTitle: { fontSize: 20, fontWeight: 700, color: "#dc2626", marginBottom: 12 },
  errorMsg: { color: "#555", fontSize: 14, lineHeight: 1.6, marginBottom: 24 },
  retryBtn: { padding: "10px 24px", background: "#2563eb", color: "#fff", border: "none",
              borderRadius: 6, cursor: "pointer", fontSize: 15, fontWeight: 600 },
  footer: { background: "#f0f0f0", textAlign: "center", padding: "16px 24px",
            fontSize: 12, color: "#888" },
};
