# Source Scaffold

This `src` scaffold is for the ASME iShow NeoTex innovation demo:

- `neotex-belt-receiver`: PyQt5 baby-belt Signal View — CSV file playback (looks live), NeuroKit2 vitals every 5 s, FastAPI JSON on `127.0.0.1:8765` for Svelte / nurse UI. See that folder’s README for endpoints and payload shapes.
- `edge-gateway`: Edge gateway that receives belt telemetry and publishes MQTT feature payloads.
- `dgx-spark-medgemma-rag`: DGX Spark MedGemma language-model and retrieval stack.
  - `mqtt-payload-consumer`: Ingests MQTT payloads from edge gateway.
  - `rag-service`: Handles parent queries using wearable vitals context.
  - `chroma-db`: ChromaDB embeddings and vector index layer.
  - `knowledge-base/neonatal-pediatric`: Domain documents for neonatal and pediatric retrieval context.
