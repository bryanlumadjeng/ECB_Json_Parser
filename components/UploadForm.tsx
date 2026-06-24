"use client";

import { useState, useRef, useEffect } from "react";

export type ScopeOption = "auto" | "all" | "credit_risk" | "market_risk_crr2" | "market_risk_crr3" | "ccr";

interface Chapter {
  id: string;
  display_name: string;
  zone: string;
}

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

const ZONE_LABELS: Record<string, string> = {
  overarching: "Overarching",
  credit_risk: "Credit Risk",
  market_risk_crr2: "Market Risk CRR2",
  market_risk_crr3: "Market Risk CRR3",
  ccr: "CCR",
};

export default function UploadForm({ onSubmit, loading }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [scope, setScope] = useState<ScopeOption>("auto");
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [chaptersLoading, setChaptersLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scope === "auto") {
      setChapters([]);
      setSelectedIds(new Set());
      return;
    }
    setChaptersLoading(true);
    fetch(`/api/chapters?scope=${scope}`)
      .then(r => r.json())
      .then(data => {
        const chs: Chapter[] = data.chapters ?? [];
        setChapters(chs);
        setSelectedIds(new Set(chs.map(c => c.id)));
      })
      .catch(() => setChapters([]))
      .finally(() => setChaptersLoading(false));
  }, [scope]);

  const toggleChapter = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("scope", scope);
    if (scope !== "auto" && selectedIds.size < chapters.length) {
      fd.append("selected_chapters", [...selectedIds].join(","));
    }
    onSubmit(fd);
  };

  const allSelected = chapters.length > 0 && selectedIds.size === chapters.length;
  const noneSelected = selectedIds.size === 0;
  const canSubmit = file && !loading && (scope === "auto" || selectedIds.size > 0);

  // Group chapters by zone for display
  const grouped: Record<string, Chapter[]> = {};
  for (const ch of chapters) {
    (grouped[ch.zone] ??= []).push(ch);
  }
  const zones = Object.keys(grouped);

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

      {scope === "auto" ? (
        <p style={styles.autoNote}>
          Chapters will be selected automatically based on the document content.
        </p>
      ) : chaptersLoading ? (
        <p style={styles.autoNote}>Loading chapters…</p>
      ) : chapters.length > 0 && (
        <div style={styles.field}>
          <div style={styles.chapterHeader}>
            <label style={styles.label}>
              Chapters
              <span style={styles.chapterCount}>
                {selectedIds.size} of {chapters.length} selected
              </span>
            </label>
            <div style={styles.chapterActions}>
              <button type="button" style={styles.actionBtn}
                onClick={() => setSelectedIds(new Set(chapters.map(c => c.id)))}
                disabled={allSelected}>
                Select all
              </button>
              <button type="button" style={styles.actionBtn}
                onClick={() => setSelectedIds(new Set())}
                disabled={noneSelected}>
                Clear
              </button>
            </div>
          </div>

          <div style={styles.chapterList}>
            {zones.map(zone => (
              <div key={zone}>
                <div style={styles.zoneLabel}>
                  {ZONE_LABELS[zone] ?? zone}
                  <span style={styles.zoneCount}>
                    {grouped[zone].filter(c => selectedIds.has(c.id)).length}/{grouped[zone].length}
                  </span>
                </div>
                {grouped[zone].map(ch => (
                  <label key={ch.id} style={styles.chapterItem}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(ch.id)}
                      onChange={() => toggleChapter(ch.id)}
                      style={{ marginRight: 8, flexShrink: 0 }}
                    />
                    <span style={styles.chapterName}>{ch.display_name}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      <button type="submit" disabled={!canSubmit} style={{
        ...styles.button,
        opacity: canSubmit ? 1 : 0.5,
        cursor: canSubmit ? "pointer" : "not-allowed",
      }}>
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
  field: { marginBottom: 20 },
  label: { display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "#444" },
  dropzone: { border: "2px dashed #c5cae9", borderRadius: 8, padding: "24px 16px",
               textAlign: "center", cursor: "pointer", color: "#666", fontSize: 14,
               transition: "border-color 0.2s" },
  dropzoneActive: { borderColor: "#2563eb", background: "#eff6ff", color: "#1d4ed8" },
  fileName: { fontWeight: 600 },
  select: { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #ddd",
             fontSize: 14, outline: "none" },
  autoNote: { fontSize: 13, color: "#666", fontStyle: "italic", margin: "0 0 20px",
              padding: "10px 14px", background: "#f8fafc", borderRadius: 6,
              border: "1px solid #e2e8f0" },
  chapterHeader: { display: "flex", justifyContent: "space-between", alignItems: "center",
                   marginBottom: 8 },
  chapterCount: { fontWeight: 400, color: "#888", marginLeft: 8 },
  chapterActions: { display: "flex", gap: 8 },
  actionBtn: { fontSize: 12, padding: "3px 10px", border: "1px solid #d1d5db", borderRadius: 5,
               background: "#fff", cursor: "pointer", color: "#374151" },
  chapterList: { border: "1px solid #e5e7eb", borderRadius: 8, maxHeight: 280,
                  overflowY: "auto", fontSize: 13 },
  zoneLabel: { display: "flex", justifyContent: "space-between", padding: "6px 12px",
               background: "#f3f4f6", fontSize: 11, fontWeight: 700, color: "#6b7280",
               textTransform: "uppercase", letterSpacing: 0.5, position: "sticky", top: 0 },
  zoneCount: { fontWeight: 400 },
  chapterItem: { display: "flex", alignItems: "flex-start", padding: "7px 12px",
                  cursor: "pointer", borderBottom: "1px solid #f3f4f6" },
  chapterName: { lineHeight: 1.4 },
  button: { width: "100%", padding: "12px 24px", background: "#2563eb", color: "#fff",
            border: "none", borderRadius: 8, fontSize: 16, fontWeight: 600,
            marginTop: 8, transition: "opacity 0.2s" },
};
