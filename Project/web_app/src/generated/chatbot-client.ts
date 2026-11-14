import type { Definition, Start, Session, Result, Answer, Message, AssistantReply, RiskSummary } from './chatbot-types';

export class ChatbotError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

/** No automatic mutation retries. Retain creation/completion keys until acknowledged. */
export function createChatbotClient(baseUrl: string, getToken: () => string | null) {
  const root = baseUrl.replace(/\/$/, '') + '/api/v1/chatbot';
  async function request<T>(path: string, method = 'GET', body?: unknown, key?: string): Promise<T> {
    const token = getToken();
    if (!token) throw new ChatbotError(401, 'unauthorized', 'Log in first.');
    const response = await fetch(root + path, {
      method,
      cache: 'no-store',
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(key ? { 'Idempotency-Key': key } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      if (response.status === 401) window.dispatchEvent(new CustomEvent('auth:expired'));
      throw new ChatbotError(response.status, payload.error?.code ?? 'http_error', payload.error?.message ?? 'Chatbot request failed.');
    }
    return payload as T;
  }
  const id = encodeURIComponent;
  return {
    assessments: () => request<Definition[]>('/assessments'),
    sessions: () => request<Session[]>('/sessions'),
    createSession: (body: Start, key: string) => request<Session>('/sessions', 'POST', body, key),
    session: (sessionId: string) => request<Session>(`/sessions/${id(sessionId)}`),
    answer: (sessionId: string, questionId: string, body: Answer) => request<Session>(`/sessions/${id(sessionId)}/responses/${id(questionId)}`, 'PUT', body),
    transition: (sessionId: string, action: 'pause' | 'resume' | 'cancel', expectedRevision: number) => request<Session>(`/sessions/${id(sessionId)}/${action}`, 'POST', { expected_revision: expectedRevision }),
    complete: (sessionId: string, expectedRevision: number, key: string) => request<Result>(`/sessions/${id(sessionId)}/complete`, 'POST', { expected_revision: expectedRevision }, key),
    result: (sessionId: string) => request<Result>(`/sessions/${id(sessionId)}/result`),
    results: () => request<Result[]>('/results'),
    assistant: (body: Message) => request<AssistantReply>('/assistant/messages', 'POST', body),
    riskSummary: (astronautId: string) => request<RiskSummary>(`/astronauts/${id(astronautId)}/risk-summary`),
  };
}
