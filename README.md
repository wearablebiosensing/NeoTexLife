# NeoTexLife

Repo for ASME ISHOW 2026 demo for NeoTex live system (neonatal multi-vitals belt + edge gateway + DGX Spark nurse agent).

## Demo pieces

| Path | What it does |
|------|----------------|
| [`src/neotex-belt-receiver`](src/neotex-belt-receiver) | PyQt5 Signal View — CSV “live” playback, NeuroKit2 vitals every 5 s, **FastAPI JSON** on `127.0.0.1:8765` for Svelte / agents |
| `src/edge-gateway` | Edge gateway → MQTT feature payloads |
| `src/dgx-spark-medgemma-rag` | MedGemma + RAG (MQTT consumer, rag-service, chroma, neonatal KB) |

### Belt receiver quick start

```bash
cd src/neotex-belt-receiver
uv venv --python 3.12 && uv pip install -r requirements.txt
uv run python main.py --neonate --autoplay
# JSON: http://127.0.0.1:8765/vitals/latest  ·  docs: /docs
```

Sample / demo CSVs live in [`sample-files/`](sample-files). Full API + Svelte usage: [`src/neotex-belt-receiver/README.md`](src/neotex-belt-receiver/README.md).

See [`docs/ideation/asme-ishow-demo-ideation.md`](docs/ideation/asme-ishow-demo-ideation.md) for ideation.
