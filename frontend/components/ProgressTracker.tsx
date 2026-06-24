"use client";

interface Props {
  message?: string;
}

export default function ProgressTracker({ message }: Props) {
  return (
    <div style={styles.container}>
      <div style={styles.spinner} />
      <h2 style={styles.heading}>Evaluating documentation…</h2>
      <p style={styles.sub}>
        {message || "Comparing your model documentation against ECB supervisory requirements."}
      </p>
      <p style={styles.note}>
        This may take a few minutes depending on the scope selected.
        Do not close this page.
      </p>
    </div>
  );
}

const keyframes = `
@keyframes spin {
  to { transform: rotate(360deg); }
}`;

const styles: Record<string, React.CSSProperties> = {
  container: { background: "#fff", borderRadius: 12, padding: 48, maxWidth: 500,
               margin: "0 auto", textAlign: "center",
               boxShadow: "0 2px 12px rgba(0,0,0,0.08)" },
  spinner: { width: 56, height: 56, border: "5px solid #e0e7ff", borderTopColor: "#2563eb",
             borderRadius: "50%", animation: "spin 0.9s linear infinite",
             margin: "0 auto 24px" },
  heading: { fontSize: 20, fontWeight: 700, marginBottom: 12 },
  sub: { color: "#555", fontSize: 14, lineHeight: 1.6, marginBottom: 16 },
  note: { color: "#888", fontSize: 13 },
};

// Inject keyframes once
if (typeof document !== "undefined") {
  const style = document.createElement("style");
  style.textContent = keyframes;
  document.head.appendChild(style);
}
