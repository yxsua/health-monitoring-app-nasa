"""Measure local Ollama latency without writing prompt or response text."""
import json
import argparse
import math
import os
import sys
import time

from .model_adapter import ModelUnavailable, language, reply
from .models import ConversationTurn

PROMPTS = {
    "en": (
        "Help me think of one small way to make time for rest after a demanding day.",
        "Ask me a gentle question to help me reflect on how my week has been going.",
        "Suggest a brief, non-medical grounding activity I can try during a break.",
        "I have had a busy day and feel tired. Help me choose one manageable next step.",
    ),
    "es": (
        "Ayúdame a encontrar una forma pequeña de descansar después de un día exigente.",
        "Hazme una pregunta amable para reflexionar sobre cómo me ha ido esta semana.",
        "Sugiere una actividad breve y no médica para centrarme durante un descanso.",
        "Tuve un día ocupado y estoy cansado. Ayúdame a elegir un siguiente paso sencillo.",
    ),
}
P95_TARGET_SECONDS = 20.0


def percentile95(values):
    return sorted(values)[max(0, math.ceil(0.95 * len(values)) - 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=30, help="Measured replies (default: 30; range: 5–300).")
    args = parser.parse_args()
    if not 5 <= args.samples <= 300:
        parser.error("--samples must be between 5 and 300")
    if not os.environ.get("CHATBOT_LOCAL_MODEL_URL", "").strip() or not os.environ.get("CHATBOT_LOCAL_MODEL_NAME", "").strip():
        print("Set CHATBOT_LOCAL_MODEL_URL and CHATBOT_LOCAL_MODEL_NAME to a local Ollama service first.", file=sys.stderr)
        return 2
    durations = []
    failures = 0
    prompts = PROMPTS[language()]
    warmup_started = time.perf_counter()
    try:
        reply([ConversationTurn(role="user", content=prompts[0])])
    except ModelUnavailable:
        print("Local model warm-up failed; no prompt or reply text was saved.", file=sys.stderr)
        return 2
    warmup_seconds = time.perf_counter() - warmup_started
    for index in range(args.samples):
        started = time.perf_counter()
        try:
            reply([ConversationTurn(role="user", content=prompts[index % len(prompts)])])
            durations.append(time.perf_counter() - started)
        except ModelUnavailable:
            failures += 1
            break
    report = {
        "model": os.environ["CHATBOT_LOCAL_MODEL_NAME"],
        "language": language(),
        "warmup_seconds": round(warmup_seconds, 2),
        "samples": len(durations),
        "failures": failures,
        "median_seconds": round(sorted(durations)[len(durations) // 2], 2) if durations else None,
        "p95_seconds": round(percentile95(durations), 2) if durations else None,
        "p95_target_seconds": P95_TARGET_SECONDS,
        "target_met": bool(durations) and failures == 0 and percentile95(durations) <= P95_TARGET_SECONDS,
        "raw_prompt_or_reply_saved": False,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
