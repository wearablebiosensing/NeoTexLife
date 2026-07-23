# ASME iShow NeoTex Demo Ideation

## Demo Goal
Build a demonstrable end-to-end flow from wearable vitals capture to parent-facing Q&A:

1. NeoTex wearable belt receiver captures neonatal/pediatric vital data.
2. Edge gateway transforms readings into MQTT feature payloads.
3. DGX Spark MedGemma pipeline receives payloads and stores contextual embeddings in ChromaDB.
4. Parent asks natural-language health questions.
5. RAG service responds with context-aware answers grounded in recent wearable vitals and curated neonatal/pediatric guidance.

## Proposed Dummy Components

- **Belt Receiver (simulated):** produces synthetic heart rate, respiration, temperature, SpO2, activity, and anomaly flags.
- **Edge Gateway:** performs light validation, buffering, and MQTT publish to feature topics.
- **MQTT Payload Consumer:** subscribes to edge topics and normalizes payloads.
- **ChromaDB Layer:** stores document and event embeddings for retrieval.
- **MedGemma RAG Service:** retrieves relevant health context + latest vitals and generates parent-friendly responses.

## MQTT Topic Ideation

- `neotex/vitals/raw/{patient_id}`
- `neotex/vitals/features/{patient_id}`
- `neotex/alerts/{patient_id}`

## Retrieval Context Ideation

- Neonatal baseline ranges and cautions.
- Pediatric range progression by age band.
- Parent-friendly explanation snippets.
- Recent patient-specific trend summaries.

## Example Parent Query Types

- “Is my baby’s breathing trend normal over the last hour?”
- “What does this oxygen dip alert mean?”
- “Should I monitor temperature more frequently tonight?”

## Next Build Steps

- Add dummy payload schemas in each service folder.
- Add local docker-compose for MQTT + ChromaDB.
- Add scripted synthetic data producer for demo scenarios.
- Add API contract for question-answer endpoint.
