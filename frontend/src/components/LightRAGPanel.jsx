import { useState } from "react";
import { queryLightRag } from "../api/client";

const MODES = [
  { id: "hybrid", label: "Hybrid", hint: "local + global combined (recommended)" },
  { id: "local", label: "Local", hint: "entity-focused, single-hop context" },
  { id: "global", label: "Global", hint: "theme/relationship-focused, broader context" },
  { id: "naive", label: "Naive", hint: "plain vector search, no graph traversal" },
];

function LatencyPill({ label, ms }) {
  return (
    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
      {label}: <span className="font-medium text-slate-800">{ms.toFixed(0)}ms</span>
    </span>
  );
}

function SubQuestionsPanel({ subQuestions, originalQuestion }) {
  // Only show when there is more than the original question itself
  const isDecomposed =
    subQuestions &&
    subQuestions.length > 1 &&
    !(subQuestions.length === 1 && subQuestions[0] === originalQuestion);

  if (!isDecomposed) return null;

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 shadow-sm">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-indigo-500">
        Query Decomposition ({subQuestions.length} Sub-Questions)
      </h3>
      <ol className="space-y-1.5 list-none">
        {subQuestions.map((q, i) => (
          <li key={i} className="flex gap-2 text-sm text-indigo-800">
            <span className="flex-shrink-0 rounded-full bg-indigo-200 w-5 h-5 flex items-center justify-center text-[10px] font-bold text-indigo-700">
              {i + 1}
            </span>
            <span>{q}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function LightRAGPanel({ hasDocuments }) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [decompose, setDecompose] = useState(false);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);
    try {
      const res = await queryLightRag(question.trim(), mode, decompose);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={
              hasDocuments
                ? "Ask a question — LightRAG will traverse the knowledge graph…"
                : "Upload a document first, then ask a question…"
            }
            className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? "Traversing…" : "Ask"}
          </button>
        </div>

        {/* Mode selector */}
        <div className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMode(m.id)}
              title={m.hint}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                mode === m.id
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-slate-200 text-slate-500 hover:border-slate-300"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Decompose toggle */}
        <label className="flex items-center gap-2 cursor-pointer select-none w-fit">
          <div
            onClick={() => setDecompose((d) => !d)}
            className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors duration-200 ${
              decompose ? "bg-indigo-500" : "bg-slate-300"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200 ${
                decompose ? "translate-x-4" : "translate-x-1"
              }`}
            />
          </div>
          <span className="text-xs text-slate-600">
            <span className="font-medium text-slate-800">Decompose Query</span>
            {" "}— break into sub-questions &amp; merge answers
          </span>
        </label>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </div>
      )}

      {!result && !error && !isLoading && (
        <p className="text-sm text-slate-400 italic">
          The generated answer, entities/relationships used, and a preview of
          LightRAG's assembled context will appear here after you ask a
          question.
        </p>
      )}

      {result && (
        <div className="space-y-4">
          {/* Sub-questions panel — only shown when decomposition produced multiple questions */}
          <SubQuestionsPanel
            subQuestions={result.sub_questions}
            originalQuestion={result.question}
          />

          {/* Answer */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                Answer
              </h3>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
                mode: {result.mode}
              </span>
            </div>
            <p className="whitespace-pre-wrap text-slate-800">{result.answer}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <LatencyPill label="Context" ms={result.latency.context_retrieval_ms} />
              <LatencyPill label="Generation" ms={result.latency.generation_ms} />
              <LatencyPill label="Total" ms={result.latency.total_ms} />
            </div>
          </div>

          {/* Entities & Relationships */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Entities Used ({result.entities.length})
              </h3>
              {result.entities.length === 0 ? (
                <p className="text-sm text-slate-400 italic">
                  No structured entities parsed from this response.
                </p>
              ) : (
                <ul className="space-y-2">
                  {result.entities.map((entity, i) => (
                    <li key={i} className="rounded-md bg-slate-50 p-2 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-800">{entity.name}</span>
                        {entity.entity_type && (
                          <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] text-brand-700">
                            {entity.entity_type}
                          </span>
                        )}
                      </div>
                      {entity.description && (
                        <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                          {entity.description}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Relationships Traversed ({result.relationships.length})
              </h3>
              {result.relationships.length === 0 ? (
                <p className="text-sm text-slate-400 italic">
                  No structured relationships parsed from this response.
                </p>
              ) : (
                <ul className="space-y-2">
                  {result.relationships.map((rel, i) => (
                    <li key={i} className="rounded-md bg-slate-50 p-2 text-sm">
                      <div className="flex items-center gap-1.5 text-slate-800">
                        <span className="font-medium">{rel.source}</span>
                        <span className="text-slate-400">→</span>
                        <span className="font-medium">{rel.target}</span>
                        {rel.weight != null && (
                          <span className="ml-auto rounded-full bg-slate-200 px-2 py-0.5 text-[10px] text-slate-600">
                            w={rel.weight.toFixed(2)}
                          </span>
                        )}
                      </div>
                      {rel.description && (
                        <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                          {rel.description}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Raw context preview */}
          <details className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wide text-slate-400">
              Raw Context Preview
            </summary>
            <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs text-slate-600">
              {result.context_preview}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
