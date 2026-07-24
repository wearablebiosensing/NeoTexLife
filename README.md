# NeoTexLife

Repo for ASME ISHOW 2026 demo for the NeoTex live system, including neonatal multi-vitals belt, edge gateway, and DGX Spark nurse agent.

## Repo Structure

This repository contains a lightweight demo scaffold for the full NeoTex system:

- `src/neotex-belt-receiver`: Simulates the wearable belt receiver and local telemetry ingestion.
- `src/edge-gateway`: Edge gateway service that receives belt telemetry and publishes MQTT payloads.
- `src/dgx-spark-medgemma-rag`: DGX-based RAG service for parent queries and MedGemma inference.
  - `mqtt-payload-consumer`: Ingests MQTT payloads from the edge gateway.
  - `rag-service`: Handles retrieval-based queries using wearable vitals and domain context.
  - `chroma-db`: Embeddings and vector index storage layer.
  - `knowledge-base/neonatal-pediatric`: Domain documents for neonatal and pediatric retrieval context.

## Demo Vision

The goal is to demonstrate a private-network RAG workflow where local sensors feed an edge gateway, context is stored on a DGX-powered retrieval stack, and MedGemma provides private LLM answers.

## Notes

- This repository is intentionally lightweight and intended as a scaffold for the ASME demo.
- The existing docs and README files describe the expected architecture, but concrete implementation is not yet complete.
- See `/home/runner/work/NeoTexLife/NeoTexLife/docs/ideation/asme-ishow-demo-ideation.md` for ideation details.
