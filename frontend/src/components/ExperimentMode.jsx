import { useEffect, useState } from "react";
import {
  clearExperimentSnapshots,
  listExperimentSnapshots,
  recordExperimentSnapshot,
} from "../api/client";

const EXPERIMENTS = [
  {
    id: 1,
    title: "Experiment 1 — Upload 1 Document",
    goal: "Observe the baseline: how many nodes/relationships does a single document produce?",
    suggestedLabel: "After 1 document",
  },
  {
    id: 2,
    title: "Experiment 2 — Upload 5 Documents",
    goal: "Watch the graph start connecting concepts across documents.",
    suggestedLabel: "After 5 documents",
  },
  {
    id: 3,
    title: "Experiment 3 — Upload 20 Documents",
    goal: "Look for rising graph density and more richly connected concepts.",
    suggestedLabel: "After 20 documents",
  },
  {
    id: 4,
    title: "Experiment 4 — Upload 100 Documents",
    goal: "Measure indexing time, graph size, latency, and retrieval quality at scale.",
    suggestedLabel: "After 100 documents",
  },
];

function formatDate(iso) {
  return new Date(iso).toLocaleString();
}

export default function ExperimentMode() {
  const [snapshots, setSnapshots] = useState([]);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    try {
      const res = await listExperimentSnapshots();
      setSnapshots(res.snapshots);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleRecord(e) {
    e.preventDefault();
    if (!label.trim() || isSaving) return;
    setIsSaving(true);
    setError(null);
    try {
      await recordExperimentSnapshot(label.trim(), notes.trim() || null);
      setLabel("");
      setNotes("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleClear() {
    if (!window.confirm("Clear all recorded experiment snapshots?")) return;
    try {
      await clearExperimentSnapshots();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        {EXPERIMENTS.map((exp) => (
          <div key={exp.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-semibold text-slate-800">{exp.title}</p>
            <p className="mt-1 text-xs text-slate-500">{exp.goal}</p>
            <button
              onClick={() => setLabel(exp.suggestedLabel)}
              className="mt-2 rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-500 hover:border-brand-400 hover:text-brand-700"
            >
              Use this label →
            </button>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Record a Snapshot
        </h3>
        <p className="mb-3 text-xs text-slate-500">
          After uploading documents in the sidebar for a given experiment
          stage, record a snapshot here to capture current document/chunk/
          entity/relationship counts for comparison over time.
        </p>
        <form onSubmit={handleRecord} className="flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label, e.g. 'After 5 documents'"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={isSaving || !label.trim()}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {isSaving ? "Saving…" : "Record Snapshot"}
          </button>
        </form>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Snapshot History ({snapshots.length})
          </h3>
          {snapshots.length > 0 && (
            <button
              onClick={handleClear}
              className="text-xs text-slate-400 hover:text-red-600"
            >
              Clear history
            </button>
          )}
        </div>
        {snapshots.length === 0 ? (
          <p className="text-sm text-slate-400 italic">
            No snapshots recorded yet.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-400">
                  <th className="py-1.5 pr-3">Label</th>
                  <th className="py-1.5 pr-3">Recorded</th>
                  <th className="py-1.5 pr-3">Docs</th>
                  <th className="py-1.5 pr-3">Chunks</th>
                  <th className="py-1.5 pr-3">Entities</th>
                  <th className="py-1.5 pr-3">Relationships</th>
                  <th className="py-1.5 pr-3">Density</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s) => (
                  <tr key={s.run_id} className="border-b border-slate-100 last:border-0">
                    <td className="py-1.5 pr-3 font-medium text-slate-700">{s.label}</td>
                    <td className="py-1.5 pr-3 text-slate-500">{formatDate(s.recorded_at)}</td>
                    <td className="py-1.5 pr-3">{s.total_documents}</td>
                    <td className="py-1.5 pr-3">{s.total_chunks}</td>
                    <td className="py-1.5 pr-3">{s.total_entities ?? "—"}</td>
                    <td className="py-1.5 pr-3">{s.total_relationships ?? "—"}</td>
                    <td className="py-1.5 pr-3">{s.graph_density ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
