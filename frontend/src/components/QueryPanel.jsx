import { useState } from "react";
import { querySimpleRag } from "../api/client";
import AnswerDisplay from "./AnswerDisplay";

export default function QueryPanel({ hasDocuments }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);
    try {
      const res = await querySimpleRag(question.trim());
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
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
              ? "Ask a question about your uploaded documents…"
              : "Upload a document first, then ask a question…"
          }
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </div>
      )}

      {!result && !error && !isLoading && (
        <p className="text-sm text-slate-400 italic">
          Retrieved chunks, the generated answer, and latency breakdown will
          appear here after you ask a question.
        </p>
      )}

      <AnswerDisplay result={result} />
    </div>
  );
}
