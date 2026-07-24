# DGX Spark MedGemma RAG

This component is the retrieval-augmented generation stack for the NeoTex demo.

Responsibilities:

- `mqtt-payload-consumer`: Receive telemetry payloads from the edge gateway and store the data for retrieval.
- `rag-service`: Answer queries using context from wearable vitals, medical knowledge, and the MedGemma model.
- `chroma-db`: Manage embeddings and vector search for relevant context retrieval.
- `knowledge-base/neonatal-pediatric`: Provide domain-specific reference documents for neonatal and pediatric care.

Future work:

- Implement a fully-working MedGemma endpoint for local inference.
- Add query instrumentation and retrieval transparency for demo use.
