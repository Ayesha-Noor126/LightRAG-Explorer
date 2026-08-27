// Sample questions from the spec's "Query Categories" section, grouped so
// the UI can explain *why* each category is a good Simple-RAG-vs-LightRAG
// test case before the user tries it.
export const QUERY_CATEGORIES = [
  {
    id: "single-document",
    title: "Single-Document Questions",
    blurb:
      "Answerable from one chunk in one document. Simple RAG and LightRAG " +
      "should perform similarly here — a good baseline sanity check.",
    examples: ["What is Neo4j?", "What is LightRAG?"],
  },
  {
    id: "cross-document",
    title: "Cross-Document Questions",
    blurb:
      "Requires connecting facts that live in different uploaded documents. " +
      "This is where Graph RAG's relationship edges start to pay off.",
    examples: [
      "How is LangChain related to Neo4j?",
      "How does ChromaDB compare to FAISS for vector storage?",
    ],
  },
  {
    id: "multi-hop",
    title: "Multi-Hop Questions",
    blurb:
      "Requires chaining through several entities/relationships to answer — " +
      "the clearest case for LightRAG's graph traversal over flat similarity search.",
    examples: [
      "Explain how Neo4j, embeddings, and Graph RAG work together.",
      "How do entity extraction, relationship extraction, and graph construction connect in a Graph RAG pipeline?",
    ],
  },
  {
    id: "relationship",
    title: "Relationship Questions",
    blurb:
      "Asks about connections across the whole corpus rather than content " +
      "within any single document — a natural fit for graph queries.",
    examples: [
      "Which uploaded documents discuss both Neo4j and Graph RAG?",
      "What entities appear across the most documents?",
    ],
  },
];
