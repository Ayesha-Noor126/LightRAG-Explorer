import { useState } from "react";

function LatencyPill({ label, ms }) {
  return (
    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
      {label}: <span className="font-medium text-slate-800">{ms.toFixed(0)}ms</span>
    </span>
  );
}

function DocumentSummaryCard({ doc }) {
  return (
    <div className="rounded-md border border-brand-100 bg-brand-50 p-3">
      <p className="mb-1 text-xs font-medium text-brand-700 truncate" title={doc.filename}>
        {doc.filename}
      </p>
      <p className="text-sm text-slate-700">{doc.summary}</p>
    </div>
  );
}

function ChunkCard({ chunk }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li className="rounded-md border border-slate-100 bg-slate-50 p-3 space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="truncate font-medium" title={chunk.filename}>
          {chunk.filename} · chunk #{chunk.chunk_index}
        </span>
        <span className="shrink-0 rounded-full bg-brand-100 px-2 py-0.5 text-brand-700">
          similarity {chunk.similarity_score.toFixed(3)}
        </span>
      </div>

      {/* Summary — shown when available */}
      {chunk.summary && (
        <div className="rounded border border-amber-100 bg-amber-50 px-2.5 py-2">
          <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-600">
            Summary
          </p>
          <p className="text-xs text-slate-700">{chunk.summary}</p>
        </div>
      )}

      {/* Full chunk text — collapsible */}
      <div>
        <p className={`text-sm text-slate-700 ${expanded ? "" : "line-clamp-3"}`}>
          {chunk.text}
        </p>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 text-xs text-brand-600 hover:underline"
        >
          {expanded ? "Show less" : "Show full chunk"}
        </button>
      </div>
    </li>
  );
}

export default function AnswerDisplay({ result }) {
  if (!result) return null;

  const docSummaries = result.document_summaries ?? [];

  return (
    <div className="space-y-4">
      {/* Answer card */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Answer
        </h3>
        <p className="whitespace-pre-wrap text-slate-800">{result.answer}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <LatencyPill label="Embedding" ms={result.latency.embedding_ms} />
          <LatencyPill label="Retrieval" ms={result.latency.retrieval_ms} />
          <LatencyPill label="LLM" ms={result.latency.llm_ms} />
          <LatencyPill label="Total" ms={result.latency.total_ms} />
        </div>
      </div>

      {/* Document-level summaries */}
      {docSummaries.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Document Overview{docSummaries.length > 1 ? "s" : ""} ({docSummaries.length})
          </h3>
          <div className="space-y-2">
            {docSummaries.map((doc) => (
              <DocumentSummaryCard key={doc.doc_id} doc={doc} />
            ))}
          </div>
        </div>
      )}

      {/* Retrieved chunks */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Retrieved Chunks ({result.retrieved_chunks.length})
        </h3>
        {result.retrieved_chunks.length === 0 ? (
          <p className="text-sm text-slate-400 italic">No chunks retrieved.</p>
        ) : (
          <ul className="space-y-3">
            {result.retrieved_chunks.map((chunk) => (
              <ChunkCard key={chunk.chunk_id} chunk={chunk} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
