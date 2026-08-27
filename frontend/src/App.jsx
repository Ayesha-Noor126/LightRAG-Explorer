import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import MetricsBar from "./components/MetricsBar";
import QueryPanel from "./components/QueryPanel";
import LightRAGPanel from "./components/LightRAGPanel";
import GraphView from "./components/GraphView";
import ComparisonView from "./components/ComparisonView";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import ExperimentMode from "./components/ExperimentMode";
import Tabs from "./components/Tabs";
import { getMetrics, listDocuments } from "./api/client";

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [activeTab, setActiveTab] = useState("simple-rag");

  const refresh = useCallback(async () => {
    try {
      const [docsRes, metricsRes] = await Promise.all([listDocuments(), getMetrics()]);
      setDocuments(docsRes.documents);
      setMetrics(metricsRes);
      setLoadError(null);
    } catch (err) {
      setLoadError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-xl font-bold text-slate-900">LightRAG Explorer</h1>
        <p className="text-sm text-slate-500">
          Complete — Simple RAG, Graph RAG, Comparison &amp; Experiment Mode
        </p>
      </header>

      <div className="flex min-h-0 flex-1">
        <Sidebar documents={documents} onRefresh={refresh} />

        <main className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-5xl space-y-6">
            {loadError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
                Could not reach the backend: {loadError}. Is it running on
                port 8000?
              </div>
            )}
            <MetricsBar metrics={metrics} />
            <Tabs active={activeTab} onChange={setActiveTab} />

            {activeTab === "simple-rag" && (
              <QueryPanel hasDocuments={documents.length > 0} />
            )}
            {activeTab === "lightrag" && (
              <LightRAGPanel hasDocuments={documents.length > 0} />
            )}
            {activeTab === "comparison" && (
              <ComparisonView hasDocuments={documents.length > 0} />
            )}
            {activeTab === "graph" && <GraphView />}
            {activeTab === "analytics" && <AnalyticsDashboard />}
            {activeTab === "experiments" && <ExperimentMode />}
          </div>
        </main>
      </div>
    </div>
  );
}
