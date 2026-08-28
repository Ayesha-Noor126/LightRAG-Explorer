const STATUS_STYLES = {
  indexed: "bg-emerald-100 text-emerald-700",
  processing: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  not_started: "bg-slate-100 text-slate-500",
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentList({ documents, onDelete, deletingId }) {
  if (documents.length === 0) {
    return (
      <p className="text-sm text-slate-400 italic py-4 text-center">
        No documents uploaded yet.
      </p>
    );
  }

  return (
    <ul className="space-y-2 max-h-72 overflow-y-auto pr-1">
      {documents.map((doc) => (
        <li
          key={doc.doc_id}
          className="rounded-md border border-slate-200 bg-white p-2.5 text-sm"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate font-medium text-slate-800" title={doc.filename}>
                {doc.filename}
              </p>
              <p className="text-xs text-slate-400">
                {formatSize(doc.size_bytes)} · {doc.num_chunks} chunks
              </p>
            </div>
            <button
              onClick={() => onDelete(doc.doc_id)}
              disabled={deletingId === doc.doc_id}
              className="shrink-0 text-xs text-slate-400 hover:text-red-600 disabled:opacity-40"
              title="Delete document"
            >
              {deletingId === doc.doc_id ? "…" : "✕"}
            </button>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                STATUS_STYLES[doc.status] || "bg-slate-100 text-slate-600"
              }`}
              title="Simple RAG (Chroma) status"
            >
              RAG: {doc.status}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                STATUS_STYLES[doc.graphrag_status] || "bg-slate-100 text-slate-600"
              }`}
              title="LightRAG (graph) status"
            >
              Graph: {doc.graphrag_status}
            </span>
          </div>
          {(doc.error_message || doc.graphrag_error_message) && (
            <p
              className="mt-1 truncate text-[11px] text-red-500"
              title={doc.error_message || doc.graphrag_error_message}
            >
              {doc.error_message || doc.graphrag_error_message}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
