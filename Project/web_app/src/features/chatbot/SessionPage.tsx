import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ChatbotError, createChatbotClient } from '../../generated/chatbot-client';
import type { AssistantReply, Result, Session } from '../../generated/chatbot-types';

export function SessionPage() {
  const { token } = useAuth(); const { sessionId = '' } = useParams(); const navigate = useNavigate();
  const [session, setSession] = useState<Session | null>(null); const [error, setError] = useState(''); const [saving, setSaving] = useState(false); const [help, setHelp] = useState<AssistantReply | null>(null);
  const [selectedValue, setSelectedValue] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [completeKey, setCompleteKey] = useState(() => sessionStorage.getItem(`orbit:complete:${sessionId}`) ?? '');
  const client = token ? createChatbotClient('', () => token) : null;
  const reload = useCallback(async () => { if (client) setSession(await client.session(sessionId)); }, [client, sessionId]);
  useEffect(() => { reload().catch(reason => setError(reason.message)); }, [reload]);
  async function transition(action: 'pause' | 'resume' | 'cancel') {
    if (!client || !session) return;
    setSaving(true); setError('');
    try {
      if (action === 'cancel' && !window.confirm('Cancel this assessment? Saved answers will remain in its history.')) return;
      setSession(await client.transition(session.session_id, action, session.revision));
      if (action === 'cancel') navigate('/wellbeing');
    } catch (reason) {
      const conflict = reason instanceof ChatbotError && reason.status === 409;
      await reload().catch(() => undefined);
      setError(conflict ? 'This session changed elsewhere. The latest saved state is shown.' : `${reason instanceof Error ? reason.message : 'The session could not be updated.'} The saved session was reloaded.`);
    }
    finally { setSaving(false); }
  }
  async function answer() {
    if (!client || !session) return;
    if (selectedValue === null) return;
    const question = editingId ? session.assessment.questions.find(item => item.id === editingId) : session.current_question;
    if (!question) return;
    setSaving(true); setError('');
    try { setSession(await client.answer(session.session_id, question.id, { expected_revision: session.revision, value: selectedValue })); setSelectedValue(null); setEditingId(null); setHelp(null); }
    catch (reason) {
      if (reason instanceof ChatbotError && reason.status === 409) { await reload(); setError('The saved session had changed. The latest question and answers are shown.'); }
      else { await reload().catch(() => undefined); setError(`${reason instanceof Error ? reason.message : 'Answer was not confirmed.'} The saved session has been reloaded.`); }
    } finally { setSaving(false); }
  }
  async function complete() {
    if (!client || !session) return;
    const key = completeKey || crypto.randomUUID();
    if (!completeKey) { setCompleteKey(key); sessionStorage.setItem(`orbit:complete:${sessionId}`, key); }
    setSaving(true); setError('');
    try {
      const result: Result = await client.complete(session.session_id, session.revision, key);
      sessionStorage.removeItem(`orbit:complete:${sessionId}`); navigate(`/wellbeing/results/${result.session_id}`, { replace: true });
    } catch (reason) {
      if (reason instanceof ChatbotError && reason.status === 409) {
        sessionStorage.removeItem(`orbit:complete:${sessionId}`);
        setCompleteKey('');
        await reload();
        setError('The session changed before completion. The saved state is shown; complete again when it is ready.');
      } else {
        setError(`${reason instanceof Error ? reason.message : 'Completion was not confirmed.'} Retry with the same request key.`);
      }
    } finally { setSaving(false); }
  }
  async function ask(intent: 'instructions' | 'question' | 'support') {
    if (!client || !session) return;
    try { setHelp(await client.assistant({ session_id: session.session_id, intent, ...(intent === 'question' && session.current_question ? { question_id: session.current_question.id } : {}) })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Static help is unavailable.'); }
  }
  if (!session) return <main className="page-content"><p className="notice" role="status">Loading assessment session…</p>{error && <p className="notice notice--error" role="alert">{error}</p>}</main>;
  const question = editingId ? session.assessment.questions.find(item => item.id === editingId) ?? session.current_question : session.current_question;
  const answered = Object.keys(session.responses).length;
  const done = session.status === 'scored';
  const cancelled = session.status === 'cancelled';
  return <main className="page-content page-content--narrow">
    <div className="breadcrumbs"><Link to="/wellbeing">Wellbeing</Link><span>/</span><span>{session.assessment.name}</span></div>
    <header className="session-head"><div><p className="eyebrow">{session.assessment.code} · {session.assessment.version}</p><h1>{session.assessment.name}</h1><p className="lead">{session.assessment.instructions}</p></div><span className={`status-pill ${session.status === 'paused' ? 'status-pill--neutral' : 'status-pill--active'}`}>{session.status.replace('_', ' ')}</span></header>
    <div className="progress-line" aria-label={`${answered} of ${session.assessment.questions.length} questions answered`}><div style={{ width: `${Math.round(answered / session.assessment.questions.length * 100)}%` }} /></div>
    <p className="muted progress-copy">{answered} of {session.assessment.questions.length} answers saved</p>
    {session.follow_up.status === 'follow_up_requested' && <section className="notice notice--followup" role="status"><strong>Follow-up requested</strong><p>{session.follow_up.guidance}</p></section>}
    {error && <p className="notice notice--error" role="alert">{error}</p>}
    {done ? <section className="panel question-panel"><h2>Assessment complete</h2><p>This session has a saved result.</p><Link className="button button--primary" to={`/wellbeing/results/${session.session_id}`}>View result</Link></section> : cancelled ? <section className="panel question-panel"><h2>Assessment canceled</h2><p>Saved responses remain in the session history.</p><Link className="button button--secondary" to="/wellbeing">Open assessments</Link></section> : <section className="panel question-panel" aria-live="polite">
      {question ? <><p className="eyebrow">{editingId ? 'CHANGE SAVED RESPONSE' : `QUESTION ${question.position} OF ${session.assessment.questions.length}`}</p><h2>{question.text}</h2><fieldset className="answer-options" disabled={saving || session.status === 'paused'}><legend>Select one response</legend>{session.assessment.options.map(option => <label className={`answer-option ${(selectedValue ?? session.responses[question.id]) === option.value ? 'is-selected' : ''}`} key={option.value}><input type="radio" name={question.id} checked={(selectedValue ?? session.responses[question.id]) === option.value} onChange={() => setSelectedValue(option.value)} /><span>{option.label}</span></label>)}</fieldset><div className="answer-actions"><button className="button button--primary save-answer" disabled={saving || selectedValue === null || session.status === 'paused'} onClick={answer}>{saving ? 'Saving answer…' : 'Save answer'}</button>{editingId && <button className="button button--secondary save-answer" disabled={saving} onClick={() => { setEditingId(null); setSelectedValue(null); }}>Keep saved response</button>}</div></> : <><h2>Answers saved</h2><p>{session.status === 'paused' ? 'Resume this session before completing the saved answers.' : 'All questions are answered. Save the completed result to review the service score.'}</p><button className="button button--primary" disabled={saving || session.status === 'paused'} onClick={complete}>{saving ? 'Saving result…' : 'Complete assessment'}</button></>}
      {answered > 0 && session.status === 'in_progress' && <section className="saved-answers"><h3>Saved responses</h3>{session.assessment.questions.filter(item => session.responses[item.id] !== undefined).map(item => <div className="saved-answer" key={item.id}><span><strong>{item.position}.</strong> {item.text}<small>{session.assessment.options.find(option => option.value === session.responses[item.id])?.label}</small></span><button className="text-button" disabled={saving} onClick={() => { setEditingId(item.id); setSelectedValue(session.responses[item.id]); }}>Change answer</button></div>)}</section>}
      <div className="question-tools"><button className="text-button" onClick={() => ask('instructions')}>Assessment instructions</button><button className="text-button" onClick={() => ask('support')}>Support information</button>{question && <button className="text-button" onClick={() => ask('question')}>Explain this question</button>}</div>
      {help && <p className="notice notice--subtle" role="status">{help.text} <span className="static-tag">Static information</span></p>}
      <div className="session-actions">{session.status === 'paused' ? <button className="button button--secondary" disabled={saving} onClick={() => transition('resume')}>Resume assessment</button> : <button className="button button--secondary" disabled={saving} onClick={() => transition('pause')}>Pause assessment</button>}<button className="text-button text-button--danger" disabled={saving} onClick={() => transition('cancel')}>Cancel session</button></div>
    </section>}
    <p className="disclaimer">Responses are saved by the local assessment service. {session.assessment.notice}</p>
  </main>;
}
