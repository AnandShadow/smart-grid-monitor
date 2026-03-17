/**
 * Scrollable feed of detected cyber-security anomalies.
 */
export default function AlertFeed({ alerts }) {
  return (
    <section>
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse" />
        Cyber Security Alert Feed
      </h2>

      {alerts.length === 0 ? (
        <p className="text-gray-500 text-sm">No anomalies detected yet.</p>
      ) : (
        <div className="overflow-y-auto max-h-96 space-y-2 pr-1">
          {alerts.map((a, i) => (
            <div
              key={`${a.meter_id}-${a.timestamp}-${i}`}
              className="bg-red-950/40 border border-red-900/60 rounded-lg px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1"
            >
              <div>
                <span className="font-mono text-red-300 text-sm">
                  [{a.meter_id}]
                </span>{" "}
                <span className="text-red-200 font-medium">
                  {a.threat_type ?? "anomaly"}
                </span>
              </div>

              <div className="flex gap-4 text-xs text-gray-400">
                <span>V: {a.voltage?.toFixed(1)}</span>
                <span>A: {a.current?.toFixed(1)}</span>
                <span>Hz: {a.frequency?.toFixed(2)}</span>
                <span>RPS: {a.request_rate?.toFixed(1)}</span>
                <span>Score: {a.anomaly_score?.toFixed(3)}</span>
              </div>

              <time className="text-xs text-gray-600 shrink-0">
                {new Date(a.timestamp).toLocaleTimeString()}
              </time>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
