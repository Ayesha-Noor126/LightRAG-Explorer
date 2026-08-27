import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

// Small helper so components get a clean error message instead of an axios object.
function unwrap(promise) {
  return promise
    .then((res) => res.data)
    .catch((err) => {
      const message =
        err.response?.data?.detail || err.message || "Unknown error occurred.";
      throw new Error(message);
    });
}

export const uploadDocuments = (files) => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return unwrap(
    api.post("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  );
};

export const listDocuments = () => unwrap(api.get("/documents"));

export const deleteDocument = (docId) => unwrap(api.delete(`/documents/${docId}`));

export const clearDocuments = () => unwrap(api.delete("/documents"));

export const rebuildIndex = () => unwrap(api.post("/documents/rebuild"));

export const querySimpleRag = (question, topK) =>
  unwrap(api.post("/query/simple-rag", { question, top_k: topK }));

export const getMetrics = () => unwrap(api.get("/analytics"));

// --- Phase 2: LightRAG / Graph RAG ---

export const queryLightRag = (question, mode, decompose = false) =>
  unwrap(api.post("/query/lightrag", { question, mode, decompose }));

export const getGraphStats = () => unwrap(api.get("/graph/stats"));

export const getGraphData = (limit = 150) =>
  unwrap(api.get("/graph/data", { params: { limit } }));

export const getGraphHealth = () => unwrap(api.get("/graph/health"));

// --- Phase 3: Comparison & Experiment Mode ---

export const compareRag = (question, lightragMode = "hybrid") =>
  unwrap(api.post("/query/compare", { question, lightrag_mode: lightragMode }));

export const recordExperimentSnapshot = (label, notes) =>
  unwrap(api.post("/experiments", { label, notes }));

export const listExperimentSnapshots = () => unwrap(api.get("/experiments"));

export const clearExperimentSnapshots = () => unwrap(api.delete("/experiments"));
