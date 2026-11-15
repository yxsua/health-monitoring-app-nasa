# Recommendation engine

This directory contains the deterministic recommendation evaluator imported by `chatbot_app`. It is a Python library, not a standalone API or Compose service. The chatbot calls it from its authenticated `POST /api/v1/chatbot/recommendations/evaluate` endpoint.

## Inputs and outputs

`engine.evaluate(profile, dashboard=None, topics=())` accepts:

- The signed-in astronaut's latest structured assessment and mood/sleep check-in summary.
- Optional simulator analysis supplied as a separate dashboard object.
- A list of conversation topics that the user explicitly chose to share. Transcript text is not accepted.

It returns a policy version and an ordered list of recommendations with a stable ID, priority, title, action, rationale, source scope, source references, timestamp and evidence. The scopes distinguish `astronaut_profile`, `simulated_fixture`, and `user_confirmed_context`; the library does not join synthetic fixture readings to a profile. The evaluator does not persist recommendation history.

## Policy behavior

- Structured assessment follow-up flags and non-minimal assessment bands can produce an informational support prompt.
- The configured self-check-in trend state can suggest a further check-in.
- Simulator rule alerts, available Isolation Forest anomalies and available LSTM projections can produce separate review prompts.
- Only allowlisted, explicitly shared topics are converted into general support guidance.
- Results are sorted by priority; IDs are deterministic for a given policy and source reference.

The evaluator is rule-based and has no external API, model download, database or package dependency. It is not clinical decision support. Recommendations do not diagnose, establish safety, contact a professional, or replace onboard procedures. Simulator rule thresholds and model results are demonstration outputs.

## Integration and development

The chatbot Dockerfile copies this package into its image. There is no separate port, service command, database, or environment file for this library. To change the public API, update the chatbot request/response schemas and contract documentation alongside the engine, then rebuild the chatbot:

```sh
docker compose up -d --build chatbot
```

From the repository root, the chatbot's developer requirements and tests are documented in [the chatbot README](../chatbot_app/README.md). Do not expose the engine directly to an unauthenticated frontend; invoke it through the chatbot's authenticated endpoint.
