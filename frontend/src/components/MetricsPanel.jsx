/**
 * Displays aggregate metric cards from the latest batch of readings.
 */
export default function MetricsPanel({ readings }) {
  if (!readings.length) {
    return (
      <p className="text-gray-500 text-center py-12">
        Waiting for meter data…
      </p>
    );
  }

  const avg = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const normal = readings.filter((r) => r.prediction === "normal").length;
  const anomalies = readings.length - normal;

  const cards = [
    {
      label: "Avg Voltage",
      value: avg(readings.map((r) => r.voltage)).toFixed(1) + " V",
      color: "text-blue-400",
    },
    {
      label: "Avg Current",
      value: avg(readings.map((r) => r.current)).toFixed(1) + " A",
      color: "text-cyan-400",
    },
    {
      label: "Avg Frequency",
      value: avg(readings.map((r) => r.frequency)).toFixed(3) + " Hz",
      color: "text-purple-400",
    },
    {
      label: "Normal",
      value: normal,
      color: "text-green-400",
    },
    {
      label: "Anomalies",
      value: anomalies,
      color: anomalies > 0 ? "text-red-400" : "text-green-400",
    },
  ];

  return (
    <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      {cards.map((c) => (
        <div
          key={c.label}
          className="bg-gray-900 border border-gray-800 rounded-xl p-5"
        >
          <p className="text-xs uppercase tracking-wider text-gray-500">
            {c.label}
          </p>
          <p className={`text-2xl font-semibold mt-1 ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </section>
  );
}
