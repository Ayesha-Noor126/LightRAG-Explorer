import { useState } from "react";
import { compareRag } from "../api/client";
import QueryCategories from "./QueryCategories";

function LatencyRow({ label, simpleMs, lightragMs }) {
  const max = Math.max(simpleMs || 0, lightragMs || 0, 1);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-brand-500"
            style={{ width: `${((simpleMs || 0) / max) * 100}%` }}
          />
        </div>
        <span className="w-16 shrink-0 text-right text-xs text-slate-600">
          {simpleMs != null ? `${simpleMs.toFixed(0)}ms` : "—"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-emerald-500"
            style={{ width: `${((lightragMs || 0) / max) * 100}%` }}
          />
        </div>
        <span className="w-16 shrink-0 text-right text-xs text-slate-600">
          {lightragMs != null ? `${lightragMs.toFixed(0)}ms` : "—"}
        </span>
      </div>
    </div>
  );
}

function ResultColumn({ title, colorClass, error, children }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3
        className={`mb-2 text-sm font-semibold uppercase tracking-wide ${colorClass}`}
      >
        {title}
      </h3>
      {error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
      ) : (
        children
      )}
    </div>
  );
}

export default function ComparisonView({ hasDocuments }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  async function runComparison(q) {
    if (!q.trim() || isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await compareRag(q.trim());
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    runComparison(question);
  }

  function handleTryQuestion(q) {
    setQuestion(q);
    runComparison(q);
  }

  return (
    <div className="space-y-5">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={
            hasDocuments
              ? "Ask a question — it'll run against both systems at once…"
              : "Upload a document first, then ask a question…"
          }
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? "Comparing…" : "Compare"}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <ResultColumn
              title="Simple RAG"
              colorClass="text-brand-700"
              error={result.simple_rag_error}
            >
              <p className="whitespace-pre-wrap text-sm text-slate-800">
                {result.simple_rag?.answer}
              </p>
              <p className="mt-3 text-xs font-medium text-slate-400">
                {result.simple_rag?.retrieved_chunks.length} chunks retrieved
              </p>
              <ul className="mt-1 space-y-1.5">
                {result.simple_rag?.retrieved_chunks.slice(0, 3).map((c) => (
                  <li
                    key={c.chunk_id}
                    className="rounded bg-slate-50 p-2 text-xs text-slate-600 line-clamp-2"
                  >
                    {c.filename} · sim {c.similarity_score.toFixed(2)} — {c.text}
                  </li>
                ))}
              </ul>
            </ResultColumn>

            <ResultColumn
              title="LightRAG"
              colorClass="text-emerald-700"
              error={result.lightrag_error}
            >
              <p className="whitespace-pre-wrap text-sm text-slate-800">
                {result.lightrag?.answer}
              </p>
              <p className="mt-3 text-xs font-medium text-slate-400">
                {result.lightrag?.entities.length} entities ·{" "}
                {result.lightrag?.relationships.length} relationships used
              </p>
              <ul className="mt-1 space-y-1.5">
                {result.lightrag?.entities.slice(0, 5).map((e, i) => (
                  <li
                    key={i}
                    className="inline-block rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700 mr-1 mb-1"
                  >
                    {e.name}
                  </li>
                ))}
              </ul>
            </ResultColumn>
          </div>

          {!result.simple_rag_error && !result.lightrag_error && (
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Latency Comparison
              </h3>
              <div className="mb-2 flex gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-brand-500" /> Simple RAG
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" /> LightRAG
                </span>
              </div>
              <LatencyRow
                label="Total"
                simpleMs={result.simple_rag?.latency.total_ms}
                lightragMs={result.lightrag?.latency.total_ms}
              />
            </div>
          )}
        </>
      )}

      {!result && !error && !isLoading && (
        <p className="text-sm text-slate-400 italic">
          Results from both systems will appear side by side after you ask a
          question — or try one of the sample questions below.
        </p>
      )}

      <QueryCategories onTry={handleTryQuestion} />
    </div>
  );
}
