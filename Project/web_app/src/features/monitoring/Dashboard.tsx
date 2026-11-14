import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { apiRequest } from '../../services/http';
import type { RiskSummary } from '../../generated/chatbot-types';
import type { Observation, Reading, SimulationResponse } from './types';

const fields: { key: string; label: string; group: keyof Pick<Observation, 'physiological' | 'self_assessment' | 'environment'> }[] = [
  { key: 'heart_rate', label: 'Heart rate', group: 'physiological' }, { key: 'systolic_pressure', label: 'Systolic pressure', group: 'physiological' },
  { key: 'diastolic_pressure', label: 'Diastolic pressure', group: 'physiological' }, { key: 'spo2', label: 'SpO₂', group: 'physiological' },
  { key: 'body_temperature', label: 'Body temperature', group: 'physiological' }, { key: 'glucose', label: 'Glucose', group: 'physiological' },
  { key: 'hrv_rmssd', label: 'HRV (RMSSD)', group: 'physiological' }, { key: 'sleep_duration', label: 'Sleep duration', group: 'self_assessment' },
  { key: 'mood', label: 'Mood', group: 'self_assessment' }, { key: 'exercise_duration', label: 'Exercise duration', group: 'self_assessment' },
  { key: 'radiation_dose_rate', label: 'Radiation dose rate', group: 'environment' }, { key: 'co2', label: 'Cabin CO₂', group: 'environment' },
  { key: 'cabin_temperature', label: 'Cabin temperature', group: 'environment' }, { key: 'humidity', label: 'Humidity', group: 'environment' },
  { key: 'noise', label: 'Noise', group: 'environment' }, { key: 'cabin_pressure', label: 'Cabin pressure', group: 'environment' },
  { key: 'gravity', label: 'Gravity', group: 'environment' }, { key: 'earth_latency', label: 'Earth latency', group: 'environment' },
  { key: 'simulated_daylight_duration', label: 'Daylight duration', group: 'environment' }, { key: 'social_interaction_duration', label: 'Social interaction', group: 'environment' },
];
function pretty(value: number | null, unit: string) { return value === null ? 'Unavailable' : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)} ${unit}`; }
function time(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); }
function getReading(observation: Observation, field: typeof fields[number]): Reading { return observation[field.group][field.key] ?? { value: null, unit: '', quality: 'missing', observed_at: null, period_start: null, period_end: null }; }

export function Dashboard() {
  const { token, profile } = useAuth();
  const [subject, setSubject] = useState('A01'); const [samples, setSamples] = useState<Observation[]>([]); const [sampleBusy, setSampleBusy] = useState(false); const [sampleError, setSampleError] = useState('');
  const [summary, setSummary] = useState<RiskSummary | null>(null); const [summaryError, setSummaryError] = useState(''); const [selectedRegion, setSelectedRegion] = useState('circulation');
  const newest = samples[0];
  const summaryState = summaryError ? 'unavailable' : !summary ? 'loading' : summary.availability;
  const loadSummary = useCallback(async () => {
    if (!token || !profile) return;
    try { const result = await apiRequest<RiskSummary>(`/api/v1/chatbot/astronauts/${encodeURIComponent(profile.astronaut_id)}/risk-summary`, token); setSummary(result); setSummaryError(''); }
    catch (reason) { setSummaryError(reason instanceof Error ? reason.message : 'Assessment summary is unavailable.'); }
  }, [token, profile]);
  useEffect(() => { loadSummary(); const timer = window.setInterval(() => { if (document.visibilityState === 'visible') loadSummary(); }, 10000); return () => window.clearInterval(timer); }, [loadSummary]);
  const history = useMemo(() => [...samples].reverse(), [samples]);
  async function generateSample() {
    if (sampleBusy) return;
    setSampleBusy(true); setSampleError('');
    try {
      const result = await apiRequest<SimulationResponse>(`/api/v1/simulation/runs/demo-run/astronauts/${subject}/inputs`);
      const observation = result.items[0];
      setSamples(previous => [observation, ...previous.filter(item => item.record_id !== observation.record_id)].slice(0, 8));
    } catch (reason) { setSampleError(reason instanceof Error ? reason.message : 'A simulated sample could not be generated.'); }
    finally { setSampleBusy(false); }
  }
  const related = selectedRegion === 'circulation' ? fields.slice(0, 3).concat(fields[6]) : selectedRegion === 'respiratory' ? [fields[3]] : selectedRegion === 'general' ? [fields[4], fields[5]] : fields.slice(7, 10);
  return <main className="page-content dashboard-content">
    <div className="page-heading dashboard-heading"><div><p className="eyebrow">MISSION HEALTH · OVERVIEW</p><h1>Monitoring overview</h1><p className="lead">Measurements and assessment status for {profile?.display_name}.</p></div><div className="mission-chip"><span className="status-dot" />{profile?.mission || 'Mission not set'}</div></div>
    <div className="dashboard-grid">
      <section className="panel readings-panel"><div className="panel-heading"><div><p className="eyebrow">SIMULATED INPUTS</p><h2>Body measurements</h2></div><span className="status-pill status-pill--neutral">Fixture subject</span></div>
        <div className="sample-controls"><label htmlFor="demo-subject">Demo subject</label><select id="demo-subject" value={subject} onChange={event => { setSubject(event.target.value); setSamples([]); setSampleError(''); }}><option value="A01">A01</option><option value="AST-001">AST-001</option></select><button className="button button--primary" onClick={generateSample} disabled={sampleBusy}>{sampleBusy ? 'Generating…' : 'Generate sample'}</button></div>
        <p className="simulator-note">Fixture measurements are separate from your signed-in profile. Every request generates a new sample.</p>
        {sampleError && <p className="notice notice--error" role="alert">{sampleError}</p>}
        {newest ? <><p className="reading-time">Latest sample · {time(newest.observed_at)} · <code>{newest.record_id.split('-').slice(0, 2).join('-')}</code></p><div className="metric-grid">{fields.slice(0, 10).map(field => { const reading = getReading(newest, field); return <Metric key={field.key} field={field.label} reading={reading} />; })}</div></> : <div className="empty-sample"><span className="empty-sample__icon" aria-hidden="true">＋</span><p>No sample generated</p><span>Choose a fixture subject and request one sample.</span></div>}
        {history.length > 1 && <div className="history-strip"><span>Recent samples · {history.length} held in this session</span><ol>{history.slice(-5).map(item => <li key={item.record_id}><time dateTime={item.observed_at}>{new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(new Date(item.observed_at))}</time></li>)}</ol></div>}
      </section>
      <section className="panel wellbeing-panel"><div className="panel-heading"><div><p className="eyebrow">ASSESSMENT SERVICE</p><h2>Wellbeing status</h2></div><span className={`status-pill status-pill--${summaryState === 'available' ? 'active' : 'neutral'}`}>{summaryState.replace('_', ' ')}</span></div>
        {summaryError ? <p className="notice notice--error">{summaryError}</p> : summary?.availability === 'not_assessed' ? <div className="empty-state"><p>No completed PHQ-9 assessment is available.</p><Link to="/wellbeing">Start assessment</Link></div> : summary?.availability === 'stale' ? <p className="notice notice--subtle">The most recent assessment is marked stale by the service. Review its timestamp and result history.</p> : summary ? <><p className="summary-copy">Latest summary returned by the assessment service.</p><div className={`followup-box ${summary.follow_up.status === 'follow_up_requested' ? 'followup-box--requested' : ''}`}><strong>{summary.follow_up.status === 'follow_up_requested' ? 'Follow-up requested' : summary.follow_up.status === 'unknown' ? 'Follow-up status unknown' : 'No follow-up flag returned'}</strong>{summary.follow_up.guidance && <p>{summary.follow_up.guidance}</p>}</div><p className="muted summary-time">Updated {summary.updated_at ? time(summary.updated_at) : 'time unavailable'}</p><p className="summary-limit">A missing follow-up flag does not establish overall safety.</p></> : <p className="muted">Loading assessment availability…</p>}
        <Link className="button button--secondary button--full" to="/wellbeing">Open wellbeing</Link>
      </section>
    </div>
    <div className="dashboard-grid dashboard-grid--lower">
      <section className="panel region-panel"><div className="panel-heading"><div><p className="eyebrow">MEASUREMENT GUIDE</p><h2>Body measurement groups</h2></div></div><p className="muted">Select a group to filter related measurements. This navigation is not a diagnostic assessment.</p><div className="region-layout"><div className="region-list" role="group" aria-label="Measurement groups">{[['circulation', 'Heart and circulation'], ['respiratory', 'Respiratory'], ['general', 'General health'], ['activity', 'Activity and wellbeing']].map(([id, label]) => <button key={id} className={`region-button ${selectedRegion === id ? 'is-selected' : ''}`} aria-pressed={selectedRegion === id} onClick={() => setSelectedRegion(id)}><span className={`region-glyph region-glyph--${id}`} aria-hidden="true">{id === 'circulation' ? '♥' : id === 'respiratory' ? '◉' : id === 'general' ? '◇' : '↗'}</span>{label}<span className="row-arrow">→</span></button>)}</div><div className="related-readings"><h3>{selectedRegion === 'circulation' ? 'Heart and circulation' : selectedRegion === 'respiratory' ? 'Respiratory' : selectedRegion === 'general' ? 'General health' : 'Activity and wellbeing'}</h3>{related.map(field => <div className="related-row" key={field.key}><span>{field.label}</span><strong>{newest ? pretty(getReading(newest, field).value, getReading(newest, field).unit) : 'Unavailable'}</strong></div>)}</div></div></section>
      <section className="panel cabin-panel"><div className="panel-heading"><div><p className="eyebrow">SIMULATED ENVIRONMENT</p><h2>Cabin conditions</h2></div><span className="status-pill status-pill--neutral">Fixture data</span></div><div className="cabin-list">{fields.slice(10).map(field => { const reading = newest ? getReading(newest, field) : null; return <div className="cabin-row" key={field.key}><span>{field.label}</span><strong>{reading ? pretty(reading.value, reading.unit) : 'Unavailable'}</strong><span className="quality-label">{reading?.quality ?? 'no sample'}</span></div>; })}</div></section>
    </div>
  </main>;
}

function Metric({ field, reading }: { field: string; reading: Reading }) {
  return <article className="metric-card"><span className="metric-label">{field}</span><strong className={reading.quality === 'valid' ? '' : 'metric-value--missing'}>{pretty(reading.value, reading.unit)}</strong><span className="quality-label">{reading.quality} reading</span></article>;
}
