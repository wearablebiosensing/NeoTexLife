# Edge Gateway

This component represents the edge gateway for the NeoTex demo.

Responsibilities:

- Consume telemetry from the belt receiver.
- Optionally transform or enrich data for downstream services.
- Publish processed payloads to MQTT topics consumed by the DGX RAG stack.

Future work:

- Add authentication and message filtering.
- Implement payload versioning and schema validation.
