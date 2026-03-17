/**
 * VoltageChart.jsx — Real-time line chart for smart-grid telemetry
 * ================================================================
 * Uses recharts to plot a rolling window of data points streamed
 * over the WebSocket.  Anomalous points are highlighted in red.
 *
 * Props:
 *   data     — array of reading objects from the WebSocket
 *   dataKey  — which numeric field to plot ("voltage", "current", etc.)
 *   label    — human-readable axis label ("Voltage (V)")
 *   color    — hex colour for the line stroke
 */

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";

// Custom dot renderer — red dot for anomalies, default for normal
function AnomalyDot(props) {
  const { cx, cy, payload } = props;
  if (payload.prediction === "anomaly") {
    return (
      <circle
        cx={cx}
        cy={cy}
        r={5}
        fill="#ef4444"
        stroke="#7f1d1d"
        strokeWidth={2}
      />
    );
  }
  // Normal readings get no visible dot (keeps the chart clean)
  return null;
}

export default function VoltageChart({ data, dataKey, label, color }) {
  // Format timestamps to HH:MM:SS for the X axis
  const chartData = data.map((d, i) => ({
    ...d,
    time: d.timestamp
      ? new Date(d.timestamp).toLocaleTimeString()
      : String(i),
  }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h3 className="text-sm uppercase tracking-wider text-gray-500 mb-4">
        {label}
      </h3>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="time"
            tick={{ fill: "#6b7280", fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "#6b7280", fontSize: 11 }}
            domain={["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#111827",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#e5e7eb",
              fontSize: 12,
            }}
            formatter={(value) => [Number(value).toFixed(2), label]}
            labelFormatter={(t) => `Time: ${t}`}
          />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            dot={<AnomalyDot />}
            activeDot={{ r: 6, fill: color }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
