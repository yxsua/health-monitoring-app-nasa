from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Start(Input):
    assessment_code: Literal["PHQ9", "GAD7"]
    assessment_version: str


class Revision(Input):
    expected_revision: int = Field(ge=0, strict=True)


class Answer(Revision):
    value: int = Field(ge=0, le=3, strict=True)


class CheckInWrite(Input):
    expected_revision: int = Field(ge=0, strict=True)
    mood_score: int = Field(ge=1, le=5, strict=True)
    sleep_duration_hours: float = Field(ge=0, le=24, allow_inf_nan=False)


class Message(Input):
    session_id: str
    intent: Literal["instructions", "question", "result", "support"]
    question_id: str | None = None


class Question(BaseModel):
    id: str
    position: int
    text: str


class Option(BaseModel):
    value: int
    label: str


class Band(BaseModel):
    minimum: int
    code: str


class Definition(BaseModel):
    code: str
    version: str
    language: str
    name: str
    instructions: str
    options: list[Option]
    questions: list[Question]
    maximum_score: int
    scoring_version: str
    bands: list[Band]
    follow_up_question_id: str | None
    source_url: str
    scoring_source_url: str
    attribution: str
    notice: str


class FollowUp(BaseModel):
    status: Literal["unknown", "not_triggered", "follow_up_requested"]
    guidance: str | None
    # No probability, diagnosis, or claim of notification.


class Session(BaseModel):
    session_id: str
    astronaut_id: str
    assessment: Definition
    status: Literal["in_progress", "paused", "cancelled", "scored"]
    revision: int
    responses: dict[str, int]
    current_question: Question | None
    follow_up: FollowUp
    created_at: str
    updated_at: str


class Result(BaseModel):
    result_id: str
    session_id: str
    assessment_code: str
    assessment_version: str
    total_score: int
    maximum_score: int
    interpretation: str
    scoring_version: str
    completed_at: str
    notice: str


class RiskSummary(BaseModel):
    schema_version: Literal["1.0.0"]
    summary_id: str
    revision: int
    astronaut_id: str
    availability: Literal["available", "not_assessed", "stale"]
    observed_at: str | None
    updated_at: str | None
    assessment_summaries: list[Result]
    follow_up: FollowUp
    rule_version: str


class CheckIn(BaseModel):
    check_in_date: date
    revision: int
    mood_score: int
    sleep_duration_hours: float
    created_at: str
    updated_at: str


class TodayCheckIn(BaseModel):
    check_in_date: date
    check_in: CheckIn | None


class CheckInTrend(BaseModel):
    policy_version: str
    status: Literal["insufficient_data", "no_pattern", "check_in_suggested"]
    evaluated_at: str
    baseline_days: int
    recent_days: int
    baseline_mood_mean: float | None
    recent_mood_mean: float | None
    baseline_sleep_mean_hours: float | None
    recent_sleep_mean_hours: float | None
    message: str


class ConversationTurn(Input):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class ConversationRequest(Input):
    consent: Literal[True]
    messages: list[ConversationTurn] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def ordered_turns_end_with_user(self):
        if self.messages[0].role != "user":
            raise ValueError("A conversation must start with a user turn")
        if self.messages[-1].role != "user":
            raise ValueError("The final conversation turn must be from the user")
        if any(left.role == right.role for left, right in zip(self.messages, self.messages[1:])):
            raise ValueError("Conversation roles must alternate")
        return self


class AssistantReply(BaseModel):
    mode: Literal["static"]
    model_available: Literal[False]
    text: str
    follow_up: FollowUp


class AssistantStatus(BaseModel):
    conversation_enabled: bool
    model_configured: bool
    language: Literal["en", "es"]
    response_timeout_seconds: int


class ConversationReply(BaseModel):
    mode: Literal["local_model"]
    model_available: Literal[True]
    text: str = Field(min_length=1, max_length=4000)


class RecommendationEvidence(Input):
    field: str = Field(min_length=1, max_length=80)
    value: float | None
    unit: str = Field(max_length=32)
    quality: Literal["valid", "missing", "invalid"]


class DashboardAlert(Input):
    code: str = Field(min_length=1, max_length=80)
    severity: Literal["caution", "warning", "critical"]
    system: str = Field(max_length=80)
    message: str = Field(max_length=500)
    evidence: list[RecommendationEvidence] = Field(max_length=20)


class DashboardRules(Input):
    status: Literal["available", "warming_up", "insufficient_data", "unavailable"]
    alerts: list[DashboardAlert] = Field(max_length=40)


class DashboardModel(Input):
    status: Literal["available", "warming_up", "insufficient_data", "unavailable"]
    is_anomaly: bool | None = None
    model_version: str | None = Field(default=None, max_length=80)


class DashboardForecast(DashboardModel):
    target_time: str | None = None


class DashboardContext(Input):
    run_id: str = Field(min_length=1, max_length=100)
    scenario_id: Literal["normal", "solar_event", "high_co2", "prolonged_isolation"]
    source_subject_id: Literal["A01", "AST-001"]
    record_id: str = Field(min_length=1, max_length=100)
    observed_at: str
    rules: DashboardRules
    anomaly: DashboardModel
    forecast: DashboardForecast


class ConversationContext(Input):
    consent: Literal[True]
    topics: list[Literal["sleep_rest", "stress_support", "exercise_recovery", "cabin_conditions", "human_support"]] = Field(min_length=1, max_length=5)


class RecommendationRequest(Input):
    dashboard: DashboardContext | None = None
    conversation: ConversationContext | None = None


class Recommendation(Input):
    recommendation_id: str
    priority: Literal["routine", "caution", "warning", "critical"]
    title: str
    action: str
    rationale: str
    source_scope: Literal["astronaut_profile", "simulated_fixture", "user_confirmed_context", "app_usage"]
    source_refs: list[str]
    observed_at: str | None
    evidence: list[RecommendationEvidence]


class RecommendationResponse(BaseModel):
    policy_version: str
    evaluated_at: str
    recommendations: list[Recommendation]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
