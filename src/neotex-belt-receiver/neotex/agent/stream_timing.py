"""
Simulate MedGemma-27B-on-DGX-Spark latency for the booth mock nurse.

Benchmarks (GGUF Q4_K_M / Gemma3-27B class on DGX Spark): ~11–12 tok/s decode.
We stream at ~12 tok/s with a short visible reasoning phase first.
"""

from __future__ import annotations

from typing import Any, Optional

from neotex.agent.mock_nurse import ScriptAnswer, compose_reply, match_intent


# DGX Spark · MedGemma / Gemma3 27B Q4 decode (approx.)
TOKENS_PER_SEC = 12.0
CHARS_PER_TOKEN = 4.0  # English clinical prose ≈ 3.5–4.5
STREAM_CHARS_PER_SEC = TOKENS_PER_SEC * CHARS_PER_TOKEN  # ≈ 48 char/s

# Thinking / prefill feel (not full prompt-eval; readable booth pacing)
THINK_STEP_MS = 700
THINK_MIN_STEPS = 3


def build_thinking_steps(
    question: str,
    history: list[dict[str, Any]],
    intent: Optional[ScriptAnswer] = None,
) -> list[str]:
    """Short grounded reasoning the UI shows before streaming the answer."""
    intent = intent or match_intent(question)
    latest = _latest_vitals(history)

    steps = [
        "Reading the parent question and matching it to NICU parent-guidance topics…",
        "Pulling the last few minutes of belt vitals (HR, RR, SpO₂, temp) for a trend line…",
    ]

    if latest:
        hr = latest.get("hr_bpm")
        rr = latest.get("rr_bpm")
        spo2 = latest.get("spo2_pct")
        bits = []
        if hr is not None:
            bits.append(f"HR {hr:.0f}")
        if rr is not None:
            bits.append(f"RR {rr:.0f}")
        if spo2 is not None:
            bits.append(f"SpO₂ {spo2:.0f}%")
        if bits:
            steps.append("Current window looks like " + ", ".join(bits) + " — checking against spell thresholds…")
        if spo2 is not None and spo2 < 90:
            steps.append("SpO₂ is soft in this window; weighing acrocyanosis vs a true desaturation pattern…")
        elif hr is not None and hr < 100:
            steps.append("Heart rate is in a lower band; relating that to apnea/bradycardia spell language…")
        else:
            steps.append("Vitals look nearer baseline; still explaining what each number means in plain language…")
    else:
        steps.append("No live vitals windows yet — answering from guidance and noting the missing trend…")

    if intent.id == "acrocyanosis_vitals":
        steps.append(
            "Distinguishing bluish hands/feet (often peripheral) from central cyanosis, "
            "then clarifying HR / RR / SpO₂ together…"
        )
    elif intent.id == "apnea_brady":
        steps.append("Framing apnea of prematurity and how bradycardia / desat define a spell…")
    elif intent.id == "breathing_now":
        steps.append("Comparing periodic breathing vs a true apnea pause against the RR trend…")
    else:
        steps.append(f"Drafting a grounded reply on “{intent.title}” with the vital line attached…")

    steps.append("Composing the answer…")
    return steps


def prepare_streamed_reply(
    question: str,
    history: list[dict[str, Any]],
    *,
    window_s: float = 180.0,
) -> dict[str, Any]:
    """Full payload for UI: thinking steps + final text + stream timing."""
    intent = match_intent(question)
    reply = compose_reply(question, history, window_s=window_s)
    thinking = build_thinking_steps(question, history, intent=intent)
    return {
        **reply,
        "thinking_steps": thinking,
        "tokens_per_sec": TOKENS_PER_SEC,
        "chars_per_sec": STREAM_CHARS_PER_SEC,
    }


def _latest_vitals(history: list[dict[str, Any]]) -> dict[str, float]:
    for item in reversed(history or []):
        v = item.get("vitals") or {}
        out: dict[str, float] = {}
        for key in ("hr_bpm", "rr_bpm", "spo2_pct", "temp_f"):
            val = v.get(key)
            if isinstance(val, (int, float)):
                out[key] = float(val)
        if out:
            return out
    return {}


__all__ = [
    "TOKENS_PER_SEC",
    "STREAM_CHARS_PER_SEC",
    "THINK_STEP_MS",
    "build_thinking_steps",
    "prepare_streamed_reply",
]
