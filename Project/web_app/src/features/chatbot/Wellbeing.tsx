import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { createChatbotClient } from '../../generated/chatbot-client';
import type { Definition, Session } from '../../generated/chatbot-types';

function api(token: string) { return createChatbotClient('', () => token); }
function requestKey(kind: string) {
  const keyName = `orbit:${kind}:pending`;
  let key = sessionStorage.getItem(keyName);
  if (!key) { key = crypto.randomUUID(); sessionStorage.setItem(keyName, key); }
  return { key, clear: () => sessionStorage.removeItem(keyName) };
}

export function Wellbeing() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [definitions, setDefinitions] = useState<Definition[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState('');
  const [busyCode, setBusyCode] = useState('');
  useEffect(() => {
    if (!token) return;
    Promise.all([api(token).assessments(), api(token).sessions()]).then(([defs, all]) => { setDefinitions(defs); setSessions(all); }).catch(reason => setError(reason.message));
  }, [token]);
  async function start(definition: Definition) {
    if (!token) return;
    setBusyCode(definition.code); setError('');
    const pending = requestKey(`create:${definition.code}`);
    try {
      const session = await api(token).createSession({ assessment_code: definition.code as 'PHQ9' | 'GAD7', assessment_version: definition.version }, pending.key);
      pending.clear(); navigate(`/wellbeing/sessions/${session.session_id}`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not start the assessment.'); }
    finally { setBusyCode(''); }
  }
  const resumable = sessions.filter(item => item.status === 'in_progress' || item.status === 'paused');
  return <main className="page-content">
    <div className="page-heading"><div><p className="eyebrow">WELLBEING</p><h1>Structured assessments</h1><p className="lead">Choose a questionnaire or continue an existing session. Scores and follow-up flags come from the assessment service.</p></div></div>
    {error && <p className="notice notice--error" role="alert">{error}</p>}
    {resumable.length > 0 && <section className="section-block"><div className="section-title"><div><p className="eyebrow">IN PROGRESS</p><h2>Continue an assessment</h2></div></div><div className="assessment-grid">{resumable.map(item => <article className="panel assessment-card" key={item.session_id}><div className="assessment-card__meta"><span className="status-pill status-pill--neutral">{item.status === 'paused' ? 'Paused' : 'In progress'}</span><span>{item.assessment.code}</span></div><h3>{item.assessment.name}</h3><p>{Object.keys(item.responses).length} of {item.assessment.questions.length} answers saved</p><Link className="button button--secondary" to={`/wellbeing/sessions/${item.session_id}`}>Resume assessment</Link></article>)}</div></section>}
    <section className="section-block"><div className="section-title"><div><p className="eyebrow">AVAILABLE</p><h2>Start an assessment</h2></div><span className="section-meta">Backend wording and options are shown as supplied</span></div>
      <div className="assessment-grid">{definitions.map(definition => <article className="panel assessment-card" key={definition.code}><div className="assessment-card__meta"><span className="status-pill status-pill--neutral">{definition.questions.length} items</span><span>{definition.code}</span></div><h3>{definition.name}</h3><p>{definition.instructions}</p><p className="notice notice--subtle">{definition.notice}</p><button className="button button--primary" onClick={() => start(definition)} disabled={!!busyCode}>{busyCode === definition.code ? 'Starting…' : 'Start assessment'}</button></article>)}</div>
    </section>
    <p className="disclaimer">This screening demonstration is not a clinical diagnosis or an astronaut fitness assessment.</p>
  </main>;
}
