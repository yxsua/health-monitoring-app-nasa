from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Start(Input):
    assessment_code: Literal["PHQ9", "GAD7"]
    assessment_version: str


class Revision(Input):
    expected_revision: int = Field(ge=0, strict=True)


class Answer(Revision):
    value: int = Field(ge=0, le=3, strict=True)


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


class AssistantReply(BaseModel):
    mode: Literal["static"]
    model_available: Literal[False]
    text: str
    follow_up: FollowUp


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
