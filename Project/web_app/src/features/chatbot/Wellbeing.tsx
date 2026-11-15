import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ChatbotError, createChatbotClient } from '../../generated/chatbot-client';
import type { CheckIn, CheckInTrend, Definition, Session, TodayCheckIn } from '../../generated/chatbot-types';
import { LocalConversation } from './LocalConversation';

function api(token: string) { return createChatbotClient('', () => token); }
function requestKey(kind: string) {
  const keyName = `orbit:${kind}:pending`;
  let key = sessionStorage.getItem(keyName);
  if (!key) { key = crypto.randomUUID(); sessionStorage.setItem(keyName, key); }
  return { key, clear: () => sessionStorage.removeItem(keyName) };
}

const moodOptions = [
  { value: 1, label: 'Very low' }, { value: 2, label: 'Low' }, { value: 3, label: 'Okay' },
  { value: 4, label: 'Good' }, { value: 5, label: 'Very good' },
];
function moodLabel(value: number) { return moodOptions.find(option => option.value === value)?.label ?? 'Not recorded'; }
function checkInDateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(`${value}T12:00:00Z`));
}

export function Wellbeing() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [definitions, setDefinitions] = useState<Definition[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState('');
  const [busyCode, setBusyCode] = useState('');
  const [todayCheckIn, setTodayCheckIn] = useState<TodayCheckIn | null>(null);
  const [checkInHistory, setCheckInHistory] = useState<CheckIn[]>([]);
  const [checkInTrend, setCheckInTrend] = useState<CheckInTrend | null>(null);
  const [checkInLoading, setCheckInLoading] = useState(true);
  const [checkInError, setCheckInError] = useState('');
  const [checkInMessage, setCheckInMessage] = useState('');
  const [checkInSaving, setCheckInSaving] = useState(false);
  const [moodScore, setMoodScore] = useState<number | null>(null);
  const [sleepDuration, setSleepDuration] = useState('');
  useEffect(() => {
    if (!token) return;
    let active = true;
    const client = api(token);
    Promise.all([client.assessments(), client.sessions(), client.todayCheckIn(), client.checkInHistory(7), client.checkInTrend()])
      .then(([defs, all, today, history, trend]) => {
        if (!active) return;
        setDefinitions(defs); setSessions(all); setTodayCheckIn(today); setCheckInHistory(history); setCheckInTrend(trend);
        setMoodScore(today.check_in?.mood_score ?? null);
        setSleepDuration(today.check_in ? String(today.check_in.sleep_duration_hours) : '');
      })
      .catch(reason => { if (active) { setError(reason.message); setCheckInError('Today’s check-in and history could not be loaded.'); } })
      .finally(() => { if (active) setCheckInLoading(false); });
    return () => { active = false; };
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
  async function saveCheckIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || moodScore === null || sleepDuration === '') return;
    setCheckInSaving(true); setCheckInError(''); setCheckInMessage('');
    const client = api(token);
    try {
      const saved = await client.saveTodayCheckIn({
        expected_revision: todayCheckIn?.check_in?.revision ?? 0,
        mood_score: moodScore,
        sleep_duration_hours: Number(sleepDuration),
      });
      setTodayCheckIn({ check_in_date: saved.check_in_date, check_in: saved });
      setCheckInHistory(previous => [saved, ...previous.filter(item => item.check_in_date !== saved.check_in_date)].slice(0, 7));
      client.checkInTrend().then(setCheckInTrend).catch(() => undefined);
      setMoodScore(saved.mood_score); setSleepDuration(String(saved.sleep_duration_hours));
      setCheckInMessage('Today’s check-in saved. You can update it again today.');
    } catch (reason) {
      if (reason instanceof ChatbotError && reason.status === 409) {
        try {
          const [today, history, trend] = await Promise.all([client.todayCheckIn(), client.checkInHistory(7), client.checkInTrend()]);
          setTodayCheckIn(today); setCheckInHistory(history); setCheckInTrend(trend);
          setMoodScore(today.check_in?.mood_score ?? null);
          setSleepDuration(today.check_in ? String(today.check_in.sleep_duration_hours) : '');
          setCheckInError('A newer check-in was saved elsewhere. The latest saved values have been loaded.');
        } catch { setCheckInError('The check-in changed elsewhere and could not be reloaded. Refresh the page before saving again.'); }
      } else setCheckInError(reason instanceof Error ? reason.message : 'Today’s check-in could not be saved.');
    } finally { setCheckInSaving(false); }
  }
  const resumable = sessions.filter(item => item.status === 'in_progress' || item.status === 'paused');
  return <main className="page-content wellbeing-page">
    <div className="page-heading"><div><p className="eyebrow">WELLBEING</p><h1>Structured assessments</h1><p className="lead">Choose a questionnaire or continue an existing session. Scores and follow-up flags come from the assessment service.</p></div></div>
    {error && <p className="notice notice--error" role="alert">{error}</p>}
    <section className="section-block check-in-section" aria-labelledby="check-in-title">
      <div className="section-title"><div><p className="eyebrow">DAILY SELF-CHECK</p><h2 id="check-in-title">Mood and sleep</h2></div><span className="section-meta">{todayCheckIn ? `UTC day · ${todayCheckIn.check_in_date}` : 'One entry per UTC day'}</span></div>
      <form className="panel check-in-panel" onSubmit={saveCheckIn}>
        {checkInLoading ? <p className="muted" role="status">Loading today’s check-in…</p> : <>
          <div className="check-in-fields">
            <fieldset className="check-in-mood" disabled={checkInSaving}>
              <legend>How would you rate your mood today?</legend>
              <div className="check-in-mood__options">{moodOptions.map(option => <label className={`check-in-mood__option ${moodScore === option.value ? 'is-selected' : ''}`} key={option.value}><input type="radio" name="mood-score" value={option.value} checked={moodScore === option.value} onChange={() => setMoodScore(option.value)} /><span><b>{option.value}</b>{option.label}</span></label>)}</div>
            </fieldset>
            <label className="check-in-sleep" htmlFor="sleep-duration"><span>Sleep during your last main sleep period</span><div><input id="sleep-duration" type="number" min="0" max="24" step="0.25" required value={sleepDuration} onChange={event => setSleepDuration(event.target.value)} disabled={checkInSaving} /><span>hours</span></div></label>
          </div>
          {checkInError && <p className="notice notice--error" role="alert">{checkInError}</p>}
          {checkInMessage && <p className="notice notice--subtle" role="status">{checkInMessage}</p>}
          <div className="check-in-actions"><p className="muted">A private self-check-in; it does not produce a score, diagnosis, or safety determination.</p><button className="button button--primary" type="submit" disabled={checkInSaving || moodScore === null || sleepDuration === ''}>{checkInSaving ? 'Saving…' : todayCheckIn?.check_in ? 'Update today’s check-in' : 'Save today’s check-in'}</button></div>
        </>}
      </form>
      {checkInHistory.length > 0 && <div className="check-in-history"><h3>Recent check-ins</h3><div className="history-list">{checkInHistory.map(item => <article className="history-row check-in-history__row" key={item.check_in_date}><span><strong>{checkInDateLabel(item.check_in_date)}</strong><small>Mood · {moodLabel(item.mood_score)}</small></span><span className="history-score">{item.sleep_duration_hours} h sleep</span></article>)}</div></div>}
      {checkInTrend && <div className={`check-in-trend ${checkInTrend.status === 'check_in_suggested' ? 'check-in-trend--prompt' : ''}`}><div><p className="eyebrow">PERSONAL TREND · {checkInTrend.policy_version}</p><h3>{checkInTrend.status === 'check_in_suggested' ? 'Consider a private check-in' : checkInTrend.status === 'no_pattern' ? 'No combined decline detected' : 'Trend needs more entries'}</h3><p>{checkInTrend.message}</p></div>{checkInTrend.status !== 'insufficient_data' && <div className="check-in-trend__values"><span>Mood <strong>{checkInTrend.baseline_mood_mean} → {checkInTrend.recent_mood_mean}</strong></span><span>Sleep <strong>{checkInTrend.baseline_sleep_mean_hours} h → {checkInTrend.recent_sleep_mean_hours} h</strong></span></div>}</div>}
    </section>
    <LocalConversation />
    {resumable.length > 0 && <section className="section-block"><div className="section-title"><div><p className="eyebrow">IN PROGRESS</p><h2>Continue an assessment</h2></div></div><div className="assessment-grid">{resumable.map(item => <article className="panel assessment-card" key={item.session_id}><div className="assessment-card__meta"><span className="status-pill status-pill--neutral">{item.status === 'paused' ? 'Paused' : 'In progress'}</span><span>{item.assessment.code}</span></div><h3>{item.assessment.name}</h3><p>{Object.keys(item.responses).length} of {item.assessment.questions.length} answers saved</p><Link className="button button--secondary" to={`/wellbeing/sessions/${item.session_id}`}>Resume assessment</Link></article>)}</div></section>}
    <section className="section-block"><div className="section-title"><div><p className="eyebrow">AVAILABLE</p><h2>Start an assessment</h2></div><span className="section-meta">Backend wording and options are shown as supplied</span></div>
      <div className="assessment-grid">{definitions.map(definition => <article className="panel assessment-card" key={definition.code}><div className="assessment-card__meta"><span className="status-pill status-pill--neutral">{definition.questions.length} items</span><span>{definition.code}</span></div><h3>{definition.name}</h3><p>{definition.instructions}</p><p className="notice notice--subtle">{definition.notice}</p><button className="button button--primary" onClick={() => start(definition)} disabled={!!busyCode}>{busyCode === definition.code ? 'Starting…' : 'Start assessment'}</button></article>)}</div>
    </section>
    <p className="disclaimer">This screening demonstration is not a clinical diagnosis or an astronaut fitness assessment.</p>
  </main>;
}
