# NeoTex Belt Receiver

This component simulates the neonatal wearable belt receiver.

Responsibilities:

- Receive simulated sensor telemetry from the NeoTex belt.
- Normalize raw vitals data and package payloads for the edge gateway.
- Provide a local demo source for telemetry ingestion.

Future work:

- Add a real sensor emulator or hardware integration layer.
- Publish normalized data to MQTT or HTTP for the edge gateway.
