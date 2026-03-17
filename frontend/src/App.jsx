/**
 * App.jsx — Root component for the HCS Smart Grid Cyber Monitor
 * ==============================================================
 * Connects to the FastAPI WebSocket at /ws/metrics on mount and
 * receives every scored reading in real time — no polling needed.
 *
 * State:
 *   readings[] — rolling window of the last 60 data points (for charts)
 *   alerts[]   — every anomaly received this session (newest first)
 *   latest     — the single most-recent reading (drives the threat banner)
 *   status     — "connecting" | "live" | "error"
 */

import { useState, useEffect, useRef, useCallback } from "react";
import MetricsPanel from "./components/MetricsPanel";
import AlertFeed from "./components/AlertFeed";
import VoltageChart from "./components/VoltageChart";
import ThreatBanner from "./components/ThreatBanner";

// ── WebSocket URL — Vite proxies /api but WS needs a direct URL ──
const WS_URL = `ws://${window.location.hostname}:8000/ws/metrics`;

// Max data points kept in the chart rolling window
const MAX_CHART_POINTS = 60;

export default function App() {
  // --- State ---
  const [readings, setReadings] = useState([]);   // chart data (rolling window)
  const [alerts, setAlerts] = useState([]);        // anomaly log
  const [latest, setLatest] = useState(null);      // most recent reading
  const [status, setStatus] = useState("connecting");

  // Ref to persist the WebSocket across renders
  const wsRef = useRef(null);

  // ------------------------------------------------------------------
  // WebSocket lifecycle — connect on mount, auto-reconnect on drop
  // ------------------------------------------------------------------
  const connect = useCallback(() => {
    // Don't open a second socket if one is already active
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[ws] Connected to", WS_URL);
      setStatus("live");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Store the latest reading for the threat banner
      setLatest(data);

      // Append to the chart rolling window (keep last MAX_CHART_POINTS)
      setReadings((prev) => [...prev, data].slice(-MAX_CHART_POINTS));

      // If it's an anomaly, prepend it to the alert log
      if (data.prediction === "anomaly") {
        setAlerts((prev) => [data, ...prev].slice(0, 200));
      }
    };

    ws.onerror = () => setStatus("error");

    ws.onclose = () => {
      console.log("[ws] Disconnected — reconnecting in 3s …");
      setStatus("connecting");
      // Auto-reconnect after 3 seconds
      setTimeout(connect, 3000);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* ── Header ── */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Smart Grid Cyber Monitor
          </h1>
          <p className="text-gray-400 mt-1">
            Real-time anomaly detection for IoT energy systems
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-sm font-medium ${
            status === "live"
              ? "bg-green-900/60 text-green-300"
              : status === "error"
              ? "bg-red-900/60 text-red-300"
              : "bg-yellow-900/60 text-yellow-300"
          }`}
        >
          {status === "live" ? "LIVE" : status === "error" ? "ERROR" : "CONNECTING"}
        </span>
      </header>

      {/* ── Flashing Threat Banner (only when latest is an anomaly) ── */}
      <ThreatBanner latest={latest} />

      {/* ── Metric Cards ── */}
      <MetricsPanel readings={readings} />

      {/* ── Live Charts ── */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <VoltageChart data={readings} dataKey="voltage" label="Voltage (V)" color="#3b82f6" />
        <VoltageChart data={readings} dataKey="current" label="Current (A)" color="#06b6d4" />
      </section>

      {/* ── Alert Feed ── */}
      <AlertFeed alerts={alerts} />
    </div>
  );
}
