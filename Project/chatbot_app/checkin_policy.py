"""Transparent, non-clinical demo rule for self-reported check-in trends."""
from datetime import date, timedelta

POLICY_VERSION = "self-check-in-trend-1.0.0"
BASELINE_DAYS = 7
RECENT_DAYS = 3
MIN_SLEEP_DECLINE_HOURS = 1.0
MIN_MOOD_DECLINE_POINTS = 1.0


def evaluate(rows, today: date, evaluated_at: str):
    """Suggest a conversation only when both signals worsen against personal baseline.

    Requires one entry for each of the 10 consecutive UTC dates ending today.
    The first seven entries form the baseline; the latest three form the recent
    window. This rule is a prototype prompt policy, not a clinical threshold.
    """
    by_date = {date.fromisoformat(row["check_in_date"]): row for row in rows}
    window_dates = [today - timedelta(days=offset) for offset in range(BASELINE_DAYS + RECENT_DAYS - 1, -1, -1)]
    window = [by_date.get(day) for day in window_dates]
    if any(row is None for row in window):
        return {
            "policy_version": POLICY_VERSION,
            "status": "insufficient_data",
            "evaluated_at": evaluated_at,
            "baseline_days": BASELINE_DAYS,
            "recent_days": RECENT_DAYS,
            "baseline_mood_mean": None,
            "recent_mood_mean": None,
            "baseline_sleep_mean_hours": None,
            "recent_sleep_mean_hours": None,
            "message": "A trend prompt needs one check-in on each of the last 10 UTC days.",
        }

    baseline, recent = window[:BASELINE_DAYS], window[BASELINE_DAYS:]
    baseline_mood = sum(row["mood_score"] for row in baseline) / BASELINE_DAYS
    recent_mood = sum(row["mood_score"] for row in recent) / RECENT_DAYS
    baseline_sleep = sum(row["sleep_duration_hours"] for row in baseline) / BASELINE_DAYS
    recent_sleep = sum(row["sleep_duration_hours"] for row in recent) / RECENT_DAYS
    worsening = (
        baseline_mood - recent_mood >= MIN_MOOD_DECLINE_POINTS
        and baseline_sleep - recent_sleep >= MIN_SLEEP_DECLINE_HOURS
    )
    return {
        "policy_version": POLICY_VERSION,
        "status": "check_in_suggested" if worsening else "no_pattern",
        "evaluated_at": evaluated_at,
        "baseline_days": BASELINE_DAYS,
        "recent_days": RECENT_DAYS,
        "baseline_mood_mean": round(baseline_mood, 2),
        "recent_mood_mean": round(recent_mood, 2),
        "baseline_sleep_mean_hours": round(baseline_sleep, 2),
        "recent_sleep_mean_hours": round(recent_sleep, 2),
        "message": (
            "Both mood and sleep are lower than the personal baseline. Consider a private check-in with a qualified support person."
            if worsening else
            "This rule did not detect simultaneous mood and sleep declines in the selected windows. It does not determine wellbeing or safety."
        ),
    }
