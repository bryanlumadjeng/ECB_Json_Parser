"use client";

import { useState, useRef } from "react";

export type ScopeOption = "auto" | "all" | "credit_risk" | "market_risk_crr2" | "market_risk_crr3" | "ccr";

interface Props {
  onSubmit: (formData: FormData) => void;
  loading: boolean;
}

const SCOPE_LABELS: Record<ScopeOption, string> = {
  auto: "Auto-detect",
  all: "All chapters",
  credit_risk: "Credit Risk (IRB)",
  market_risk_crr2: "Market Risk – CRR2",
  market_risk_crr3: "Market Risk – CRR3",
  ccr: "Counterparty Credit Risk",
};

export default function UploadForm({ onSubmit, loading }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [scope, setScope] = useState<ScopeOption>("auto");
  const [maxChapters, setMaxChapters] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("scope", scope);
    fd.append("max_chapters", String(maxChapters));
    onSubmit(fd);
  };

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <h2 style={styles.heading}>Upload Model Documentation</h2>
      <p style={styles.hint}>
        Upload a PDF, text, or Excel file containing your bank&apos;s internal model documentation.
        The agent will evaluate it against the ECB Supervisory Guide for Internal Models (July 2025).
      </p>

      <div style={styles.field}>
        <label style={styles.label}>Document (PDF, TXT, or XLSX)</label>
        <div
          style={{ ...styles.dropzone, ...(file ? styles.dropzoneActive : {}) }}
          onClick={() => fileRef.current?.click()}
        >
          {file ? (
            <span style={styles.fileName}>{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
          ) : (
            <span>Click to select a file, or drag and drop here</span>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt,.xlsx"
            style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
      </div>

      <div style={styles.row}>
        <div style={styles.field}>
          <label style={styles.label}>Scope</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as ScopeOption)}
            style={styles.select}
          >
            {Object.entries(SCOPE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
        </div>

        <div style={styles.field}>
          <label style={styles.label}>Max chapters (0 = all)</label>
          <input
            type="number"
            min={0}
            max={76}
            value={maxChapters}
            onChange={(e) => setMaxChapters(Number(e.target.value))}
            style={styles.input}
          />
        </div>
      </div>

      <button type="submit" disabled={!file || loading} style={styles.button}>
        {loading ? "Evaluating…" : "Start Evaluation"}
      </button>
    </form>
  );
}

const styles: Record<string, React.CSSProperties> = {
  form: { background: "#fff", borderRadius: 12, padding: 32, maxWidth: 680, margin: "0 auto",
          boxShadow: "0 2px 12px rgba(0,0,0,0.08)" },
  heading: { fontSize: 22, fontWeight: 700, marginBottom: 8 },
  hint: { color: "#555", fontSize: 14, marginBottom: 24, lineHeight: 1.6 },
  field: { marginBottom: 20, flex: 1 },
  label: { display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "#444" },
  dropzone: { border: "2px dashed #c5cae9", borderRadius: 8, padding: "24px 16px",
               textAlign: "center", cursor: "pointer", color: "#666", fontSize: 14,
               transition: "border-color 0.2s" },
  dropzoneActive: { borderColor: "#2563eb", background: "#eff6ff", color: "#1d4ed8" },
  fileName: { fontWeight: 600 },
  row: { display: "flex", gap: 16 },
  select: { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #ddd",
             fontSize: 14, outline: "none" },
  input: { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #ddd",
           fontSize: 14, outline: "none" },
  button: { width: "100%", padding: "12px 24px", background: "#2563eb", color: "#fff",
            border: "none", borderRadius: 8, fontSize: 16, fontWeight: 600, cursor: "pointer",
            marginTop: 8, opacity: 1, transition: "opacity 0.2s" },
};
