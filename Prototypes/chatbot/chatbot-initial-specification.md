# **Technical Specification: Hybrid Mental Health Assessment Chatbot**

Based on your choices, I recommend building a **hybrid assessment chatbot for adults**, integrated directly into your React application. It should combine a structured, evidence-based questionnaire with an optional AI conversational assistant, while keeping assessment scoring and safety decisions under deterministic backend control.

The system should support two result destinations:

1. **Personal results:** Users can review their assessment history, scores, and general wellness recommendations.
2. **Professional results:** Users can explicitly authorize sharing their results with a qualified mental health professional through a secure professional interface.

The chatbot should be a wellness and screening tool, not a diagnostic system or a replacement for professional care.

## **1. Project definition**

### **1.1. Main objective**

Develop a hybrid conversational system that guides adult users through structured mental health assessments, calculates results using predefined scoring rules, provides general educational feedback, and optionally allows users to share their results with qualified professionals.

### **1.2. Functional scope**

| Module                   | Responsibility                                                           |
| ------------------------ | ------------------------------------------------------------------------ |
| Conversational interface | Display questions, answers, and conversational responses                 |
| Assessment engine        | Manage questionnaires, question order, and branching                     |
| Scoring engine           | Calculate assessment results using validated rules                       |
| AI assistant             | Explain questions, clarify instructions, and provide general information |
| Safety engine            | Identify responses requiring a safety protocol                           |
| User results             | Display scores, history, and recommendations                             |
| Professional portal      | Allow authorized professionals to review shared assessments              |
| Data management          | Store responses, results, consent, and audit records                     |

### **1.3. Hybrid chatbot behavior**

The chatbot will have two complementary interaction modes.

Mode 1

**Structured assessment**

The primary assessment mechanism.

- Presents predefined questions.
- Uses fixed answer options.
- Follows a controlled question sequence.
- Validates responses.
- Calculates scores through backend rules.

Mode 2

**AI conversational assistant**

An optional supporting mechanism.

- Explains what a question means.
- Clarifies how to select an answer.
- Answers general questions about emotional well-being.
- Explains the meaning and limitations of assessment results.
- Provides general educational resources.

**Important implementation rule:** AI must never modify assessment questions, invent answer options, calculate official scores, change a user's responses, or independently determine whether someone is at immediate risk.

## **2. Recommended technology stack**

I recommend using the existing React ecosystem and a TypeScript backend. This provides control over the assessment logic, data privacy, and integration with the rest of your application.

| Layer            | Recommended technology                          | Purpose                                |
| ---------------- | ----------------------------------------------- | -------------------------------------- |
| Frontend         | React + TypeScript + Vite                       | Main application                       |
| UI               | Tailwind CSS                                    | Chat interface and dashboards          |
| State management | Zustand or React Context                        | Chat and assessment state              |
| Backend          | Node.js + Express + TypeScript                  | API and business logic                 |
| Database         | PostgreSQL                                      | Users, assessments, responses, results |
| ORM              | Prisma                                          | Database access and migrations         |
| AI integration   | Ollama or an API-compatible LLM                 | Optional conversational assistant      |
| Authentication   | JWT with refresh-token strategy                 | User and professional authentication   |
| Deployment       | Docker Compose + Nginx                          | Containerization and reverse proxy     |
| Testing          | Vitest + React Testing Library + Jest/Supertest | Frontend and backend tests             |

This stack also makes it possible to implement the chatbot as a module within your existing React application rather than maintaining a separate chatbot product.

### **Why not use a chatbot builder as the main engine?**

Tools such as Typebot can accelerate conversational interface development, but a custom React implementation gives you more control over assessment state, access permissions, sensitive information, and the professional portal. Typebot's current licensing should also be reviewed before commercial deployment.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://opensaurus.org\&sz=32)

Opensaurus+1



## **3. System architecture**

The proposed architecture separates the user interface, assessment logic, AI functionality, and sensitive data.

**React application**

Chat interface · User dashboard · Professional portal

HTTPS / REST API

**Express API**

**Authentication**

JWT · Roles · Permissions

**Assessment engine**

Questions · Sessions · Branching

**Scoring engine**

Validated scoring rules

**Safety engine**

Safety protocols · Escalation

**AI assistant service**

Contextual explanations · General information

**PostgreSQL database**

Users · Questions · Responses · Results · Consent · Audit logs

**Personal results**

History and feedback

**Professional portal**

Authorized shared results

### **3.1. Main data flow**

1. The user logs into the React application.
2. The user selects a mental health assessment.
3. The system displays the assessment information, limitations, and consent requirements.
4. The backend creates an assessment session.
5. React displays questions and collects answers.
6. The backend validates and stores each response.
7. The scoring engine calculates the result when the assessment is completed.
8. The safety engine evaluates any responses that require additional attention.
9. The results are displayed to the user.
10. The user can authorize sharing with a professional.
11. The professional can access the result through their authorized dashboard.

## **4. Assessment design**

The initial version should use established questionnaires rather than creating an entirely new mental health scale.

### **4.1. Recommended initial questionnaires**

**PHQ-9 — Depression screening**

- 9 questions.
- Evaluates symptoms over the previous two weeks.
- Answer scale: 0–3.
- Total score: 0–27.
- Includes a question concerning thoughts of self-harm or being better off dead.

Reference: University of Washington AIMS Center.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://aims.uw.edu\&sz=32)

AIMS Center+1



[GAD-7 Scoring, Graphing, and Administering Now in BON](https://images.openai.com/static-rsc-4/PSMDhnO7H-8Y9o8_z40LcJYJtd4T8v84-bdX6YDFvG3uyc9Ob8OeGAtlV-39gJ62dkc9EgTcJRqOATcPxL5LikROFFCPyo8EkALxxShP7U_j9c81JMo4whAqk_lSys8apfrvng4TP4xYS5DI3JGFxofiTgp3VAc_qZehfyGTAFA?purpose=inline)

**GAD-7 — Anxiety screening**

- 7 questions.
- Evaluates symptoms over the previous two weeks.
- Answer scale: 0–3.
- Total score: 0–21.

Reference: University of Washington AIMS Center.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://aims.uw.edu\&sz=32)

AIMS Center+1



[WHO (Five) Well-Being Index (1998 version) 1 2 3 4 5 - Cure4you](https://images.openai.com/static-rsc-4/3sWAligz19pCZ2KMu-wiYsJ21-PRogqQ9uolXWi_7oGRO7cFgeCr8_R0NUEZbEnZlbeil5sYWTsEShQN4NRMIFe-Vjlj7XlZmaz3lCZuyVf3ZZ8DJIIAIbZcAygs4j_DYEK5YRzVQn0uhvCldDguVxog9FOGiLNaKaXASO9zebY?purpose=inline)

**WHO-5 — Well-being index**

- 5 questions.
- Evaluates subjective well-being.
- Answer scale: 0–5.
- Raw score: 0–25; can be converted to a 0–100 scale.

Use the official questionnaire and scoring guidance when implementing.

I recommend beginning with PHQ-9 and GAD-7, then incorporating WHO-5 as a complementary well-being assessment. The final instrument versions, Spanish wording, scoring, and interpretation must be reviewed by a qualified professional before deployment.

### **4.2. Assessment configuration**

Each questionnaire should be configurable in the database instead of being hardcoded into React components.

Example:

```
{
  "code": "PHQ9",
  "name": "Patient Health Questionnaire-9",
  "version": "1.0",
  "language": "es-MX",
  "status": "active",
  "questions": [
    {
      "code": "PHQ9_Q1",
      "position": 1,
      "type": "single_choice",
      "required": true,
      "options": [
        { "value": 0, "score": 0 },
        { "value": 1, "score": 1 },
        { "value": 2, "score": 2 },
        { "value": 3, "score": 3 }
      ]
    }
  ]
}
```

This is a simplified structural example, not the complete questionnaire wording.

### **4.3. Scoring implementation**

Scoring must be performed on the backend.

For PHQ-9:

\\[ S\_{\text{PHQ-9}}=\sum\_{i=1}^{9}r_i \\]

Where \\(r_i\\) represents the numeric response to each question.

For GAD-7:

\\[ S\_{\text{GAD-7}}=\sum\_{i=1}^{7}r_i \\]

The backend should also validate that:

- All required questions have responses.
- Every response belongs to a valid option.
- The assessment version is preserved.
- The result is calculated using the scoring rules corresponding to that version.
- Duplicate submissions do not create inconsistent results.

Do not allow the AI model to calculate or change these values.

## **5. Chatbot conversation design**

### **5.1. Conversation workflow**

1. **Welcome**

   The chatbot introduces itself and explains its purpose and limitations.
2. **Consent and eligibility**

   Confirms the user is an adult, explains sensitive data processing, and obtains consent.
3. **Assessment selection**

   The user chooses an available questionnaire.
4. **Instructions**

   Explains the assessment period and answer options.
5. **Questionnaire**

   Presents one question at a time, with fixed answer buttons.
6. **Optional clarification**

   The user can ask the AI assistant for an explanation without changing the assessment.
7. **Completion and scoring**

   The backend validates the responses and calculates the score.
8. **Results**

   Displays the result, limitations, and appropriate next steps.
9. **Sharing**

   The user decides whether to share the assessment with a professional.

### **5.2. Example conversation**

**Wellness assistant**

Demo

Hello! I can guide you through a structured well-being assessment. This tool does not provide a medical diagnosis. Your responses are treated as sensitive information.

I would like to start an assessment.

Great. Which assessment would you like to complete?

**PHQ-9** — Depression symptom screening

**GAD-7** — Anxiety symptom screening

**WHO-5** — General well-being

Example question: During the last two weeks, how often have you experienced the symptom described in this question?

Not at all

Several days

More than half the days

Nearly every day

Illustrative interface only. Production questionnaires must preserve the official wording and response options.

### **5.3. Conversation state management**

The assessment session should have explicit states:

| State             | Description                         |
| ----------------- | ----------------------------------- |
| `created`         | Session created                     |
| `consent_pending` | Awaiting consent                    |
| `in_progress`     | Questions being answered            |
| `paused`          | User temporarily stopped            |
| `completed`       | All required responses submitted    |
| `scored`          | Result calculated                   |
| `shared`          | User authorized professional access |
| `cancelled`       | User ended the assessment           |

The backend should be the source of truth for the current question and session status. React should not independently determine which question is next.

## **6. AI assistant specification**

The AI component should be optional and restricted to a clearly defined set of tasks.

### **6.1. Permitted functionality**

- Explain the purpose of an assessment.
- Clarify instructions.
- Explain the difference between answer options without influencing the response.
- Provide general information about mental health.
- Explain how to interpret a score using approved descriptions.
- Recommend seeking qualified professional support when appropriate.
- Provide approved local resources.

### **6.2. Restricted functionality**

The AI must not:

- Diagnose depression, anxiety, or other conditions.
- Predict suicide risk from conversational text.
- Modify questionnaire responses.
- Generate alternative versions of validated questions during an assessment.
- Tell users to stop prescribed treatment.
- Promise confidentiality beyond the application's actual privacy controls.
- Claim that a professional has been contacted unless that notification was successfully performed.

### **6.3. Suggested AI architecture**

Use a separate AI service rather than mixing language-model logic with the scoring engine.

```
React Chat
    |
    v
Express API
    |
    +---- Assessment Service
    |         |
    |         +---- Question validation
    |         +---- Session management
    |         +---- Score calculation
    |
    +---- AI Assistant Service
              |
              +---- Prompt restrictions
              +---- Approved knowledge base
              +---- LLM provider
              +---- Output validation
```

If using Ollama, the model can run locally in your infrastructure. This may reduce exposure to external AI providers, but local hosting does not automatically guarantee privacy: logs, backups, model prompts, and infrastructure access must also be controlled.

### **6.4. Example system prompt**

```
You are a mental wellness educational assistant.

Your responsibilities:
- Explain assessment instructions.
- Clarify general mental health concepts.
- Provide approved educational information.
- Explain results generated by the backend.

Restrictions:
- Never provide a clinical diagnosis.
- Never calculate or modify assessment scores.
- Never alter validated questionnaire wording.
- Never change a user's recorded answers.
- Never independently determine immediate suicide risk.
- Never recommend stopping prescribed medication.
- Do not claim a professional has been notified unless
  the application confirms successful notification.

If a user expresses immediate danger or self-harm concerns,
follow the application's predefined safety protocol and
provide appropriate emergency resources.
```

The application should also validate the model's output before displaying it. A prompt alone is not an adequate safety control.

## **7. Safety and escalation system**

This is one of the most important components because PHQ-9 includes a question about thoughts of self-harm or being better off dead.

A positive response must trigger a predefined, professionally reviewed follow-up protocol. It should not simply be treated as another point in the score.

### **7.1. Proposed safety workflow**

**User submits an assessment response**

**Backend safety rule evaluation**

No trigger

**Continue assessment**

Proceed according to the questionnaire's rules.

Trigger detected

**Safety protocol**

Display professionally reviewed follow-up guidance.

**Provide appropriate support options**

- Encourage immediate contact with qualified support.
- Display emergency information when appropriate.
- Offer a clear path to contact a professional.
- Follow a defined escalation policy if staffed monitoring exists.

For users in Mexico, the application can include:

- **Línea de la Vida:** 800 911 2000.
- **Emergency services:** 911.

These resources should be verified periodically and presented with appropriate instructions.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.gob.mx\&sz=32)

Gob.mx+2



**Important:** If your application does not have a staffed monitoring service, it must clearly state that responses are not monitored in real time. Do not imply that an alert will be handled by a human.

## **8. Database design**

I recommend a relational database with clear separation between assessment definitions, user responses, results, and professional sharing.

### **8.1. Proposed entities**

| Table                      | Main responsibility                          |
| -------------------------- | -------------------------------------------- |
| `users`                    | Adult user accounts                          |
| `professionals`            | Qualified professional profiles              |
| `professional_credentials` | Credential verification information          |
| `assessments`              | Questionnaire definitions                    |
| `assessment_versions`      | Version and language management              |
| `assessment_questions`     | Question definitions                         |
| `assessment_options`       | Valid response options                       |
| `assessment_sessions`      | Individual assessment attempts               |
| `assessment_responses`     | User answers                                 |
| `assessment_results`       | Calculated results                           |
| `scoring_rules`            | Scoring and interpretation configuration     |
| `assessment_consents`      | Consent records                              |
| `result_shares`            | Professional sharing permissions             |
| `safety_events`            | Safety protocol events                       |
| `audit_logs`               | Sensitive access and administrative activity |
| `ai_conversations`         | Optional assistant interaction records       |

### **8.2. Entity relationship diagram**

\#chatgpt-mermaid-\_r_1ne\_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(237, 237, 237);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-\_r_1ne\_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_1ne\_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_1ne\_ .error-icon{fill:rgb(48, 48, 48);}#chatgpt-mermaid-\_r_1ne\_ .error-text{fill:rgb(237, 237, 237);stroke:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_1ne\_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-\_r_1ne\_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-\_r_1ne\_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-\_r_1ne\_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-\_r_1ne\_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-\_r_1ne\_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-\_r_1ne\_ .marker{fill:rgb(175, 175, 175);stroke:rgb(175, 175, 175);}#chatgpt-mermaid-\_r_1ne\_ .marker.cross{stroke:rgb(175, 175, 175);}#chatgpt-mermaid-\_r_1ne\_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-\_r_1ne\_ p{margin:0;}#chatgpt-mermaid-\_r_1ne\_ .entityBox{fill:rgb(9, 23, 44);stroke:rgb(31, 78, 148);}#chatgpt-mermaid-\_r_1ne\_ .relationshipLabelBox{fill:rgb(48, 48, 48);opacity:0.7;background-color:rgb(48, 48, 48);}#chatgpt-mermaid-\_r_1ne\_ .relationshipLabelBox rect{opacity:0.5;}#chatgpt-mermaid-\_r_1ne\_ .labelBkg{background-color:rgba(48, 48, 48, 0.5);}#chatgpt-mermaid-\_r_1ne\_ .edgeLabel{background-color:rgb(0, 0, 0);}#chatgpt-mermaid-\_r_1ne\_ .edgeLabel .label rect{fill:rgb(0, 0, 0);}#chatgpt-mermaid-\_r_1ne\_ .edgeLabel .label text{fill:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_1ne\_ .edgeLabel .label{fill:rgb(31, 78, 148);font-size:14px;}#chatgpt-mermaid-\_r_1ne\_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_1ne\_ .edge-pattern-dashed{stroke-dasharray:8,8;}#chatgpt-mermaid-\_r_1ne\_ .node rect,#chatgpt-mermaid-\_r_1ne\_ .node circle,#chatgpt-mermaid-\_r_1ne\_ .node ellipse,#chatgpt-mermaid-\_r_1ne\_ .node polygon{fill:rgb(9, 23, 44);stroke:rgb(31, 78, 148);stroke-width:1px;}#chatgpt-mermaid-\_r_1ne\_ .relationshipLine{stroke:rgb(175, 175, 175);stroke-width:1px;fill:none;}#chatgpt-mermaid-\_r_1ne\_ .marker{fill:none!important;stroke:rgb(175, 175, 175)!important;stroke-width:1;}#chatgpt-mermaid-\_r_1ne\_ [data-look=neo].labelBkg{background-color:rgba(48, 48, 48, 0.5);}#chatgpt-mermaid-\_r_1ne\_ .node .neo-node{stroke:rgb(31, 78, 148);}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].node rect,#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].cluster rect,#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-\_r_1ne\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-\_r_1ne\_-gradient);stroke-width:1px;}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].node .neo-line path{stroke:rgb(31, 78, 148);filter:none;}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-\_r_1ne\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-\_r_1ne\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_1ne\_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-\_r_1ne\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_1ne\_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}USERSuuididPKstringemailstringpassword_hashstringstatusASSESSMENT_SESSIONSuuididPKuuiduser_idFKuuidassessment_idFKstringstatusdatetimestarted_atASSESSMENTSuuididPKstringcodestringnameASSESSMENT_VERSIONSuuididPKuuidassessment_idFKstringversionstringlanguageASSESSMENT_QUESTIONSuuididPKuuidversion_idFKstringquestion_codeintpositionASSESSMENT_OPTIONSuuididPKuuidquestion_idFKintscorestringvalueASSESSMENT_RESPONSESuuididPKuuidsession_idFKuuidquestion_idFKuuidoption_idFKASSESSMENT_RESULTSuuididPKuuidsession_idFKinttotal_scorestringinterpretationASSESSMENT_CONSENTSRESULT_SHARESuuididPKuuidresult_idFKuuidprofessional_idFKdatetimeexpires_atPROFESSIONALSuuididPKstringverification_statusSAFETY_EVENTSAUDIT_LOGScreateshascontainsoffersrecordsanswersproducesrecordsauthorizesreceivesshared_asgeneratesperforms

### **8.3. Important database considerations**

- Use UUIDs for externally exposed record identifiers.
- Preserve questionnaire and scoring versions.
- Store the exact consent version and timestamp.
- Avoid storing unnecessary conversational content.
- Encrypt sensitive information at rest and in transit.
- Separate professional permissions from ordinary user permissions.
- Record every professional access to a shared assessment.
- Implement data retention and deletion policies.
- Do not expose database identifiers or sensitive responses in application logs.

## **9. API specification**

The React application should communicate with the backend through REST endpoints.

Suggested API prefix:

`/api/v1`

### **9.1. Assessment endpoints**

| Method | Endpoint                             | Purpose                    |
| ------ | ------------------------------------ | -------------------------- |
| GET    | `/assessments`                       | List available assessments |
| GET    | `/assessments/:id`                   | Get assessment details     |
| POST   | `/assessment-sessions`               | Start a session            |
| GET    | `/assessment-sessions/:id`           | Retrieve session state     |
| POST   | `/assessment-sessions/:id/consent`   | Record consent             |
| POST   | `/assessment-sessions/:id/responses` | Submit an answer           |
| POST   | `/assessment-sessions/:id/pause`     | Pause session              |
| POST   | `/assessment-sessions/:id/complete`  | Complete assessment        |
| GET    | `/assessment-sessions/:id/result`    | Retrieve calculated result |

### **9.2. AI endpoints**

| Method | Endpoint                       | Purpose                                      |
| ------ | ------------------------------ | -------------------------------------------- |
| POST   | `/assistant/messages`          | Send a question to the assistant             |
| GET    | `/assistant/conversations/:id` | Retrieve an allowed conversation             |
| DELETE | `/assistant/conversations/:id` | Delete conversation data according to policy |

The AI endpoint should receive only the minimum context needed to answer. It should not automatically receive all assessment responses or the user's entire history.

### **9.3. Professional endpoints**

| Method | Endpoint                           | Purpose                                   |
| ------ | ---------------------------------- | ----------------------------------------- |
| GET    | `/professional/shared-results`     | List results shared with the professional |
| GET    | `/professional/shared-results/:id` | Retrieve an authorized result             |
| POST   | `/results/:id/share`               | Authorize sharing                         |
| DELETE | `/results/:id/share/:shareId`      | Revoke sharing                            |

The backend must verify the ownership of the assessment, the user's sharing permission, and the professional's authorization for every relevant request.

### **9.4. Example response**

```
{
  "session_id": "uuid",
  "assessment": "PHQ9",
  "status": "completed",
  "result": {
    "total_score": 12,
    "maximum_score": 27,
    "interpretation": "moderate_symptom_range",
    "scoring_version": "1.0"
  },
  "sharing": {
    "authorized": false
  }
}
```

This is an illustrative API structure. The interpretation must be generated from an approved scoring configuration and must not be presented as a diagnosis.

## **10. Results and professional portal**

Because you selected both private and professional results, the system should have two separate interfaces with different permissions.

### **10.1. Personal results dashboard**

The user should be able to:

- View completed assessments.
- Review scores and assessment dates.
- Compare results over time.
- Read general explanations.
- Download a report, if enabled.
- Decide whether to share a result.
- Revoke existing sharing permissions.
- Request deletion according to the applicable data policy.

Example dashboard:

**My mental well-being**

Illustrative dashboard with fictional data

PHQ-9

# **12/27**

Example range

GAD-7

# **8/21**

Example range

**Assessment history**

Illustrative scores only; not actual user data.

PHQ-9GAD-7

810121416SepOctNov

Trend charts should only compare compatible versions of the same instrument. They should not imply a diagnosis or treatment outcome.

**Sharing permissions**

**Professional access**

No professional currently authorized

Private

### **10.2. Professional dashboard**

Professionals should have access to:

- A list of users who explicitly shared results with them.
- Assessment dates and instrument versions.
- Scores and individual responses, if specifically authorized.
- Previous shared assessments.
- Relevant safety events, according to the consent and approved workflow.
- A report view for professional review.

A professional account must be verified before receiving access. The application should not assume that a person is qualified merely because they register as a professional.

### **10.3. Sharing authorization**

Sharing must be explicit, granular, and revocable.

A suitable flow is:

1. User selects "Share with a professional."
2. User selects or identifies the intended professional.
3. The system explains exactly what information will be shared.
4. User confirms authorization.
5. Backend creates a sharing permission.
6. Professional receives access to the authorized report.
7. User can revoke access later.

The system should also define what happens to previously downloaded reports after access is revoked; revocation cannot retrieve files already downloaded.

## **11. Security and privacy requirements**

Mental health assessment information is sensitive personal data. The application should be designed around privacy by default.

| Requirement               | Implementation                                     |
| ------------------------- | -------------------------------------------------- |
| Authentication            | Secure session and token management                |
| Authorization             | Role-based and resource-level access               |
| Encryption                | TLS in transit and encryption at rest              |
| Passwords                 | Argon2id or bcrypt                                 |
| Consent                   | Explicit, versioned, timestamped consent           |
| Sharing                   | Separate authorization records                     |
| Audit                     | Record access to sensitive records                 |
| Data minimization         | Only collect information necessary for the feature |
| Retention                 | Define retention and deletion schedules            |
| Backups                   | Encrypt backups and restrict access                |
| AI privacy                | Avoid unnecessary transmission of personal data    |
| Professional verification | Verify credentials and authorization               |

For Mexico, review the applicable requirements of the *Ley Federal de Protección de Datos Personales en Posesión de los Particulares* and any relevant regulations, especially regarding sensitive personal data, consent, privacy notices, and data-subject rights.

I would also recommend completing a privacy impact assessment before piloting the application with real users.

# **12. Implementation plan**

I recommend developing the system incrementally. The first milestone should be a functional questionnaire with reliable scoring and safety handling. AI and professional sharing should be added after the core assessment mechanism is validated.



Recommended sequence

**8–10 weeks for an initial controlled prototype**, assuming the questionnaire wording, scoring rules, safety protocol, and professional review are available without major delays.



| Phase                                 | Duration  | Main deliverable                                  |
| ------------------------------------- | --------- | ------------------------------------------------- |
| 1. Requirements and assessment design | 1 week    | Functional specification and approved instruments |
| 2. Database and backend foundation    | 1–2 weeks | API, authentication, schema, sessions             |
| 3. React chatbot                      | 1–2 weeks | Interactive assessment interface                  |
| 4. Scoring and safety engine          | 1 week    | Deterministic calculations and safety workflows   |
| 5. AI assistant                       | 1 week    | Restricted conversational functionality           |
| 6. Results and professional portal    | 1–2 weeks | Dashboards and sharing permissions                |
| 7. Testing and controlled pilot       | 1 week    | Validated prototype and pilot report              |

## **Phase 1 — Requirements and assessment design**

**Tasks:**

- Define the supported adult age range.
- Select initial assessment instruments.
- Confirm Spanish questionnaire versions and scoring rules.
- Define consent and privacy notices.
- Define the safety protocol with a qualified professional.
- Define professional roles and credential verification.
- Define what information can be shared.

**Deliverable:** Approved functional and assessment specification.

## **Phase 2 — Backend and database**

**Tasks:**

- Configure Express, TypeScript, Prisma, and PostgreSQL.
- Implement authentication and roles.
- Create database migrations.
- Implement assessment configuration.
- Implement session creation and state management.
- Implement response validation.
- Add audit logging.

**Deliverable:** Functional assessment API.

## **Phase 3 — React chatbot**

**Tasks:**

- Create reusable chat components.
- Implement message bubbles and answer buttons.
- Add assessment progress.
- Implement pause and resume.
- Add consent screens.
- Connect the React interface to the API.
- Implement error handling and session recovery.

**Deliverable:** Fully interactive structured chatbot.

## **Phase 4 — Scoring and safety engine**

**Tasks:**

- Implement PHQ-9 and GAD-7 scoring.
- Validate calculations with test cases.
- Store scoring versions.
- Implement safety rules.
- Add safety resource screens.
- Test incomplete and invalid responses.

**Deliverable:** Validated scoring and safety module.

## **Phase 5 — AI assistant**

**Tasks:**

- Deploy Ollama or configure an approved model provider.
- Implement the assistant service.
- Create restricted prompts.
- Build an approved knowledge base.
- Add output validation.
- Test attempts to manipulate scoring or questionnaire wording.
- Ensure sensitive information is not unnecessarily passed to the model.

**Deliverable:** Hybrid conversational assistant.

## **Phase 6 — Results and professional portal**

**Tasks:**

- Build personal results dashboard.
- Add assessment history.
- Implement sharing authorization.
- Implement professional account verification.
- Build professional result views.
- Implement access revocation.
- Add audit records for professional access.

**Deliverable:** Complete results-sharing workflow.

## **Phase 7 — Testing and pilot**

**Tasks:**

- Unit-test scoring calculations.
- Integration-test API endpoints.
- Test authentication and authorization.
- Test safety scenarios with professional oversight.
- Test data isolation between users.
- Test AI behavior and limitations.
- Run a small controlled pilot with informed adult participants.

**Deliverable:** Pilot-ready prototype and technical documentation.

## **13. Testing strategy and acceptance criteria**

The following criteria should be used to determine whether the prototype is ready for a controlled pilot.

| Area               | Acceptance criterion                                                  |
| ------------------ | --------------------------------------------------------------------- |
| Assessment         | Questions and answer options match the approved instrument version    |
| Scoring            | Backend scores match independently verified test cases                |
| Validation         | Invalid and incomplete answers cannot produce a completed score       |
| Session management | Users can resume eligible paused sessions                             |
| AI                 | Cannot change official scores or assessment responses                 |
| Safety             | Professionally approved triggers display the correct protocol         |
| Privacy            | Users cannot access another user's records                            |
| Sharing            | Professionals cannot access results without explicit authorization    |
| Revocation         | Revoked permissions block subsequent access                           |
| Audit              | Sensitive access is recorded                                          |
| Accessibility      | Chatbot is usable with keyboard navigation and assistive technologies |

### **Essential test scenarios**

1. User completes PHQ-9 with all answers equal to zero.
2. User submits the maximum valid score.
3. User attempts to submit an invalid answer.
4. User leaves the questionnaire halfway through and resumes.
5. User gives a positive response to the self-harm-related item.
6. User asks the AI to diagnose them.
7. User asks the AI to change a previous response.
8. User attempts to access another user's assessment.
9. User shares a result with a professional.
10. User revokes sharing permissions.
11. Professional attempts to access an unshared result.
12. Professional attempts to access a result after revocation.

## **14. Suggested project structure**

A modular monolith is sufficient for the first version. You do not need microservices at this stage.

```
mental-health-platform/
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── chatbot/
│       │   ├── assessments/
│       │   ├── results/
│       │   └── shared/
│       │
│       ├── pages/
│       │   ├── user/
│       │   ├── professional/
│       │   └── assessments/
│       │
│       ├── services/
│       ├── hooks/
│       ├── store/
│       └── types/
│
├── backend/
│   └── src/
│       ├── modules/
│       │   ├── auth/
│       │   ├── users/
│       │   ├── professionals/
│       │   ├── assessments/
│       │   ├── scoring/
│       │   ├── safety/
│       │   ├── assistant/
│       │   ├── results/
│       │   └── sharing/
│       │
│       ├── middleware/
│       ├── config/
│       ├── database/
│       └── utils/
│
├── database/
│   ├── migrations/
│   └── seeds/
│
├── infrastructure/
│   ├── docker/
│   └── nginx/
│
└── documentation/
    ├── architecture/
    ├── api/
    ├── assessments/
    └── privacy/
```

# **15. Recommended MVP scope**

To avoid making the first version unnecessarily complex, I would divide the project into three releases.

**Release 1 — Core assessment**

First priority

- Adult user authentication.
- Consent and privacy notice.
- PHQ-9 and GAD-7.
- Structured React chatbot.
- Backend scoring.
- Basic safety protocol.
- Personal results dashboard.

**Release 2 — Hybrid AI**

- Optional AI assistant.
- Educational knowledge base.
- Question clarification.
- General result explanations.
- AI output validation.

**Release 3 — Professional integration**

- Verified professional accounts.
- Professional dashboard.
- Explicit result sharing.
- Permission revocation.
- Audit logs.
- Downloadable assessment reports.

## **16. Final recommendations**

My recommendation is to implement the assessment as a **custom React conversational interface backed by a deterministic Express assessment engine**, with AI isolated as a supporting service.

The most important architectural decisions are:

1. Keep questionnaire definitions and scoring rules in the backend.
2. Preserve instrument versions to ensure historical results remain interpretable.
3. Make the AI assistant optional and strictly non-diagnostic.
4. Treat safety handling as a separate, professionally reviewed subsystem.
5. Keep personal results private by default.
6. Require explicit authorization before sharing anything with professionals.
7. Build the professional portal only after access control and credential verification are established.

This approach provides a practical foundation for a prototype while allowing you to extend the platform later with additional assessments, wearable data, progress indicators, and other wellness features.

## **17. Proposed next development milestone**

The most useful next step is to define the first release in enough detail that implementation can begin without ambiguity.

I recommend starting with a technical backlog containing:

- Database SQL schema and Prisma models.
- Express API contracts and service responsibilities.
- React chatbot component specifications.
- PHQ-9 and GAD-7 configuration structure.
- Scoring test cases.
- Safety protocol requirements.
- Authentication and access-control rules.

This will turn the specification into a concrete development blueprint. I can also help review implementation progress next week.

🧠Review chatbot implementation progress next weekTap to set up