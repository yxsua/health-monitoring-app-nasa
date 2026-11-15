"""Deterministic recommendation layer. Guidance is informational, not clinical."""
from uuid import uuid5, NAMESPACE_URL


POLICY_VERSION = "recommendations-demo-v1"

TOPIC_GUIDANCE = {
    "sleep_rest": ("Review rest routine", "Consider reviewing your rest routine and sharing any ongoing sleep concern with a qualified support person."),
    "stress_support": ("Make space for stress support", "Consider a brief check-in with a trusted crew member or the qualified support channel available to you."),
    "exercise_recovery": ("Review activity and recovery", "Consider reviewing recent activity and recovery context with the appropriate crew support."),
    "cabin_conditions": ("Review cabin conditions", "Consider reviewing the current cabin readings and following the applicable environmental procedure."),
    "human_support": ("Follow up with a support person", "You selected human support as a topic. Consider reaching out to a trusted crew member or qualified support person."),
}


def _recommendation(priority, title, action, rationale, scope, refs, observed_at=None, evidence=None, stable_id=None):
    seed = stable_id or "|".join([scope, title, *(str(value) for value in refs)])
    return {
        "recommendation_id": str(uuid5(NAMESPACE_URL, POLICY_VERSION + ":" + seed)),
        "priority": priority, "title": title, "action": action, "rationale": rationale,
        "source_scope": scope, "source_refs": refs, "observed_at": observed_at,
        "evidence": evidence or [],
    }


def evaluate(profile, dashboard=None, topics=()):
    """Create independent outputs for profile, fixture, and user-shared sources."""
    items = []
    follow_up = profile.get("follow_up_requested", False)
    if follow_up:
        items.append(_recommendation(
            "warning", "Wellbeing follow-up requested",
            "Review the assessment follow-up with a qualified support person; use the onboard support procedure if you feel unsafe.",
            "A structured screening response requested follow-up. This does not determine immediate danger or notify anyone.",
            "astronaut_profile", profile.get("flag_refs", []), profile.get("updated_at"),
            stable_id="profile-follow-up",
        ))
    for result in profile.get("assessments", []):
        band = result.get("interpretation", "minimal_symptom_range")
        if band not in ("minimal_symptom_range", "minimal"):
            items.append(_recommendation(
                "caution", "Review screening result",
                "Consider reviewing this screening result with a qualified support person. It is not a diagnosis or fitness determination.",
                "The latest completed structured screening result is outside its minimal symptom range.",
                "astronaut_profile", [result["result_id"]], result.get("completed_at"),
                evidence=[{"field": result["assessment_code"], "value": result["total_score"], "unit": f"of {result['maximum_score']}", "quality": "valid"}],
                stable_id="assessment:" + result["result_id"],
            ))
    if profile.get("check_in_status") == "check_in_suggested":
        items.append(_recommendation(
            "caution", "Check in on recent wellbeing",
            "Consider completing a mood and sleep check-in, then review any ongoing concern with a qualified support person.",
            "The check-in trend policy detected a pattern that suggests a follow-up check-in.",
            "astronaut_profile", [profile.get("check_in_policy", "check-in-trend-v1")], profile.get("check_in_observed_at"),
            stable_id="check-in-trend:" + str(profile.get("check_in_observed_at")),
        ))

    if dashboard:
        run_ref = dashboard.get("run_id", "")
        record_ref = dashboard.get("record_id", "")
        refs = [value for value in (dashboard.get("source_subject_id"), run_ref, record_ref) if value]
        observed_at = dashboard.get("observed_at")
        rules = dashboard.get("rules", {})
        for alert in rules.get("alerts", []):
            severity = alert.get("severity")
            if severity not in ("caution", "warning", "critical"):
                continue
            action = {
                "critical": "Follow the applicable onboard response procedure and contact qualified crew support.",
                "warning": "Confirm the reading and sensor quality, then review the applicable onboard response procedure.",
                "caution": "Review this reading, repeat it using the approved sensor procedure if appropriate, and note relevant context.",
            }[severity]
            items.append(_recommendation(
                severity, alert.get("message", "Rule alert"), action,
                "This alert was returned by the simulator rule engine. Its demonstration thresholds are not clinically validated.",
                "simulated_fixture", refs + ["system:" + alert.get("system", "unknown"), alert.get("code", "rule")], observed_at,
                evidence=alert.get("evidence", []),
                stable_id=f"fixture:{run_ref}:{record_ref}:{alert.get('code', 'rule')}",
            ))
        anomaly = dashboard.get("anomaly", {})
        if anomaly.get("status") == "available" and anomaly.get("is_anomaly") is True:
            items.append(_recommendation(
                "caution", "Unusual simulated measurement pattern",
                "Review the sample and sensor quality. An anomaly flag is not a diagnosis or a rule alert.",
                "The simulator anomaly model flagged this sample for review.", "simulated_fixture",
                refs + [anomaly.get("model_version") or "isolation-forest"], observed_at,
                stable_id=f"fixture-anomaly:{run_ref}:{record_ref}",
            ))
        forecast = dashboard.get("forecast", {})
        if forecast.get("status") == "available":
            items.append(_recommendation(
                "routine", "Review next-step projection",
                "Use the projection as a planning signal only; compare it with new readings as they arrive.",
                "A simulator forecast is available, but it is not a clinical prediction.", "simulated_fixture",
                refs + [forecast.get("model_version") or "lstm-projection"], forecast.get("target_time") or observed_at,
                stable_id=f"fixture-forecast:{run_ref}:{record_ref}",
            ))

    for topic in dict.fromkeys(topics):
        if topic in TOPIC_GUIDANCE:
            title, action = TOPIC_GUIDANCE[topic]
            items.append(_recommendation(
                "routine", title, action,
                "You explicitly chose to share this topic from the conversation. No conversation text is stored or analyzed here.",
                "user_confirmed_context", [topic], stable_id="shared-topic:" + topic,
            ))
    order = {"critical": 0, "warning": 1, "caution": 2, "routine": 3}
    items.sort(key=lambda item: (order[item["priority"]], item["source_scope"], item["title"]))
    return {"policy_version": POLICY_VERSION, "recommendations": items}
