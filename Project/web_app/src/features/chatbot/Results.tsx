import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { createChatbotClient } from '../../generated/chatbot-client';
import type { Result, Session } from '../../generated/chatbot-types';

function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); }
export function ResultPage() {
  const { token } = useAuth(); const { sessionId = '' } = useParams();
  const [result, setResult] = useState<Result | null>(null); const [error, setError] = useState('');
  useEffect(() => { if (token) createChatbotClient('', () => token).result(sessionId).then(setResult).catch(reason => setError(reason.message)); }, [token, sessionId]);
  if (error) return <main className="page-content"><p className="notice notice--error" role="alert">{error}</p><Link to="/wellbeing/history">View result history</Link></main>;
  if (!result) return <main className="page-content"><p role="status">Loading assessment result…</p></main>;
  return <main className="page-content page-content--narrow"><div className="breadcrumbs"><Link to="/wellbeing">Wellbeing</Link><span>/</span><span>Result</span></div><p className="eyebrow">{result.assessment_code} · {result.assessment_version}</p><h1>Assessment result</h1><section className="panel result-panel"><div className="result-score"><span>Score</span><strong>{result.total_score}<small> / {result.maximum_score}</small></strong></div><div><p className="eyebrow">SERVICE INTERPRETATION</p><p className="result-interpretation">{result.interpretation}</p></div><p className="muted">Completed {formatDate(result.completed_at)}</p></section><p className="disclaimer">{result.notice}</p><div className="button-row"><Link className="button button--primary" to="/wellbeing/history">View result history</Link><Link className="button button--secondary" to="/dashboard">Return to overview</Link></div></main>;
}
export function HistoryPage() {
  const { token } = useAuth(); const [results, setResults] = useState<Result[]>([]); const [sessions, setSessions] = useState<Session[]>([]); const [error, setError] = useState('');
  useEffect(() => { if (!token) return; const client = createChatbotClient('', () => token); Promise.all([client.results(), client.sessions()]).then(([history, all]) => { setResults(history); setSessions(all.filter(s => s.status === 'paused' || s.status === 'in_progress')); }).catch(reason => setError(reason.message)); }, [token]);
  return <main className="page-content"><div className="page-heading"><div><p className="eyebrow">WELLBEING</p><h1>Assessment history</h1><p className="lead">Completed results are grouped by the instrument and version returned by the service.</p></div></div>{error && <p role="alert" className="notice notice--error">{error}</p>}
    {sessions.length > 0 && <section className="section-block"><h2>Sessions to resume</h2><div className="history-list">{sessions.map(session => <Link className="history-row" key={session.session_id} to={`/wellbeing/sessions/${session.session_id}`}><span><strong>{session.assessment.name}</strong><small>{session.status === 'paused' ? 'Paused' : 'In progress'}</small></span><span className="row-arrow">Resume →</span></Link>)}</div></section>}
    <section className="section-block"><h2>Completed results</h2>{results.length ? <div className="history-list">{results.map(result => <Link className="history-row" key={result.result_id} to={`/wellbeing/results/${result.session_id}`}><span><strong>{result.assessment_code} result</strong><small>{result.assessment_version} · {formatDate(result.completed_at)}</small></span><span className="history-score">{result.total_score} / {result.maximum_score}</span></Link>)}</div> : <div className="empty-state"><p>No completed assessments are available yet.</p><Link to="/wellbeing">Start assessment</Link></div>}</section>
  </main>;
}
