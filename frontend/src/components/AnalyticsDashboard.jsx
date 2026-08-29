import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getMetrics, listExperimentSnapshots } from "../api/client";

function MetricCard({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

export default function AnalyticsDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      const [m, history] = await Promise.all([getMetrics(), listExperimentSnapshots()]);
      setMetrics(m);
      setSnapshots(history.snapshots);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!metrics) {
    return <p className="text-sm text-slate-400 italic">Loading analytics…</p>;
  }

  const overviewData = [
    { name: "Chunks", value: metrics.total_chunks },
    { name: "Entities", value: metrics.total_entities ?? 0 },
    { name: "Relationships", value: metrics.total_relationships ?? 0 },
  ];

  const growthData = snapshots.map((s) => ({
    name: s.label,
    Entities: s.total_entities ?? 0,
    Relationships: s.total_relationships ?? 0,
    Chunks: s.total_chunks,
  }));

  return (
    <div className="space-y-5">
      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Document Metrics
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard label="Documents" value={metrics.total_documents} />
          <MetricCard label="Chunks" value={metrics.total_chunks} />
          <MetricCard label="Chunk Size" value={metrics.chunk_size} sub="characters" />
          <MetricCard label="Overlap" value={metrics.chunk_overlap} sub="characters" />
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Knowledge Graph Metrics
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard label="Entities" value={metrics.total_entities ?? "—"} />
          <MetricCard label="Relationships" value={metrics.total_relationships ?? "—"} />
          <MetricCard label="Graph Density" value={metrics.graph_density ?? "—"} />
          <MetricCard
            label="Docs in Graph"
            value={metrics.documents_indexed_in_graph}
            sub={`of ${metrics.total_documents}`}
          />
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Corpus Overview
        </h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={overviewData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="value" fill="#3b6ef6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Graph Growth Over Recorded Experiments
        </h3>
        {growthData.length === 0 ? (
          <p className="text-sm text-slate-400 italic">
            No experiment snapshots recorded yet. Use the Experiment Mode tab
            to record dataset-size checkpoints and see growth trends here.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={growthData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="Entities" stroke="#3b6ef6" strokeWidth={2} />
              <Line
                type="monotone"
                dataKey="Relationships"
                stroke="#10b981"
                strokeWidth={2}
              />
              <Line type="monotone" dataKey="Chunks" stroke="#f59e0b" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <p className="text-xs text-slate-400">
        Last indexed:{" "}
        {metrics.last_indexed_at
          ? new Date(metrics.last_indexed_at).toLocaleString()
          : "never"}
      </p>
    </div>
  );
}
