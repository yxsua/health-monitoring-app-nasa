"""Versioned English screening content and deterministic scoring.

PHQ/GAD instruments are public-domain per their authors' instruction manual.
The package version identifies this application bundle, not a clinical revision.
"""
from copy import deepcopy

VERSION = "en-1.0.0"
RULE_VERSION = "screening-1.0.0"
SOURCE = "https://www.uab.edu/medicine/pcp-sci/images/SCIMS/PHQ-9_Instruction_Manual.pdf"
OPTIONS = [
    {"value": 0, "label": "Not at all"},
    {"value": 1, "label": "Several days"},
    {"value": 2, "label": "More than half the days"},
    {"value": 3, "label": "Nearly every day"},
]
PHQ = [
    "Little interest or pleasure in doing things?",
    "Feeling down, depressed, or hopeless?",
    "Trouble falling or staying asleep, or sleeping too much?",
    "Feeling tired or having little energy?",
    "Poor appetite or overeating?",
    "Feeling bad about yourself—or that you are a failure or have let yourself or your family down?",
    "Trouble concentrating on things, such as reading the newspaper or watching television?",
    "Moving or speaking so slowly that other people could have noticed? Or the opposite—being so fidgety or restless that you have been moving around a lot more than usual?",
    "Thoughts that you would be better off dead or of hurting yourself in some way?",
]
GAD = [
    "Feeling nervous, anxious or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it is hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid as if something awful might happen",
]
SUPPORT = (
    "This answer calls for a follow-up conversation with a qualified support person. "
    "If you feel unsafe, reach out to a nearby trusted crew member now and use your onboard support procedure. "
    "This prototype has not contacted anyone and does not determine immediate danger."
)


def definition(code):
    if code not in ("PHQ9", "GAD7"):
        raise KeyError(code)
    questions = PHQ if code == "PHQ9" else GAD
    bands = [(0, "minimal"), (5, "mild"), (10, "moderate"), (15, "moderately_severe"), (20, "severe")] if code == "PHQ9" else [(0, "minimal"), (5, "mild"), (10, "moderate"), (15, "severe")]
    return {
        "code": code, "version": VERSION, "language": "en",
        "name": "Patient Health Questionnaire-9" if code == "PHQ9" else "Generalized Anxiety Disorder-7",
        "instructions": "Over the last 2 weeks, how often have you been bothered by any of the following:" if code == "PHQ9" else "Over the last 2 weeks, how often have you been bothered by the following problems?",
        "options": deepcopy(OPTIONS),
        "questions": [{"id": f"{code}_Q{i}", "position": i, "text": text} for i, text in enumerate(questions, 1)],
        "maximum_score": len(questions) * 3,
        "scoring_version": RULE_VERSION,
        "bands": [{"minimum": value, "code": label + "_symptom_range"} for value, label in bands],
        "follow_up_question_id": "PHQ9_Q9" if code == "PHQ9" else None,
        "source_url": SOURCE if code == "PHQ9" else "https://aims.uw.edu/sites/default/files/GAD-7_English_0.pdf",
        "scoring_source_url": SOURCE,
        "attribution": "Developed by Robert L. Spitzer, Janet B.W. Williams, Kurt Kroenke and colleagues, with an educational grant from Pfizer Inc.",
        "notice": "Screening score demonstration, not a diagnosis or a validated assessment of astronaut fitness. English scored items only; no translated or generated wording.",
    }


def score(bundle, answers):
    expected = {q["id"] for q in bundle["questions"]}
    if set(answers) != expected or any(type(v) is not int or v not in (0, 1, 2, 3) for v in answers.values()):
        raise ValueError("Complete, valid answers required")
    total = sum(answers.values())
    band = next(b["code"] for b in reversed(bundle["bands"]) if total >= b["minimum"])
    return {"total_score": total, "maximum_score": bundle["maximum_score"],
            "interpretation": band, "scoring_version": bundle["scoring_version"]}
