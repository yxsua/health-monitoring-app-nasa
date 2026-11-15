import { useEffect, useState, type FormEvent } from 'react';
import { createChatbotClient } from '../../generated/chatbot-client';
import type { AssistantStatus, ConversationTurn } from '../../generated/chatbot-types';
import { useAuth } from '../auth/AuthContext';

export function LocalConversation() {
  const { token, profile } = useAuth();
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [consent, setConsent] = useState(false);
  const [started, setStarted] = useState(false);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [shareTopics, setShareTopics] = useState(false);
  const [topics, setTopics] = useState<string[]>([]);

  const topicChoices = [
    ['sleep_rest', 'Sleep and rest'], ['stress_support', 'Stress support'],
    ['exercise_recovery', 'Exercise and recovery'], ['cabin_conditions', 'Cabin conditions'],
    ['human_support', 'Human support'],
  ] as const;

  useEffect(() => {
    if (!profile) return;
    try {
      const shared = JSON.parse(window.sessionStorage.getItem(`astrahealth-shared-topics:${profile.astronaut_id}`) ?? 'null') as { consent?: boolean; topics?: string[] } | null;
      if (shared?.consent && Array.isArray(shared.topics)) { setShareTopics(true); setTopics(shared.topics); }
    } catch { /* Optional local preference; conversation remains available. */ }
  }, [profile]);

  function updateSharedTopics(enabled: boolean, selected = topics) {
    setShareTopics(enabled);
    if (!profile) return;
    const key = `astrahealth-shared-topics:${profile.astronaut_id}`;
    try {
      if (!enabled || selected.length === 0) {
        window.sessionStorage.removeItem(key);
        return;
      }
      window.sessionStorage.setItem(key, JSON.stringify({ consent: true, topics: selected }));
    } catch { /* Keep the optional sharing control usable when browser storage is blocked. */ }
  }

  function toggleTopic(topic: string) {
    const next = topics.includes(topic) ? topics.filter(item => item !== topic) : [...topics, topic];
    setTopics(next);
    if (next.length) updateSharedTopics(shareTopics, next);
    else updateSharedTopics(false, []);
  }

  useEffect(() => {
    if (!token) return;
    let active = true;
    createChatbotClient('', () => token).assistantStatus()
      .then(current => { if (active) setStatus(current); })
      .catch(() => { if (active) setStatus({ conversation_enabled: false, model_configured: false, language: 'en', response_timeout_seconds: 45 }); });
    return () => { active = false; };
  }, [token]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!token || !consent || !started || !status?.conversation_enabled || busy || !content) return;
    const next = [...turns, { role: 'user' as const, content }];
    if (next.length > 12) next.splice(0, next.length - 11);
    setTurns(next); setDraft(''); setBusy(true); setError('');
    try {
      const response = await createChatbotClient('', () => token).conversation({ consent: true, messages: next });
      setTurns([...next, { role: 'assistant', content: response.text }]);
    } catch (reason) {
      setTurns(turns);
      setDraft(content);
      setError(reason instanceof Error ? reason.message : 'The local assistant could not reply.');
    } finally { setBusy(false); }
  }

  function endConversation() {
    setTurns([]); setDraft(''); setConsent(false); setStarted(false); setError('');
  }

  const languageName = status?.language === 'es' ? 'Spanish' : 'English';
  const statusLabel = !status ? 'Checking model' : status.conversation_enabled ? 'Local model enabled' : status.model_configured ? 'Disabled by policy' : 'Model unavailable';

  return <section className="section-block" aria-labelledby="conversation-title">
    <div className="section-title"><div><p className="eyebrow">OPTIONAL · LOCAL MODEL</p><h2 id="conversation-title">Conversation support</h2></div><span className={`status-pill ${status?.conversation_enabled ? 'status-pill--active' : 'status-pill--neutral'}`}>{statusLabel}</span></div>
    <div className="panel local-chat-panel">
      <p className="muted">An opt-in conversation for reflection. It does not read assessment answers or check-in history, and the chatbot service does not save messages. The configured model host may have its own logging or retention settings.</p>
      {!status?.conversation_enabled && <p className="notice notice--subtle" role="status">{status?.model_configured ? 'A local model is configured, but conversation remains disabled by operator policy.' : 'No local model is configured.'} Structured check-ins and assessment support remain available.</p>}
      <div className="conversation-sharing"><label className="local-chat-consent"><input type="checkbox" checked={shareTopics} onChange={event => updateSharedTopics(event.target.checked)} /><span>Share selected topics with dashboard recommendations. Message text is never shared.</span></label>{shareTopics && <div className="conversation-topics">{topicChoices.map(([id, label]) => <label key={id}><input type="checkbox" checked={topics.includes(id)} onChange={() => toggleTopic(id)} />{label}</label>)}</div>}</div>
      {!started ? <div className="local-chat-optin"><label className="local-chat-consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} disabled={!status?.conversation_enabled} /><span>I agree to send my messages to the configured local model for this conversation.</span></label><button className="button button--primary" type="button" disabled={!consent || !status?.conversation_enabled} onClick={() => { setStarted(true); setError(''); }}>Start conversation</button></div> : <>
        <div className="local-chat-thread" aria-live="polite" aria-label="Conversation messages">{turns.map((turn, index) => <article className={`local-chat-message local-chat-message--${turn.role}`} key={`${index}-${turn.role}`}><span>{turn.role === 'user' ? 'You' : 'Local assistant'}</span><p>{turn.content}</p></article>)}{busy && <p className="muted" role="status">Waiting for the local model…</p>}</div>
        <form className="local-chat-form" onSubmit={send}><label htmlFor="local-chat-message">Your message <span className="muted">{languageName} replies · up to {status?.response_timeout_seconds ?? 45} seconds</span></label><textarea id="local-chat-message" rows={3} maxLength={1200} value={draft} onChange={event => setDraft(event.target.value)} placeholder="What would you like to reflect on?" disabled={busy} required /><div className="local-chat-actions"><span className="muted">{draft.length}/1200</span><div><button className="button button--secondary" type="button" onClick={endConversation} disabled={busy}>End and clear</button><button className="button button--primary" type="submit" disabled={busy || !draft.trim()}>{busy ? 'Sending…' : 'Send message'}</button></div></div></form>
        {error && <p className="notice notice--error" role="alert">{error}</p>}
      </>}
      <p className="local-chat-support">This assistant cannot diagnose or contact anyone. If you feel unsafe, reach out to a nearby trusted crew member and use your onboard support procedure.</p>
    </div>
  </section>;
}
