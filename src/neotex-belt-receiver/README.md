# NeoTex Belt Receiver — Live Demo Playback

PyQt5 **Signal View** that plays baby-belt CSV at native rate (looks like a USB COM livestream), runs NeuroKit2 vitals every **5 s**, and publishes JSON on **FastAPI** for a Svelte (or any) front end / nurse agent.

Default API: `http://127.0.0.1:8765` (CORS open for local demos).

## What’s in this package

| Piece | Role |
|-------|------|
| Signal View GUI | HR / RR / SpO₂ / Temp cards + ECG, RED, IR, Resp plots |
| CSV playback | Chunked ~100 Hz stream from `sample-files/*.csv` |
| Demo synth | Scenario: 30 s normal → slowing Resp + ↓SpO₂ + bradycardia (real-bio warped) |
| NeuroKit2 metrics | Every 5 s over a ~20 s analysis window |
| FastAPI | `/vitals/latest`, `/vitals/history`, `/health`, `/status` |

```
neotex-belt-receiver/
  main.py
  requirements.txt
  neotex/
    ui/            # Signal View + hamburger setup drawer + vital icons
    workers/       # Playback + metrics threads
    processing/    # Display/analysis filters, SpO₂, IMU→resp
    api/           # FastAPI + thread-safe vitals store
    utils/         # CSV loader, ring buffer, neonate synth, scenario
```

## Run

```bash
cd src/neotex-belt-receiver
uv venv --python 3.12
uv pip install -r requirements.txt

# Scenario demo (30s normal → bradypnea/desat/↓HR) + autoplay
uv run python main.py --neonate --autoplay
# same:
uv run python main.py --scenario --autoplay

# Or Setup → "Generate scenario demo"
uv run python main.py
```

**Scenario timeline:** 0–30 s baseline → 30–45 s ramp (slower Resp, falling SpO₂, HR down) → 45–75 s nadir → recovery. Status bar shows the active phase.

Setup drawer: streams on/off, per-channel prep (ECG / PPG AC / resp), RR source (auto / Resp / Ch1), generate scenario.

Sampling rate is inferred from `PC_Time` / `InterArrival` (nominally **100 Hz**).

---

## FastAPI JSON (for Svelte / any client)

The GUI process starts uvicorn on **`127.0.0.1:8765`**. Metrics land in a shared store whenever the processing worker finishes a window (~every 5 s).

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness + streaming flag |
| `GET` | `/status` | Playback / file / history length |
| `GET` | `/vitals/latest` | Newest metrics envelope (or `status: "waiting"`) |
| `GET` | `/vitals/history?limit=50` | Recent windows (`limit` 1–500) |
| — | `/docs` | Swagger UI |

### Latest payload shape

```json
{
  "unix_timestamp": 1753315200.123,
  "window_s": 5.0,
  "analysis_window_s": 20.0,
  "sampling_rate_hz": 100.0,
  "source": "file_playback",
  "file": "NEONATE_SYNTH_DEMO.csv",
  "rr_source": "resp0",
  "vitals": {
    "hr_bpm": 138.2,
    "rr_bpm": 42.1,
    "spo2_pct": 97.4,
    "temp_f": 98.9
  },
  "quality": {
    "ecg_sqi": 0.91,
    "n_r_peaks": 24,
    "n_rsp_peaks": 12
  },
  "preview": {
    "ecg_n": 2000,
    "rsp_n": 2000
  }
}
```

Notes:

- `unix_timestamp` — seconds since epoch (float) when that window was computed.
- `temp_f` — temperature in **°F** (belt dump convention).
- Fields under `vitals` may be `null` if a channel failed that window; check `error` if present.
- Before the first metrics tick, `/vitals/latest` returns:

```json
{
  "unix_timestamp": null,
  "vitals": { "hr_bpm": null, "rr_bpm": null, "spo2_pct": null, "temp_f": null },
  "status": "waiting"
}
```

### History payload

```json
{
  "count": 12,
  "items": [ { "...same as latest..." }, ... ]
}
```

### Quick curl checks

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/vitals/latest
curl "http://127.0.0.1:8765/vitals/history?limit=20"
```

---

## Using this from Svelte

CORS allows browser calls from a Vite/SvelteKit app on another localhost port.

### 1. Types

```ts
// src/lib/neotexVitals.ts
export type NeoTexVitals = {
  hr_bpm: number | null;
  rr_bpm: number | null;
  spo2_pct: number | null;
  temp_f: number | null;
};

export type NeoTexMetrics = {
  unix_timestamp: number | null;
  window_s?: number;
  analysis_window_s?: number;
  sampling_rate_hz?: number;
  source?: string;
  file?: string | null;
  rr_source?: string;
  vitals: NeoTexVitals;
  quality?: Record<string, unknown>;
  preview?: Record<string, unknown>;
  error?: string;
  status?: 'waiting';
};

export type NeoTexHistory = {
  count: number;
  items: NeoTexMetrics[];
};

export const NEOTEX_API = 'http://127.0.0.1:8765';
```

### 2. Poll latest (recommended for cards)

Metrics update about every **5 seconds** — poll at 1–5 s.

```svelte
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { NEOTEX_API, type NeoTexMetrics } from '$lib/neotexVitals';

  let metrics: NeoTexMetrics | null = null;
  let err = '';
  let timer: ReturnType<typeof setInterval>;

  async function refresh() {
    try {
      const res = await fetch(`${NEOTEX_API}/vitals/latest`);
      if (!res.ok) throw new Error(`${res.status}`);
      metrics = await res.json();
      err = '';
    } catch (e) {
      err = e instanceof Error ? e.message : String(e);
    }
  }

  onMount(() => {
    refresh();
    timer = setInterval(refresh, 2000);
  });
  onDestroy(() => clearInterval(timer));
</script>

{#if err}
  <p>API offline — start the belt receiver GUI.</p>
{:else if metrics?.status === 'waiting' || metrics?.unix_timestamp == null}
  <p>Waiting for first vitals window…</p>
{:else}
  <p>HR {metrics.vitals.hr_bpm?.toFixed(1)} bpm</p>
  <p>RR {metrics.vitals.rr_bpm?.toFixed(1)} /min</p>
  <p>SpO₂ {metrics.vitals.spo2_pct?.toFixed(1)} %</p>
  <p>Temp {metrics.vitals.temp_f?.toFixed(1)} °F</p>
  <small>{new Date((metrics.unix_timestamp ?? 0) * 1000).toLocaleTimeString()}</small>
{/if}
```

### 3. History for sparklines / trends

```ts
export async function fetchHistory(limit = 50): Promise<NeoTexHistory> {
  const res = await fetch(`${NEOTEX_API}/vitals/history?limit=${limit}`);
  if (!res.ok) throw new Error(`history ${res.status}`);
  return res.json();
}

// Example: HR series for a chart
const { items } = await fetchHistory(60);
const hrSeries = items
  .filter((m) => m.unix_timestamp != null && m.vitals.hr_bpm != null)
  .map((m) => ({ t: m.unix_timestamp as number, hr: m.vitals.hr_bpm as number }));
```

### 4. Env tip (SvelteKit)

```env
# .env
PUBLIC_NEOTEX_API=http://127.0.0.1:8765
```

```ts
import { publicEnv } from '$env/dynamic/public';
export const NEOTEX_API = publicEnv.PUBLIC_NEOTEX_API ?? 'http://127.0.0.1:8765';
```

### Demo flow for ASME iShow

1. Start receiver: `uv run python main.py --neonate --autoplay`
2. Confirm `curl http://127.0.0.1:8765/vitals/latest` returns numbers after ~5–20 s
3. Point Svelte vitals cards / nurse UI at that base URL
4. Optional: edge-gateway / MQTT can wrap the same JSON later; payload fields stay the same

This API is **vitals-only** (not raw waveform samples). Waveforms stay in the PyQt Signal View for the booth monitor.
