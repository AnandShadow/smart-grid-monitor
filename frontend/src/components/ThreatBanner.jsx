/**
 * ThreatBanner.jsx — Flashing "CYBER THREAT DETECTED" alert
 * ==========================================================
 * Conditionally renders a full-width, animated red banner when
 * the most recent reading is flagged as an anomaly by the
 * Isolation Forest model.
 *
 * Props:
 *   latest — the single most-recent reading from the WebSocket
 *            (or null before the first message arrives)
 */

export default function ThreatBanner({ latest }) {
  // Don't render anything if we haven't received data yet or it's normal
  if (!latest || latest.prediction !== "anomaly") return null;

  return (
    <div className="animate-pulse rounded-xl border-2 border-red-600 bg-red-950/70 px-6 py-4 shadow-lg shadow-red-900/40">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        {/* ── Left: alert title + threat type ── */}
        <div className="flex items-center gap-3">
          {/* Pulsing red dot */}
          <span className="relative flex h-4 w-4">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75" />
            <span className="relative inline-flex h-4 w-4 rounded-full bg-red-600" />
          </span>

          <div>
            <p className="text-lg font-bold text-red-300 tracking-wide">
              CYBER THREAT DETECTED
            </p>
            <p className="text-sm text-red-400">
              {latest.threat_type ?? "Unknown anomaly"} &mdash; Meter{" "}
              <span className="font-mono">{latest.meter_id}</span>
            </p>
          </div>
        </div>

        {/* ── Right: score + timestamp ── */}
        <div className="flex gap-6 text-sm">
          <div>
            <p className="text-red-500 text-xs uppercase tracking-wider">
              Threat Score
            </p>
            <p className="text-red-200 font-mono font-semibold text-lg">
              {latest.anomaly_score?.toFixed(4)}
            </p>
          </div>
          <div>
            <p className="text-red-500 text-xs uppercase tracking-wider">
              Timestamp
            </p>
            <p className="text-red-200 font-mono text-lg">
              {latest.timestamp
                ? new Date(latest.timestamp).toLocaleTimeString()
                : "—"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
