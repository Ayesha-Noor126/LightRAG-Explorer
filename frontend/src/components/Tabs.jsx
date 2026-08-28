const TABS = [
  { id: "simple-rag", label: "Simple RAG" },
  { id: "lightrag", label: "LightRAG" },
  { id: "comparison", label: "Comparison" },
  { id: "graph", label: "Neo4j Graph" },
  { id: "analytics", label: "Analytics" },
  { id: "experiments", label: "Experiments" },
];

export default function Tabs({ active, onChange }) {
  return (
    <div className="flex gap-1 border-b border-slate-200">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            active === tab.id
              ? "border-brand-600 text-brand-700"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
