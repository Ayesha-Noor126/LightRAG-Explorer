import { useState } from "react";
import DocumentUpload from "./DocumentUpload";
import DocumentList from "./DocumentList";
import { clearDocuments, deleteDocument, rebuildIndex } from "../api/client";

export default function Sidebar({ documents, onRefresh }) {
  const [deletingId, setDeletingId] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [notice, setNotice] = useState(null);

  async function handleDelete(docId) {
    setDeletingId(docId);
    try {
      await deleteDocument(docId);
      await onRefresh();
    } catch (err) {
      setNotice({ type: "error", text: err.message });
    } finally {
      setDeletingId(null);
    }
  }

  async function handleClearAll() {
    if (!window.confirm("Remove all uploaded documents and clear the index?")) return;
    setIsBusy(true);
    try {
      await clearDocuments();
      await onRefresh();
      setNotice({ type: "success", text: "All documents cleared." });
    } catch (err) {
      setNotice({ type: "error", text: err.message });
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRebuild() {
    setIsBusy(true);
    try {
      const res = await rebuildIndex();
      await onRefresh();
      setNotice({
        type: "success",
        text: `Rebuilt ${res.total_documents} docs / ${res.total_chunks} chunks in ${res.rebuild_time_ms.toFixed(0)}ms.`,
      });
    } catch (err) {
      setNotice({ type: "error", text: err.message });
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col gap-4 border-r border-slate-200 bg-slate-50 p-4">
      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Upload Documents</h2>
        <DocumentUpload onUploaded={onRefresh} />
      </div>

      <div className="flex-1 overflow-hidden">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">
            Documents ({documents.length})
          </h2>
        </div>
        <DocumentList
          documents={documents}
          onDelete={handleDelete}
          deletingId={deletingId}
        />
      </div>

      <div className="flex gap-2 border-t border-slate-200 pt-3">
        <button
          onClick={handleRebuild}
          disabled={isBusy || documents.length === 0}
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40"
        >
          Rebuild Index
        </button>
        <button
          onClick={handleClearAll}
          disabled={isBusy || documents.length === 0}
          className="flex-1 rounded-md border border-red-200 bg-white px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-40"
        >
          Clear All
        </button>
      </div>

      {notice && (
        <p
          className={`text-xs ${
            notice.type === "error" ? "text-red-600" : "text-emerald-600"
          }`}
        >
          {notice.text}
        </p>
      )}
    </aside>
  );
}
