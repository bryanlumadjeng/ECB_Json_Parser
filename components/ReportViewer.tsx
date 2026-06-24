"use client";

import { useState } from "react";

interface Finding {
  finding_id: string;
  ecb_chapter: string;
  ecb_zone: string;
  ecb_paragraph_ids: number[];
  verdict: "missing" | "partial";
  confidence: "high" | "medium" | "low";
  ecb_requirement_summary: string;
  gap_description: string | null;
  matched_excerpts: string[];
  recommendation: string | null;
}

interface Summary {
  overall_verdict: string;
  compliant: number;
  partial: number;
  missing: number;
  not_applicable: number;
  compliance_score: number;
}

export interface Report {
  report_id: string;
  generated_at: string;
  bank_document: { path: string; size_bytes: number; chunks: number };
  scope: { tags: string[]; chapters_evaluated: number; chapters_skipped: number };
  summary: Summary;
  findings: Finding[];
  token_usage: { input_tokens: number; output_tokens: number; estimated_cost_usd: number };
}

interface Props {
  report: Report;
  onReset: () => void;
}

const VERDICT_COLOR: Record<string, string> = {
  compliant: "#16a34a",
  partial: "#d97706",
  missing: "#dc2626",
  not_applicable: "#6b7280",
  non_compliant: "#dc2626",
};

const VERDICT_BG: Record<string, string> = {
  compliant: "#dcfce7",
  partial: "#fef3c7",
  missing: "#fee2e2",
  not_applicable: "#f3f4f6",
  non_compliant: "#fee2e2",
};

function ScoreDial({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "#16a34a" : pct >= 50 ? "#d97706" : "#dc2626";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 48, fontWeight: 800, color }}>{pct}%</div>
      <div style={{ fontSize: 13, color: "#666" }}>Compliance Score</div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  return (
    <span style={{
      padding: "2px 10px", borderRadius: 12, fontSize: 12, fontWeight: 700,
      color: VERDICT_COLOR[verdict] ?? "#333",
      background: VERDICT_BG[verdict] ?? "#f5f5f5",
      textTransform: "uppercase",
    }}>
      {verdict.replace("_", " ")}
    </span>
  );
}

export default function ReportViewer({ report, onReset }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const s = report.summary;

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.report_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const missing = report.findings.filter(f => f.verdict === "missing");
  const partial = report.findings.filter(f => f.verdict === "partial");

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Compliance Report</h2>
          <p style={styles.meta}>
            {report.bank_document.path} &bull; {report.scope.chapters_evaluated} chapters &bull;{" "}
            {new Date(report.generated_at).toLocaleString()}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={downloadJson} style={styles.btnSecondary}>Download JSON</button>
          <button onClick={onReset} style={styles.btnPrimary}>New Evaluation</button>
        </div>
      </div>

      {/* Summary cards */}
      <div style={styles.summaryGrid}>
        <div style={styles.card}>
          <ScoreDial score={s.compliance_score} />
        </div>
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>Overall Verdict</h3>
          <div style={{ marginTop: 8 }}>
            <VerdictBadge verdict={s.overall_verdict} />
          </div>
          <div style={styles.statRow}>
            <span style={{ color: VERDICT_COLOR.compliant }}>Compliant</span>
            <strong>{s.compliant}</strong>
          </div>
          <div style={styles.statRow}>
            <span style={{ color: VERDICT_COLOR.partial }}>Partial</span>
            <strong>{s.partial}</strong>
          </div>
          <div style={styles.statRow}>
            <span style={{ color: VERDICT_COLOR.missing }}>Missing</span>
            <strong>{s.missing}</strong>
          </div>
          <div style={styles.statRow}>
            <span style={{ color: VERDICT_COLOR.not_applicable }}>N/A</span>
            <strong>{s.not_applicable}</strong>
          </div>
        </div>
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>Scope</h3>
          <p style={styles.metaSmall}>{report.scope.tags.join(", ")}</p>
          <div style={styles.statRow}>
            <span>Chapters evaluated</span>
            <strong>{report.scope.chapters_evaluated}</strong>
          </div>
          <div style={styles.statRow}>
            <span>Chunks indexed</span>
            <strong>{report.bank_document.chunks}</strong>
          </div>
          <div style={{ ...styles.statRow, marginTop: 8, borderTop: "1px solid #eee", paddingTop: 8 }}>
            <span>Est. cost</span>
            <strong>${report.token_usage.estimated_cost_usd.toFixed(3)}</strong>
          </div>
        </div>
      </div>

      {/* Findings */}
      {report.findings.length === 0 ? (
        <div style={styles.noFindings}>All evaluated chapters are compliant!</div>
      ) : (
        <>
          {missing.length > 0 && (
            <section>
              <h3 style={styles.sectionTitle}>Missing Requirements ({missing.length})</h3>
              {missing.map(f => <FindingCard key={f.finding_id} f={f} expanded={expandedId === f.finding_id} onToggle={() => setExpandedId(expandedId === f.finding_id ? null : f.finding_id)} />)}
            </section>
          )}
          {partial.length > 0 && (
            <section style={{ marginTop: 24 }}>
              <h3 style={styles.sectionTitle}>Partial Compliance ({partial.length})</h3>
              {partial.map(f => <FindingCard key={f.finding_id} f={f} expanded={expandedId === f.finding_id} onToggle={() => setExpandedId(expandedId === f.finding_id ? null : f.finding_id)} />)}
            </section>
          )}
        </>
      )}
    </div>
  );
}

function FindingCard({ f, expanded, onToggle }: { f: Finding; expanded: boolean; onToggle: () => void }) {
  return (
    <div style={styles.finding} onClick={onToggle}>
      <div style={styles.findingHeader}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
          <span style={styles.findingId}>{f.finding_id}</span>
          <VerdictBadge verdict={f.verdict} />
          <span style={styles.findingChapter}>{f.ecb_chapter}</span>
        </div>
        <span style={{ color: "#999", fontSize: 18 }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (
        <div style={styles.findingBody} onClick={e => e.stopPropagation()}>
          <p><strong>ECB Requirement:</strong> {f.ecb_requirement_summary}</p>
          <p style={{ marginTop: 8 }}>
            <strong>Paragraphs:</strong> {f.ecb_paragraph_ids.join(", ")}
          </p>
          {f.gap_description && (
            <p style={{ marginTop: 8, color: "#b91c1c" }}>
              <strong>Gap:</strong> {f.gap_description}
            </p>
          )}
          {f.matched_excerpts.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <strong>Evidence found:</strong>
              {f.matched_excerpts.slice(0, 2).map((ex, i) => (
                <blockquote key={i} style={styles.quote}>{ex.slice(0, 400)}</blockquote>
              ))}
            </div>
          )}
          {f.recommendation && (
            <p style={{ marginTop: 10, padding: "8px 12px", background: "#eff6ff",
                        borderLeft: "3px solid #2563eb", borderRadius: 4 }}>
              <strong>Recommendation:</strong> {f.recommendation}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 960, margin: "0 auto", padding: "0 16px 48px" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start",
            marginBottom: 24, flexWrap: "wrap", gap: 12 },
  title: { fontSize: 24, fontWeight: 800, marginBottom: 4 },
  meta: { fontSize: 13, color: "#666" },
  metaSmall: { fontSize: 12, color: "#888", marginTop: 4, marginBottom: 8 },
  summaryGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                 gap: 16, marginBottom: 32 },
  card: { background: "#fff", borderRadius: 10, padding: 20, boxShadow: "0 1px 6px rgba(0,0,0,0.07)" },
  cardTitle: { fontSize: 13, fontWeight: 600, color: "#555", textTransform: "uppercase",
               letterSpacing: 0.5, marginBottom: 8 },
  statRow: { display: "flex", justifyContent: "space-between", fontSize: 14, padding: "4px 0" },
  sectionTitle: { fontSize: 16, fontWeight: 700, marginBottom: 12, color: "#1a1a2e" },
  finding: { background: "#fff", borderRadius: 8, marginBottom: 10, cursor: "pointer",
             boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflow: "hidden" },
  findingHeader: { display: "flex", alignItems: "center", justifyContent: "space-between",
                   padding: "14px 16px" },
  findingId: { fontSize: 12, fontWeight: 700, color: "#6b7280", fontFamily: "monospace" },
  findingChapter: { fontSize: 14, fontWeight: 500, color: "#1a1a2e" },
  findingBody: { padding: "0 16px 16px", fontSize: 14, lineHeight: 1.6,
                 borderTop: "1px solid #f0f0f0" },
  quote: { margin: "8px 0", padding: "8px 12px", background: "#f9fafb",
           borderLeft: "3px solid #d1d5db", borderRadius: 4, fontSize: 13,
           fontStyle: "italic", color: "#555" },
  noFindings: { textAlign: "center", padding: 48, background: "#f0fdf4",
                borderRadius: 10, color: "#16a34a", fontSize: 16, fontWeight: 600 },
  btnPrimary: { padding: "8px 18px", background: "#2563eb", color: "#fff",
                border: "none", borderRadius: 6, cursor: "pointer", fontSize: 14, fontWeight: 600 },
  btnSecondary: { padding: "8px 18px", background: "#fff", color: "#374151",
                  border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer",
                  fontSize: 14, fontWeight: 600 },
};
