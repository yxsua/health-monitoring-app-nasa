from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


MetricField = Literal[
    "heart_rate", "systolic_pressure", "diastolic_pressure", "spo2", "body_temperature",
    "glucose", "hrv_rmssd", "sleep_duration", "mood", "exercise_duration",
    "radiation_dose_rate", "co2", "cabin_temperature", "humidity", "noise",
    "cabin_pressure", "gravity", "earth_latency", "simulated_daylight_duration",
    "social_interaction_duration",
]
SourceScope = Literal["account_profile", "simulated_fixture", "user_entered"]
OutboxStatus = Literal["queued", "deferred", "transmitting", "sent", "cancelled", "failed"]


class MetricSnapshot(Input):
    field: MetricField
    value: float | None
    unit: str = Field(min_length=1, max_length=24)
    quality: Literal["valid", "missing", "invalid"]
    observed_at: datetime
    source_ref: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        return value.astimezone(timezone.utc)


class AlertSnapshot(Input):
    alert_id: str = Field(min_length=1, max_length=100)
    severity: Literal["caution", "warning", "critical"]
    system: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=300)
    observed_at: datetime
    source_ref: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        return value.astimezone(timezone.utc)


class ProfileContext(Input):
    """Explicit per-message profile selection. DOB and emergency contact are not exportable."""
    age_years: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = Field(default=None, max_length=80)
    pronouns: str | None = Field(default=None, max_length=80)
    blood_type: Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] | None = None
    allergies: str | None = Field(default=None, max_length=1000)
    medical_conditions: str | None = Field(default=None, max_length=1000)
    medications: str | None = Field(default=None, max_length=1000)

    @field_validator("gender", "pronouns", "allergies", "medical_conditions", "medications")
    @classmethod
    def clean_optional_text(cls, value):
        return value or None

    @model_validator(mode="after")
    def require_selected_values(self):
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("Select at least one profile field to share")
        return self


class MessageContent(Input):
    kind: Literal["text_update", "professional_help", "additional_help"]
    help_type: Literal["medical", "mental_health", "technical", "other"] | None = None
    text: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_help_type(self):
        if self.kind == "professional_help" and self.help_type is None:
            raise ValueError("Choose the type of professional help requested")
        if self.kind != "professional_help" and self.help_type is not None:
            raise ValueError("help_type is only valid for professional_help messages")
        return self


class PacketData(Input):
    mission: str | None = Field(default=None, min_length=1, max_length=100)
    metrics: list[MetricSnapshot] = Field(default_factory=list, max_length=20)
    alerts: list[AlertSnapshot] = Field(default_factory=list, max_length=40)
    profile_context: ProfileContext | None = None
    message: MessageContent | None = None

    @model_validator(mode="after")
    def require_content_and_unique_metrics(self):
        if not self.metrics and not self.alerts and self.profile_context is None and self.message is None:
            raise ValueError("Select at least one metric, alert, profile field, or message")
        metric_fields = [item.field for item in self.metrics]
        if len(metric_fields) != len(set(metric_fields)):
            raise ValueError("Each metric field may appear only once")
        alert_ids = [item.alert_id for item in self.alerts]
        if len(alert_ids) != len(set(alert_ids)):
            raise ValueError("Each alert may appear only once")
        return self


class CreatePacket(Input):
    contract_version: Literal["1.1.0"]
    consent: Literal[True]
    source_scope: SourceScope
    data: PacketData

    @model_validator(mode="after")
    def keep_sources_separate(self):
        if self.source_scope == "simulated_fixture" and self.data.profile_context is not None:
            raise ValueError("Simulated fixture data cannot be combined with account profile data")
        if self.data.profile_context is not None and self.source_scope != "account_profile":
            raise ValueError("Profile context requires account_profile source scope")
        if self.data.message is not None and self.source_scope != "user_entered":
            raise ValueError("Text updates and help requests require user_entered source scope")
        return self


class CancelPacket(Input):
    expected_revision: int = Field(ge=0, strict=True)


class PacketEvent(BaseModel):
    event_id: int
    event_type: Literal["queued", "deferred", "transmission_started", "resumed", "sent", "received", "cancelled", "failed"]
    created_at: str
    detail: dict[str, str]


class OutboxPacket(BaseModel):
    message_id: str
    contract_version: Literal["1.0.0", "1.1.0"]
    source_scope: SourceScope
    provenance_status: Literal["user_declared"]
    data: PacketData
    selected_fields: list[str]
    status: OutboxStatus
    revision: int
    payload_bytes: int
    bytes_sent: int
    attempt_count: int
    last_attempt_at: str | None
    created_at: str
    updated_at: str
    sent_at: str | None
    earth_received_at: str | None


class OutboxDetail(BaseModel):
    message: OutboxPacket
    events: list[PacketEvent]


class MissionControlStatus(BaseModel):
    contract_version: Literal["1.1.0"]
    service_state: Literal["ready"]
    transport_state: Literal["simulated"]
    link_state: Literal["open", "closed"]
    current_window_ends_at: str | None
    next_contact_at: str
    window_duration_seconds: int
    window_capacity_bytes: int
    transfer_rate_bytes_per_second: int
    queued_count: int
    deferred_count: int
    transmitting_count: int
    sent_count: int
    cancelled_count: int
    failed_count: int
    retention_days: int
    last_sent_at: str | None


class ContactWindow(BaseModel):
    window_id: str
    starts_at: str
    ends_at: str
    state: Literal["open", "upcoming"]
    capacity_bytes: int
    bytes_used: int


class ContactWindowList(BaseModel):
    simulated: Literal[True]
    windows: list[ContactWindow]


class EarthReceivedMessage(BaseModel):
    message: OutboxPacket
    received_at: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
