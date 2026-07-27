"""
Mock Nurse agent for the ASME / BabyCare booth demo.

Answers follow ``docs/ideation/babycare_demo_script.md`` templates and append a
grounded vital line from the last few minutes of FastAPI vitals history.
Educational only — not clinical advice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Scripted intents (from babycare_demo_script.md), wording tuned for booth chat
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScriptAnswer:
    id: str
    title: str
    body: str
    keywords: tuple[str, ...]


ANSWERS: tuple[ScriptAnswer, ...] = (
    ScriptAnswer(
        id="acrocyanosis_vitals",
        title="Blue hands/feet + reading the numbers",
        keywords=(
            "blue",
            "bluish",
            "hands",
            "feet",
            "acrocyanosis",
            "oxygen level",
            "o2",
            "spo2",
            "don't understand",
            "dont understand",
            "heart rate",
            "resp",
            "how is she",
            "how is he",
            "these numbers",
            "the numbers",
        ),
        body=(
            "Short answer: bluish hands and feet alone are often a common, usually "
            "harmless newborn finding called acrocyanosis — especially if she is cool, "
            "just after a bath or feed, or still settling after birth. It happens because "
            "a baby’s blood vessels in the extremities are still learning to regulate, "
            "so more oxygen is extracted in the hands and feet even when the blood leaving "
            "the heart is well oxygenated. Warming her and rechecking often helps.\n\n"
            "What would worry me more is central cyanosis: a bluish color of the tongue, "
            "inner lips, or gums (and sometimes the face or trunk). That pattern means "
            "arterial oxygen is truly low and needs urgent evaluation — it is not treated "
            "as “just cold hands.” If you only see blue on the palms and soles and the "
            "rest of her looks pink and she is breathing comfortably, that fits "
            "acrocyanosis much better than a lung or heart emergency.\n\n"
            "About the numbers on the monitor — they answer different questions:\n\n"
            "• Oxygen (SpO₂) is the percent of hemoglobin carrying oxygen, measured by "
            "the pulse-ox light sensor. In healthy term babies at sea level after the "
            "newborn transition, values are usually about 95% or higher (often in the "
            "high 90s). In the NICU, for premature babies, a drop below about 85% is "
            "commonly counted as a desaturation — especially when it comes with a "
            "breathing pause or a heart-rate drop. So “oxygen looks okay” on one glance "
            "is reassuring for oxygenation right then, but it is only one piece.\n\n"
            "• Heart rate (HR) is beats per minute. Young infants often run faster than "
            "adults; many resting newborns cluster around the 120–160 range, and "
            "evidence-based charts show typical infant rates well above adult norms. "
            "In apnea-of-prematurity care, a sustained fall below about 100 beats/min "
            "with a breathing pause is the bradycardia part of an “A&B spell.”\n\n"
            "• Respiratory rate (RR) is breaths per minute. Newborns commonly breathe "
            "about 30–60 times a minute, and brief irregular pauses can be normal "
            "periodic breathing. A pause longer than about 20 seconds — or a shorter "
            "pause with bradycardia or desaturation — is treated as apnea of prematurity "
            "and is why continuous monitoring is used.\n\n"
            "How to read them together: do not judge her from SpO₂ alone. Ask — Is the "
            "blue only on hands/feet, or also tongue/lips? Is she breathing hard "
            "(flaring, grunting, pulling in at the ribs)? Is HR or RR falling with the "
            "color change? Hands-and-feet blue with a stable SpO₂ in the mid–high 90s "
            "and comfortable breathing is a very different story from blue lips plus "
            "falling oxygen or a slowing heart rate. Use the trend over the last few "
            "minutes, not a single snapshot.\n\n"
            "If her tongue or lips look blue, she seems limp or hard to wake, or "
            "breathing looks labored, call your care team or emergency services right "
            "away — do not wait for the numbers to “look worse.”"
        ),
    ),
    ScriptAnswer(
        id="apnea_brady",
        title="Apnea and bradycardia spells",
        keywords=(
            "apnea",
            "bradycardia",
            "brady",
            "spell",
            "spells",
            "a&b",
            "a and b",
        ),
        body=(
            "Apnea of prematurity is one of the most common conditions in the NICU. "
            "It means a pause in breathing longer than about 20 seconds — or a shorter "
            "pause paired with a drop in heart rate (bradycardia, below 100 beats/min) "
            "or oxygen level (desaturation, below about 85%). It happens because a "
            "premature baby’s brain and breathing-control systems are still immature, "
            "not because anything is fundamentally wrong with the lungs. It is usually "
            "monitored continuously, often treated with caffeine to stimulate breathing, "
            "and typically resolves as the baby matures — a common benchmark is 5–7 days "
            "free of events."
        ),
    ),
    ScriptAnswer(
        id="breathing_now",
        title="Is breathing normal right now?",
        keywords=(
            "breathing normally",
            "breathing ok",
            "breathing okay",
            "is my baby breathing",
            "respirat",
        ),
        body=(
            "Newborns typically breathe 30–60 times a minute, and irregular breathing "
            "with brief pauses is common. In a premature baby, though, a pause beyond "
            "about 20 seconds — or a shorter pause with a heart-rate or oxygen drop — "
            "is defined as apnea of prematurity and is monitored closely. The "
            "distinction that matters is between normal periodic breathing and a true "
            "apnea spell. Persistent fast breathing above 60/min, nostril flaring, "
            "chest pulling-in, grunting, or any bluish colour of the lips or face "
            "needs prompt attention."
        ),
    ),
    ScriptAnswer(
        id="corrected_age",
        title="Corrected age / milestones",
        keywords=(
            "weeks old",
            "corrected age",
            "milestones",
            "doesn't do",
            "doesnt do",
            "development",
        ),
        body=(
            "For a premature baby, use corrected age rather than age since birth for "
            "the first two years. Take age in weeks since birth and subtract how many "
            "weeks early the baby was born (40 minus gestational age at birth). For "
            "example, born at 32 weeks is 8 weeks early; at 16 weeks old, corrected "
            "age is 8 weeks — you’d expect skills closer to a 2-month-old, not a "
            "4-month-old. That is the American Academy of Pediatrics standard, and "
            "most preemies catch up to term peers by about age 2."
        ),
    ),
    ScriptAnswer(
        id="kangaroo",
        title="Skin-to-skin / kangaroo care",
        keywords=(
            "skin-to-skin",
            "skin to skin",
            "kangaroo",
            "holding",
        ),
        body=(
            "It genuinely helps. Skin-to-skin (“kangaroo”) care has been associated "
            "with fewer apnea and bradycardia episodes in premature babies, alongside "
            "more stable temperature and better feeding. A stable thermal environment "
            "and gentle, clustered care are part of the same picture — one of the few "
            "things a parent can do directly at the bedside that supports stability."
        ),
    ),
    ScriptAnswer(
        id="going_home",
        title="When can baby come home?",
        keywords=(
            "come home",
            "go home",
            "discharge",
            "car seat",
        ),
        body=(
            "Most NICUs look for a stretch of stability rather than a fixed date. A "
            "common benchmark is 5–7 days with no clinically significant apnea, "
            "bradycardia, or desaturation spells. Before discharge, preterm babies "
            "also typically pass a car-seat challenge, feed reliably, and keep "
            "temperature in an open crib. Only a small number go home on a monitor."
        ),
    ),
)


FALLBACK_BODY = (
    "I can help with common NICU parent questions — apnea/bradycardia spells, "
    "whether breathing looks okay, bluish hands or feet and oxygen numbers, "
    "corrected age, skin-to-skin care, and going-home readiness. "
    "Try asking about her colour and what the heart rate, breathing, and oxygen "
    "numbers mean together."
)

DISCLAIMER = (
    "If you are worried about your baby’s colour, breathing, or alertness, "
    "call your care team or emergency services."
)

# Default example parent question (internal; not shown as a demo chip)
DEMO_PROMPT = (
    "Her hands and feet look a little blue, how is she? "
    "I don't understand these numbers; oxygen level is okay?"
)


def _norm(text: str) -> str:
    t = text.lower().strip()
    t = t.replace("’", "'").replace("‘", "'")
    t = re.sub(r"\s+", " ", t)
    return t


def match_intent(question: str) -> ScriptAnswer:
    q = _norm(question)
    # Prefer the combined blue/vitals literacy intent when both themes appear
    blueish = any(k in q for k in ("blue", "bluish", "hands", "feet", "acrocyanosis"))
    numbers = any(
        k in q
        for k in (
            "heart rate",
            "hr",
            "resp",
            "oxygen",
            "spo2",
            "o2",
            "don't understand",
            "dont understand",
            "number",
        )
    )
    if blueish and numbers:
        return ANSWERS[0]
    if blueish or ("oxygen" in q and ("okay" in q or "ok" in q or "level" in q)):
        return ANSWERS[0]

    best: Optional[ScriptAnswer] = None
    best_hits = 0
    for ans in ANSWERS:
        hits = sum(1 for kw in ans.keywords if kw in q)
        if hits > best_hits:
            best_hits = hits
            best = ans
    if best is not None and best_hits > 0:
        return best
    return ScriptAnswer(
        id="fallback",
        title="General",
        body=FALLBACK_BODY,
        keywords=(),
    )


def _collect_vitals_window(
    history: list[dict[str, Any]],
    window_s: float = 180.0,
) -> dict[str, list[float]]:
    """Pull numeric vitals from history covering roughly the last ``window_s``."""
    out: dict[str, list[float]] = {
        "hr_bpm": [],
        "rr_bpm": [],
        "spo2_pct": [],
        "temp_f": [],
        "ts": [],
    }
    if not history:
        return out

    latest_ts = None
    for item in reversed(history):
        ts = item.get("unix_timestamp")
        if isinstance(ts, (int, float)):
            latest_ts = float(ts)
            break

    for item in history:
        ts = item.get("unix_timestamp")
        if latest_ts is not None and isinstance(ts, (int, float)):
            if float(ts) < latest_ts - window_s:
                continue
        vitals = item.get("vitals") or {}
        for key in ("hr_bpm", "rr_bpm", "spo2_pct", "temp_f"):
            val = vitals.get(key)
            if isinstance(val, (int, float)):
                out[key].append(float(val))
        if isinstance(ts, (int, float)):
            out["ts"].append(float(ts))
    return out


def _fmt(vals: list[float], unit: str = "", digits: int = 1) -> str:
    if not vals:
        return "—"
    cur = vals[-1]
    mean = sum(vals) / len(vals)
    lo, hi = min(vals), max(vals)
    trend = ""
    if len(vals) >= 3:
        early = sum(vals[: max(1, len(vals) // 3)]) / max(1, len(vals) // 3)
        late = sum(vals[-max(1, len(vals) // 3) :]) / max(1, len(vals) // 3)
        delta = late - early
        if abs(delta) >= (3.0 if "bpm" in unit or "/min" in unit else 1.0):
            trend = " ↓" if delta < 0 else " ↑"
        else:
            trend = " steady"
    u = f" {unit}" if unit else ""
    return f"{cur:.{digits}f}{u} (avg {mean:.{digits}f}, range {lo:.{digits}f}–{hi:.{digits}f}){trend}"


def _clinical_flags(series: dict[str, list[float]]) -> list[str]:
    notes: list[str] = []
    hr = series["hr_bpm"]
    rr = series["rr_bpm"]
    spo2 = series["spo2_pct"]
    if hr and min(hr) < 100:
        notes.append("heart rate dipped below ~100 bpm in this window (bradycardia range used in A&B spells)")
    if rr and (min(rr) < 25 or (len(rr) >= 2 and rr[-1] < 0.7 * (sum(rr) / len(rr)))):
        notes.append("breathing looks slower than a typical newborn resting band in this window")
    if spo2 and min(spo2) < 90:
        if min(spo2) < 85:
            notes.append("SpO₂ crossed below ~85% (desaturation threshold often used for spells)")
        else:
            notes.append("SpO₂ dipped under 90% — worth watching alongside HR and RR")
    if spo2 and spo2[-1] >= 95 and hr and hr[-1] < 110:
        notes.append(
            "oxygen can look acceptable while heart rate is still low — read HR, RR, and SpO₂ together"
        )
    return notes


def vital_trend_line(history: list[dict[str, Any]], window_s: float = 180.0) -> str:
    series = _collect_vitals_window(history, window_s=window_s)
    n = max(len(series["hr_bpm"]), len(series["spo2_pct"]), 0)
    if n == 0:
        return (
            "Vital line (last few minutes): no live windows yet — start playback and "
            "wait ~5–20 s for the first NeuroKit update."
        )

    span = window_s / 60.0
    lines = [
        f"Vital line (last ~{span:.0f} min from belt stream):",
        f"  • HR  {_fmt(series['hr_bpm'], 'bpm')}",
        f"  • RR  {_fmt(series['rr_bpm'], '/min')}",
        f"  • SpO₂ {_fmt(series['spo2_pct'], '%')}",
        f"  • Temp {_fmt(series['temp_f'], '°F')}",
        "Term resting references (Fleming 2011-style bands) are age-dependent; "
        "for preemies, corrected age matters. These are live belt readings, not alarm limits.",
    ]
    flags = _clinical_flags(series)
    if flags:
        lines.append("What stands out in this window:")
        for f in flags:
            lines.append(f"  • {f}")
    return "\n".join(lines)


def compose_reply(
    question: str,
    history: list[dict[str, Any]],
    *,
    window_s: float = 180.0,
) -> dict[str, str]:
    """Return structured mock nurse reply for the GUI."""
    intent = match_intent(question)
    vitals = vital_trend_line(history, window_s=window_s)
    text = (
        f"{intent.body}\n\n"
        f"{vitals}\n\n"
        f"— {DISCLAIMER}"
    )
    return {
        "intent_id": intent.id,
        "title": intent.title,
        "question": question.strip(),
        "text": text,
    }


__all__ = [
    "DEMO_PROMPT",
    "ANSWERS",
    "compose_reply",
    "match_intent",
    "vital_trend_line",
]
