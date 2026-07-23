# Source Scaffold

This `src` scaffold is for the ASME iShow NeoTex innovation demo:

- `neotex-belt-receiver`: Simulated wearable belt receiver component.
- `edge-gateway`: Edge gateway that receives belt telemetry and publishes MQTT feature payloads.
- `dgx-spark-medgemma-rag`: DGX Spark MedGemma language-model and retrieval stack.
  - `mqtt-payload-consumer`: Ingests MQTT payloads from edge gateway.
  - `rag-service`: Handles parent queries using wearable vitals context.
  - `chroma-db`: ChromaDB embeddings and vector index layer.
  - `knowledge-base/neonatal-pediatric`: Domain documents for neonatal and pediatric retrieval context.
