function Stat({ label, value }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      <span className="text-lg font-semibold text-slate-800">{value}</span>
    </div>
  );
}

export default function MetricsBar({ metrics }) {
  if (!metrics) return null;

  return (
    <div className="flex flex-wrap gap-6 rounded-lg border border-slate-200 bg-white px-5 py-3 shadow-sm">
      <Stat label="Documents" value={metrics.total_documents} />
      <Stat label="Chunks" value={metrics.total_chunks} />
      <Stat label="Chunk Size" value={metrics.chunk_size} />
      <Stat label="Overlap" value={metrics.chunk_overlap} />
      <Stat label="Embedding Model" value={metrics.embedding_model} />
      <Stat
        label="Graph Entities"
        value={metrics.total_entities ?? "—"}
      />
      <Stat
        label="Graph Relationships"
        value={metrics.total_relationships ?? "—"}
      />
    </div>
  );
}
