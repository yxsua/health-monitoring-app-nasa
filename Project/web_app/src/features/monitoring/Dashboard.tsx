import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { apiRequest } from '../../services/http';
import type { RecommendationResponse, RiskSummary } from '../../generated/chatbot-types';
import type { AnalysisResponse, Observation, Reading, SimulationResponse } from './types';

const scenarioOptions = [
  { id: 'normal', label: 'Nominal simulation' },
  { id: 'solar_event', label: 'Solar event' },
  { id: 'high_co2', label: 'Elevated cabin CO₂' },
  { id: 'prolonged_isolation', label: 'Prolonged isolation' },
] as const;
type ScenarioId = typeof scenarioOptions[number]['id'];

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
const physicalFields = fields.filter(field => field.group === 'physiological');
const wellbeingFields = fields.filter(field => field.group === 'self_assessment');
const environmentFields = fields.filter(field => field.group === 'environment');
// These are the simulator's nominal means, not clinical targets.
const simulatorBaselines: Record<string, number> = {
  heart_rate: 70, systolic_pressure: 115, diastolic_pressure: 75, spo2: 98,
  body_temperature: 36.7, glucose: 95, hrv_rmssd: 65, sleep_duration: 7, mood: 4,
  exercise_duration: 30, radiation_dose_rate: 0.5, co2: 1000, cabin_temperature: 22,
  humidity: 45, noise: 40, cabin_pressure: 101, gravity: 0.1,
};
const metricInformation: Record<string, { what: string; why: string }> = {
  heart_rate: { what: 'Heart beats per minute.', why: 'Tracks cardiovascular response and changes with activity, rest, and stress.' },
  systolic_pressure: { what: 'Pressure in the arteries as the heart contracts.', why: 'Helps monitor cardiovascular load alongside diastolic pressure.' },
  diastolic_pressure: { what: 'Pressure in the arteries between heartbeats.', why: 'Adds context to systolic pressure when following circulation trends.' },
  spo2: { what: 'Estimated percentage of oxygen carried in the blood.', why: 'A change can prompt a closer look at breathing and cabin oxygen conditions.' },
  body_temperature: { what: 'The astronaut’s measured body temperature.', why: 'Trends can help identify changes in thermal or general physiological state.' },
  glucose: { what: 'Glucose concentration in the blood.', why: 'Provides context about energy metabolism and meal-related changes.' },
  hrv_rmssd: { what: 'Beat-to-beat interval variability, measured as RMSSD in milliseconds.', why: 'Can help follow recovery and autonomic trends against an individual reference.' },
  sleep_duration: { what: 'Reported sleep duration for the day, in hours.', why: 'Sleep patterns support interpretation of mood, recovery, and daily performance.' },
  mood: { what: 'A self-reported mood score from 1 to 5.', why: 'Repeated check-ins help reveal changes in wellbeing over time.' },
  exercise_duration: { what: 'Reported exercise time for the day, in minutes.', why: 'Activity context helps interpret cardiovascular and recovery measurements.' },
  radiation_dose_rate: { what: 'Estimated radiation dose rate, not accumulated dose.', why: 'Tracks the current exposure environment during a mission.' },
  co2: { what: 'Carbon dioxide concentration in the cabin air.', why: 'Helps monitor air quality and ventilation conditions.' },
  cabin_temperature: { what: 'Ambient temperature measured inside the cabin.', why: 'Supports monitoring of environmental comfort and thermal control.' },
  humidity: { what: 'Relative humidity in the cabin, shown as a percentage.', why: 'Helps track cabin comfort and moisture conditions.' },
  noise: { what: 'Cabin sound level measured in decibels (dBA).', why: 'Persistent noise can affect rest, communication, and comfort.' },
  cabin_pressure: { what: 'Cabin atmospheric pressure.', why: 'Helps monitor the spacecraft’s pressurized environment.' },
  gravity: { what: 'The simulated gravity level, in g.', why: 'Provides context for movement, exercise, and other mission measurements.' },
  earth_latency: { what: 'Simulated communication delay to Earth.', why: 'Communication delay affects coordination and response timing.' },
  simulated_daylight_duration: { what: 'Simulated daylight duration for the day.', why: 'Light exposure provides context for sleep and circadian patterns.' },
  social_interaction_duration: { what: 'Reported social interaction time for the day.', why: 'Helps follow connection and isolation patterns during a mission.' },
};
type RiskLevel = 'normal' | 'caution' | 'warning' | 'critical' | 'unknown';
type ToastAlert = { id: string; type: string; level: Exclude<RiskLevel, 'normal' | 'unknown'>; title: string; detail: string };
const alertSystemLabels: Record<string, string> = {
  fisiologia: 'physiology', ambiente: 'environment', soporte_vital: 'life support',
  cognitivo: 'cognitive', radiacion: 'radiation', sensor: 'sensor',
};
const riskRank: Record<RiskLevel, number> = { unknown: 0, normal: 1, caution: 2, warning: 3, critical: 4 };
const regionOptions = [
  { id: 'activity', label: 'Activity and wellbeing', title: 'Activity and wellbeing', fieldKeys: ['sleep_duration', 'mood', 'exercise_duration'] },
  { id: 'circulation', label: 'Heart and circulation', title: 'Heart and circulation', fieldKeys: ['heart_rate', 'systolic_pressure', 'diastolic_pressure', 'hrv_rmssd'] },
  { id: 'respiratory', label: 'Respiratory', title: 'Respiratory', fieldKeys: ['spo2'] },
  { id: 'general', label: 'General health', title: 'General health', fieldKeys: ['body_temperature', 'glucose'] },
] as const;
function pretty(value: number | null, unit: string) { return value === null ? 'Unavailable' : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)} ${unit}`; }
function time(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); }
function getReading(observation: Observation, field: typeof fields[number]): Reading { return observation[field.group][field.key] ?? { value: null, unit: '', quality: 'missing', observed_at: null, period_start: null, period_end: null }; }
function baselineDeviationScore(fieldKey: string, observation: Observation | null) {
  const baseline = simulatorBaselines[fieldKey];
  const field = fields.find(item => item.key === fieldKey);
  const reading = field && observation ? observation[field.group][fieldKey] : undefined;
  if (baseline === undefined || !reading || reading.quality !== 'valid' || reading.value === null) return 0;
  const sigma = Math.max(Math.abs(baseline) * 0.03, 0.0001);
  const deviations = Math.abs(reading.value - baseline) / sigma;
  return deviations <= 3 ? 0 : Math.round(Math.min(100, ((deviations - 3) / 7) * 100));
}

export function Dashboard() {
  const { token, profile } = useAuth();
  const [subject, setSubject] = useState('A01');
  const [scenario, setScenario] = useState<ScenarioId>('normal');
  const [scenarioReady, setScenarioReady] = useState(false);
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [scenarioError, setScenarioError] = useState('');
  const [scenarioTransition, setScenarioTransition] = useState({ active: false, step: 8, total_steps: 8 });
  const [scenarioRampStarted, setScenarioRampStarted] = useState(false);
  const [samples, setSamples] = useState<Observation[]>([]);
  const [analysis, setAnalysis] = useState<{ recordId: string; state: 'loading' | 'unavailable' | 'ready'; result?: AnalysisResponse; message?: string } | null>(null);
  const [live, setLive] = useState(true);
  const [feedState, setFeedState] = useState<'connecting' | 'live' | 'paused' | 'error'>('connecting');
  const [feedMessage, setFeedMessage] = useState('');
  const [summary, setSummary] = useState<RiskSummary | null>(null); const [summaryError, setSummaryError] = useState(''); const [selectedRegion, setSelectedRegion] = useState<string>('circulation');
  const [notifications, setNotifications] = useState<ToastAlert[]>([]);
  const subjectRef = useRef(subject);
  subjectRef.current = subject;
  const liveRef = useRef(true);
  const inFlightRef = useRef(false);
  const bootstrapRequestRef = useRef(false);
  const pollTimerRef = useRef<number | null>(null);
  const currentRecordIdRef = useRef('');
  const scenarioRef = useRef<ScenarioId>('normal');
  const scenarioChangeRef = useRef(false);
  const notificationTimersRef = useRef<number[]>([]);
  const alertCooldownsRef = useRef(new Map<string, number>());
  const newest = samples[0];
  const summaryState = summaryError ? 'unavailable' : !summary ? 'loading' : summary.availability;
  const selectedRegionInfo = regionOptions.find(region => region.id === selectedRegion) ?? regionOptions[1];
  const related = fields.filter(field => selectedRegionInfo.fieldKeys.includes(field.key as never));
  const latestAnalysis = analysis?.state === 'ready' && analysis.recordId === newest?.record_id ? analysis.result : undefined;
  const riskForField = (fieldKey: string): RiskLevel => {
    if (latestAnalysis?.rules.status !== 'available') return 'unknown';
    const severity = latestAnalysis.rules.alerts
      .filter(alert => alert.evidence.some(item => item.field === fieldKey))
      .reduce<RiskLevel>((highest, alert) => riskRank[alert.severity] > riskRank[highest] ? alert.severity : highest, 'normal');
    return severity;
  };
  const groupRisk = (keys: readonly string[]): RiskLevel => latestAnalysis?.rules.status !== 'available' ? 'unknown' : keys.map(riskForField).reduce<RiskLevel>((highest, risk) => riskRank[risk] > riskRank[highest] ? risk : highest, 'normal');
  const regionHasAlert = (keys: readonly string[]) => keys.some(key => baselineDeviationScore(key, newest) >= 35) || (latestAnalysis?.rules.status === 'available' && latestAnalysis.rules.alerts.some(alert => alert.evidence.some(item => keys.includes(item.field) && item.quality === 'valid')));
  const loadSummary = useCallback(async () => {
    if (!token || !profile) return;
    try { const result = await apiRequest<RiskSummary>(`/api/v1/chatbot/astronauts/${encodeURIComponent(profile.astronaut_id)}/risk-summary`, token); setSummary(result); setSummaryError(''); }
    catch (reason) { setSummaryError(reason instanceof Error ? reason.message : 'Assessment summary is unavailable.'); }
  }, [token, profile]);
  useEffect(() => { loadSummary(); const timer = window.setInterval(() => { if (document.visibilityState === 'visible') loadSummary(); }, 10000); return () => window.clearInterval(timer); }, [loadSummary]);

  useEffect(() => () => notificationTimersRef.current.forEach(window.clearTimeout), []);

  useEffect(() => {
    if (analysis?.state !== 'ready' || analysis.recordId !== newest?.record_id || !analysis.result) return;
    const result = analysis.result;
    const incoming: Omit<ToastAlert, 'id'>[] = result.rules.alerts.map(alert => ({
      type: `rule:${alert.code}`, level: alert.severity, title: alert.message,
      detail: alertSystemLabels[alert.system.toLowerCase()] ?? alert.system.replaceAll('_', ' '),
    }));
    if (result.anomaly.status === 'available' && result.anomaly.is_anomaly) incoming.push({
      type: 'model:anomaly', level: 'warning', title: 'Unusual measurement pattern', detail: 'Isolation Forest flagged this sample for review.',
    });
    const now = Date.now();
    let lastShown: Record<string, number> = {};
    try { lastShown = JSON.parse(window.localStorage.getItem('astrahealth-alert-cooldowns') ?? '{}') as Record<string, number>; } catch { lastShown = {}; }
    const eligible = incoming.filter((item, index) => incoming.findIndex(candidate => candidate.type === item.type) === index && now - Math.max(lastShown[item.type] ?? 0, alertCooldownsRef.current.get(item.type) ?? 0) >= 180_000);
    if (!eligible.length) return;
    for (const item of eligible) { lastShown[item.type] = now; alertCooldownsRef.current.set(item.type, now); }
    try { window.localStorage.setItem('astrahealth-alert-cooldowns', JSON.stringify(lastShown)); } catch { /* Continue for this page even when storage is unavailable. */ }
    const created = eligible.map((item, index) => ({ ...item, id: `${now}-${index}-${item.type}` }));
    setNotifications(previous => [...previous, ...created].slice(-4));
    for (const item of created) {
      const timer = window.setTimeout(() => setNotifications(previous => previous.filter(current => current.id !== item.id)), 8500);
      notificationTimersRef.current.push(timer);
    }
  }, [analysis, newest?.record_id]);

  useEffect(() => {
    if (summary?.follow_up.status !== 'follow_up_requested') return;
    const type = 'wellbeing:follow_up_requested';
    const now = Date.now();
    let lastShown: Record<string, number> = {};
    try { lastShown = JSON.parse(window.localStorage.getItem('astrahealth-alert-cooldowns') ?? '{}') as Record<string, number>; } catch { lastShown = {}; }
    if (now - Math.max(lastShown[type] ?? 0, alertCooldownsRef.current.get(type) ?? 0) < 180_000) return;
    lastShown[type] = now;
    alertCooldownsRef.current.set(type, now);
    try { window.localStorage.setItem('astrahealth-alert-cooldowns', JSON.stringify(lastShown)); } catch { /* Continue for this page even when storage is unavailable. */ }
    const notification: ToastAlert = { id: `${now}-${type}`, type, level: 'warning', title: 'Wellbeing follow-up requested', detail: summary.follow_up.guidance || 'Open the wellbeing section to review the latest assessment.' };
    setNotifications(previous => [...previous, notification].slice(-4));
    const timer = window.setTimeout(() => setNotifications(previous => previous.filter(item => item.id !== notification.id)), 8500);
    notificationTimersRef.current.push(timer);
  }, [summary]);

  useEffect(() => {
    let active = true;
    apiRequest<{ run_id: string; scenario_id: ScenarioId; available_scenarios: ScenarioId[]; scenario_transition: { active: boolean; step: number; total_steps: number } }>('/api/v1/simulation/runs/demo-run/scenario')
      .then(result => {
        if (active && !scenarioChangeRef.current) {
          scenarioRef.current = result.scenario_id;
          setScenario(result.scenario_id);
          setScenarioTransition(result.scenario_transition);
          setScenarioReady(true);
        }
      })
      .catch(reason => {
        if (active && !scenarioChangeRef.current) setScenarioError(reason instanceof Error ? reason.message : 'Could not load the active scenario. Choose a scenario to continue.');
      });
    return () => { active = false; };
  }, []);

  const fetchSample = useCallback(async () => {
    if (!liveRef.current || inFlightRef.current || scenarioChangeRef.current || !scenarioReady || document.visibilityState !== 'visible') return;
    const requestedSubject = subjectRef.current;
    inFlightRef.current = true;
    setFeedState('connecting'); setFeedMessage('');
    try {
      const result = await apiRequest<SimulationResponse>(`/api/v1/simulation/runs/demo-run/astronauts/${requestedSubject}/inputs`);
      const observation = result.items[0];
      if (!observation) throw new Error('The simulator returned no observation.');
      if (subjectRef.current === requestedSubject && result.scenario_id === scenarioRef.current) {
        setScenarioTransition(result.scenario_transition);
        currentRecordIdRef.current = observation.record_id;
        setSamples(previous => [observation, ...previous.filter(item => item.record_id !== observation.record_id)].slice(0, 8));
        if (liveRef.current) setFeedState('live');
        setAnalysis({ recordId: observation.record_id, state: 'loading' });
        try {
          const analyzed = await apiRequest<AnalysisResponse>(`/api/v1/simulation/runs/${encodeURIComponent(result.run_id)}/astronauts/${encodeURIComponent(requestedSubject)}/analysis`, undefined, {
            method: 'POST', body: JSON.stringify({ scenario_id: result.scenario_id, observation }),
          });
          if (subjectRef.current === requestedSubject && currentRecordIdRef.current === observation.record_id) {
            setAnalysis({ recordId: observation.record_id, state: 'ready', result: analyzed });
            try {
              let shared: { consent?: boolean; topics?: string[] } | null = null;
              try { shared = profile ? JSON.parse(window.sessionStorage.getItem(`astrahealth-shared-topics:${profile.astronaut_id}`) ?? 'null') as { consent?: boolean; topics?: string[] } | null : null; } catch { /* Ignore malformed optional sharing preferences. */ }
              const recommendationResult = await apiRequest<RecommendationResponse>('/api/v1/chatbot/recommendations/evaluate', token, {
                method: 'POST',
                body: JSON.stringify({
                  dashboard: {
                    run_id: analyzed.run_id, scenario_id: analyzed.scenario_id, source_subject_id: analyzed.astronaut_id,
                    record_id: analyzed.record_id, observed_at: analyzed.observed_at,
                    rules: { status: analyzed.rules.status, alerts: analyzed.rules.alerts },
                    anomaly: { status: analyzed.anomaly.status, is_anomaly: analyzed.anomaly.is_anomaly, model_version: analyzed.anomaly.model_version },
                    forecast: { status: analyzed.forecast.status, target_time: analyzed.forecast.target_time, model_version: analyzed.forecast.model_version },
                  },
                  ...(shared?.consent && shared.topics?.length ? { conversation: { consent: true, topics: shared.topics } } : {}),
                }),
              });
              if (subjectRef.current === requestedSubject && currentRecordIdRef.current === observation.record_id) {
                recommendationResult.recommendations.forEach(item => window.dispatchEvent(new CustomEvent('astrahealth:recommendation', { detail: item })));
              }
            } catch { /* Recommendation service can be unavailable without interrupting live readings. */ }
          }
        } catch (reason) {
          if (subjectRef.current === requestedSubject && currentRecordIdRef.current === observation.record_id) {
            setAnalysis({ recordId: observation.record_id, state: 'unavailable', message: reason instanceof Error ? reason.message : 'Analysis is unavailable.' });
          }
        }
      }
    } catch (reason) {
      if (liveRef.current) setFeedState('error');
      setFeedMessage(reason instanceof Error ? reason.message : 'The simulated inputs service is unavailable.');
    } finally { inFlightRef.current = false; }
  }, [profile, scenarioReady, token]);

  const pauseFeed = useCallback((message = 'Live updates paused.') => {
    liveRef.current = false;
    if (pollTimerRef.current !== null) window.clearInterval(pollTimerRef.current);
    pollTimerRef.current = null;
    setLive(false);
    setFeedState('paused');
    setFeedMessage(message);
  }, []);

  const resumeFeed = useCallback(() => {
    if (document.visibilityState !== 'visible') return;
    liveRef.current = true;
    setLive(true);
    setFeedState('connecting');
    setFeedMessage('');
    void fetchSample();
  }, [fetchSample]);

  useEffect(() => {
    liveRef.current = live;
    if (!live || document.visibilityState !== 'visible') return;
    if (!bootstrapRequestRef.current) {
      bootstrapRequestRef.current = true;
      void fetchSample();
    }
    pollTimerRef.current = window.setInterval(() => { void fetchSample(); }, 3000);
    return () => {
      if (pollTimerRef.current !== null) window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    };
  }, [fetchSample, live, scenarioReady]);

  useEffect(() => {
    const pauseWhenHidden = () => {
      if (document.visibilityState === 'hidden' && liveRef.current) {
        pauseFeed('Live updates paused because this tab is hidden. Resume to continue sampling.');
      }
    };
    document.addEventListener('visibilitychange', pauseWhenHidden);
    if (document.visibilityState === 'hidden') pauseFeed('Live updates paused because this tab is hidden. Resume to continue sampling.');
    return () => {
      document.removeEventListener('visibilitychange', pauseWhenHidden);
      liveRef.current = false;
      if (pollTimerRef.current !== null) window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    };
  }, [pauseFeed]);

  function selectRegion(id: string) { setSelectedRegion(id); }
  async function selectScenario(next: ScenarioId) {
    if ((next === scenarioRef.current && scenarioReady) || scenarioChangeRef.current) return;
    const previous = scenarioRef.current;
    scenarioRef.current = next;
    scenarioChangeRef.current = true;
    currentRecordIdRef.current = '';
    setScenario(next); setScenarioTransition({ active: true, step: 0, total_steps: 8 }); setScenarioRampStarted(true); setScenarioBusy(true); setScenarioError(''); setSamples([]); setAnalysis(null);
    try {
      await apiRequest<{ run_id: string; scenario_id: ScenarioId }>('/api/v1/simulation/runs/demo-run/scenario', undefined, {
        method: 'PUT', body: JSON.stringify({ scenario_id: next }),
      });
      if (scenarioRef.current === next) {
        scenarioChangeRef.current = false;
        setScenarioBusy(false); setScenarioReady(true);
        if (liveRef.current) void fetchSample();
      }
    } catch (reason) {
      if (scenarioRef.current === next) {
        scenarioRef.current = previous;
        setScenario(previous);
        setScenarioError(reason instanceof Error ? reason.message : 'Could not change simulator scenario.');
        try {
          await apiRequest('/api/v1/simulation/runs/demo-run/scenario', undefined, {
            method: 'PUT', body: JSON.stringify({ scenario_id: previous }),
          });
          scenarioChangeRef.current = false;
          setScenarioBusy(false);
        } catch {
          scenarioChangeRef.current = false;
          setScenarioBusy(false);
          setScenarioError('Scenario update could not be confirmed. Reload the dashboard before continuing.');
        }
      }
    }
  }
  function regionKeyDown(event: KeyboardEvent<SVGGElement>, id: string) {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectRegion(id); }
  }

  return <main className="page-content dashboard-content">
    <div className="alert-stack" aria-live="assertive" aria-label="Recent alerts">{notifications.map(alert => <article className={`alert-toast alert-toast--${alert.level}`} key={alert.id}><StateIcon risk={alert.level}/><div><strong>{alert.title}</strong><span>{alert.detail}</span></div><button type="button" aria-label="Dismiss alert" onClick={() => setNotifications(previous => previous.filter(item => item.id !== alert.id))}>×</button></article>)}</div>
    <div className="page-heading dashboard-heading"><div><p className="eyebrow">MISSION HEALTH · OVERVIEW</p><h1>Monitoring overview</h1><p className="lead">Measurements and assessment status for {profile?.display_name}.</p></div><div className="dashboard-heading__meta"><div className="mission-chip"><span className="status-dot" />{profile?.mission || 'Mission not set'}</div><div className="live-control"><span className={`live-indicator live-indicator--${feedState}`}><i aria-hidden="true" />{feedState === 'live' ? 'Live simulated inputs' : feedState === 'connecting' ? 'Connecting' : feedState === 'error' ? 'Service unavailable' : 'Updates paused'}</span><Link className="button button--primary" to="/mission-control">Messages &amp; support</Link>{live ? <button className="button button--secondary" onClick={() => pauseFeed()}>Pause live feed</button> : <button className="button button--primary" onClick={resumeFeed}>Resume live feed</button>}</div></div></div>
    <div className="dashboard-grid dashboard-grid--monitor">
      <section className="panel body-map-panel"><div className="panel-heading"><div><p className="eyebrow">BODY OVERVIEW</p><h2>Measurement groups</h2></div><span className="status-pill status-pill--neutral">Navigation only</span></div><p className="muted body-map-intro">Select a highlighted area to filter its related readings. This map does not assess health.</p>
        <div className="body-map-wrap body-map-wrap--image">
          <img className="body-map-image" src="/human-scan.png" alt="Glowing human scan used to locate measurement groups" />
          <svg className="body-map-hotspots" viewBox="0 0 270 340" role="group" aria-labelledby="body-map-title body-map-desc">
            <title id="body-map-title">Human scan measurement map</title>
            <desc id="body-map-desc">Select the head, chest, lung, or abdomen markers to filter related readings. A red pulsing marker means a rule alert or a large deviation from simulator reference is present in that region.</desc>
            <RegionHotspot x={135} y={84} id="activity" selected={selectedRegion} label="Activity & wellbeing" labelX={210} labelY={83} hasAlert={regionHasAlert(['sleep_duration', 'mood', 'exercise_duration'])} onChoose={selectRegion} onKeyDown={regionKeyDown}/>
            <RegionHotspot x={135} y={140} id="circulation" selected={selectedRegion} label="Heart & circulation" labelX={210} labelY={126} hasAlert={regionHasAlert(['heart_rate', 'systolic_pressure', 'diastolic_pressure', 'hrv_rmssd'])} onChoose={selectRegion} onKeyDown={regionKeyDown}/>
            <RegionHotspot x={135} y={170} id="respiratory" selected={selectedRegion} label="Respiratory" labelX={210} labelY={169} hasAlert={regionHasAlert(['spo2'])} onChoose={selectRegion} onKeyDown={regionKeyDown}/>
            <RegionHotspot x={135} y={200} id="general" selected={selectedRegion} label="General health" labelX={210} labelY={212} hasAlert={regionHasAlert(['body_temperature', 'glucose'])} onChoose={selectRegion} onKeyDown={regionKeyDown}/>
          </svg>
        </div>
        <div className="related-readings"><h3>{selectedRegionInfo.title}</h3>{related.map(field => { const reading = newest ? getReading(newest, field) : null; return <div className="related-row" key={field.key}><span>{field.label}</span><strong>{reading ? pretty(reading.value, reading.unit) : 'Unavailable'}</strong></div>; })}</div>
        <CompoundRiskIndex observation={newest ?? null} analysis={latestAnalysis}/>
      </section>

      <div className="telemetry-column">
        <section className="panel readings-panel"><div className="panel-heading readings-heading"><div className="readings-title"><p className="eyebrow">PHYSIOLOGICAL</p><h2>Physical measurements</h2></div><FixtureControls subject={subject} scenario={scenario} scenarioBusy={scenarioBusy} scenarioError={scenarioError} feedState={feedState} feedMessage={feedMessage} newest={newest ?? null} windowAvailable={latestAnalysis?.rules.window_available ?? 0} scenarioTransition={scenarioTransition} scenarioRampStarted={scenarioRampStarted} onSubjectChange={nextSubject => { subjectRef.current = nextSubject; currentRecordIdRef.current = ''; setSubject(nextSubject); setSamples([]); setAnalysis(null); setFeedMessage(''); }} onScenarioChange={nextScenario => { void selectScenario(nextScenario); }} /></div>
          <div className="metric-grid metric-grid--physical">{physicalFields.map(field => { const reading = newest ? getReading(newest, field) : null; return <Metric key={field.key} field={field.label} fieldKey={field.key} group={field.group} samples={samples} risk={riskForField(field.key)} reading={reading} sampleId={newest?.record_id} />; })}</div>
          <HeartRateTrend samples={samples} risk={riskForField('heart_rate')}/>
        </section>
        <section className="panel wellbeing-panel"><div className="panel-heading"><div><p className="eyebrow">SELF-REPORTED INPUTS</p><div className="section-state-heading"><h2>Activity and wellbeing</h2><StateIcon risk={groupRisk(wellbeingFields.map(field => field.key))}/><span className={`state-word state-word--${groupRisk(wellbeingFields.map(field => field.key))}`}>{riskLabel(groupRisk(wellbeingFields.map(field => field.key)))}</span></div></div><span className="status-pill status-pill--neutral">Simulator values</span></div><div className="metric-grid metric-grid--wellbeing">{wellbeingFields.map(field => { const reading = newest ? getReading(newest, field) : null; return <Metric key={field.key} field={field.label} fieldKey={field.key} group={field.group} samples={samples} risk={riskForField(field.key)} reading={reading} sampleId={newest?.record_id} />; })}</div></section>
        <section className="panel cabin-panel"><div className="panel-heading"><div><p className="eyebrow">ENVIRONMENT</p><h2>Cabin conditions</h2></div><span className="status-pill status-pill--neutral">Fixture data</span></div><div className="metric-grid metric-grid--environment">{environmentFields.map(field => { const reading = newest ? getReading(newest, field) : null; return <Metric key={field.key} field={field.label} fieldKey={field.key} group={field.group} samples={samples} risk={riskForField(field.key)} reading={reading} sampleId={newest?.record_id} />; })}</div></section>
        <AnalysisPanel analysis={analysis} newestRecordId={newest?.record_id ?? null} observation={newest ?? null} />
        <section className="panel assessment-summary">
          <div className="panel-heading"><div><p className="eyebrow">ASSESSMENT SERVICE</p><h2>Wellbeing status</h2></div><span className={`status-pill status-pill--${summaryState === 'available' ? 'active' : 'neutral'}`}>{summaryState.replace('_', ' ')}</span></div>
          <div className="assessment-summary__content">
            {summaryError ? <p className="notice notice--error">{summaryError}</p> : summary?.availability === 'not_assessed' ? <div className="empty-state"><p>No completed PHQ-9 assessment is available.</p><Link to="/wellbeing">Start assessment</Link></div> : summary?.availability === 'stale' ? <p className="notice notice--subtle">The most recent assessment is marked stale by the service. Review its timestamp and result history.</p> : summary ? <>
              <p className="summary-copy">Latest summary returned by the assessment service.</p>
              <div className={`followup-box ${summary.follow_up.status === 'follow_up_requested' ? 'followup-box--requested' : ''}`}><strong>{summary.follow_up.status === 'follow_up_requested' ? 'Follow-up requested' : summary.follow_up.status === 'unknown' ? 'Follow-up status unknown' : 'No follow-up flag returned'}</strong>{summary.follow_up.guidance && <p>{summary.follow_up.guidance}</p>}</div>
              <div className="assessment-summary__details"><p className="muted summary-time">Updated {summary.updated_at ? time(summary.updated_at) : 'time unavailable'}</p><p className="summary-limit">A missing follow-up flag does not establish overall safety.</p></div>
            </> : <p className="muted">Loading assessment availability…</p>}
            <Link className="button button--secondary button--full" to="/wellbeing">Open wellbeing</Link>
          </div>
        </section>
      </div>
    </div>
  </main>;
}

function FixtureControls({ subject, scenario, scenarioBusy, scenarioError, feedState, feedMessage, newest, windowAvailable, scenarioTransition, scenarioRampStarted, onSubjectChange, onScenarioChange }: {
  subject: string; scenario: ScenarioId; scenarioBusy: boolean; scenarioError: string;
  feedState: 'connecting' | 'live' | 'paused' | 'error'; feedMessage: string; newest: Observation | null;
  windowAvailable: number; scenarioTransition: { active: boolean; step: number; total_steps: number }; scenarioRampStarted: boolean;
  onSubjectChange: (subject: string) => void; onScenarioChange: (scenario: ScenarioId) => void;
}) {
  const feedLabel = feedState === 'live' ? 'Live' : feedState === 'connecting' ? 'Connecting' : feedState === 'error' ? 'Unavailable' : 'Paused';
  const rampLabel = scenarioTransition.active ? `Ramp ${scenarioTransition.step}/${scenarioTransition.total_steps}` : 'Ramp complete';
  return <div className="fixture-controls">
    <div className="fixture-controls__top"><span className="fixture-label">Simulated fixture</span><span className={`live-indicator live-indicator--${feedState}`}><i aria-hidden="true" />{scenarioBusy ? 'Changing scenario' : feedLabel}</span></div>
    <div className="fixture-controls__selectors">
      <label htmlFor="demo-subject"><span>Astronaut</span><select id="demo-subject" value={subject} onChange={event => onSubjectChange(event.target.value)}><option value="A01">A01</option><option value="AST-001">AST-001</option></select></label>
      <label htmlFor="demo-scenario"><span>Scenario</span><select id="demo-scenario" value={scenario} disabled={scenarioBusy} onChange={event => onScenarioChange(event.target.value as ScenarioId)}>{scenarioOptions.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
    </div>
    <div className="fixture-controls__meta"><span>3s refresh</span><span>Alert window {windowAvailable}/8</span>{scenarioRampStarted && <span>{rampLabel}</span>}{newest && <span>Last {time(newest.observed_at)}</span>}</div>
    <span className="fixture-controls__note">Fixture values · not sensor telemetry</span>
    {scenarioError && <span className="sync-error" role="alert">{scenarioError}</span>}
    {feedMessage && <span className={feedState === 'error' ? 'sync-error' : 'sync-note'} role={feedState === 'error' ? 'alert' : 'status'}>{feedMessage}</span>}
  </div>;
}

function AnalysisPanel({ analysis, newestRecordId, observation }: { analysis: { recordId: string; state: 'loading' | 'unavailable' | 'ready'; result?: AnalysisResponse; message?: string } | null; newestRecordId: string | null; observation: Observation | null }) {
  const current = analysis && analysis.recordId === newestRecordId ? analysis : null;
  const result = current?.state === 'ready' ? current.result : undefined;
  return <section className="panel model-analysis" aria-labelledby="analysis-title">
    <div className="panel-heading"><div><p className="eyebrow">AUTOMATED ANALYSIS</p><h2 id="analysis-title">Rules and model outputs</h2><p className="analysis-panel-note">Model results are advisory and trained on simulated data.</p></div><span className={`status-pill ${result?.analysis_status === 'complete' ? 'status-pill--active' : 'status-pill--neutral'}`}>{current?.state === 'loading' ? 'Analyzing sample' : current?.state === 'unavailable' ? 'Unavailable' : result?.analysis_status === 'complete' ? 'All components available' : result ? 'Partial results' : 'Waiting for sample'}</span></div>
    {current?.state === 'unavailable' && <p className="notice notice--subtle" role="status">Measurements continue to update, but this sample could not be analyzed. {current.message}</p>}
    {!current && <p className="muted analysis-waiting">{newestRecordId ? 'Waiting for analysis of the latest sample…' : 'Analysis appears when the first sample arrives.'}</p>}
    {current?.state === 'loading' && <p className="muted analysis-waiting" role="status">Checking rule alerts and model availability for this sample…</p>}
    {!result && <div className="analysis-grid analysis-grid--reserved" aria-label="Loading analysis models" aria-busy="true">
      <AnalysisSkeleton label="Rule assessment" />
      <AnalysisSkeleton label="Anomaly detection" />
      <AnalysisSkeleton label="Next-step forecast" forecast />
    </div>}
    {result && <div className="analysis-grid" aria-busy="false">
      <article className="analysis-card"><div className="analysis-card__heading"><div><span className="eyebrow">RULE ENGINE</span><h3>Current rule assessment</h3></div><span className={`severity-pill severity-pill--${result.rules.overall_level ?? 'unknown'}`}>{result.rules.overall_level ?? 'Unknown'}</span></div>
        <p className="analysis-model-meta">{result.rules.version} · demonstration thresholds</p>
        {result.rules.alerts.length ? <ul className="rule-alert-list">{result.rules.alerts.map((alert, index) => <li key={`${alert.code}-${index}`} className={`rule-alert rule-alert--${alert.severity}`}><strong>{alert.message}</strong><span>{alert.system.replaceAll('_', ' ')}</span>{alert.evidence.length > 0 && <small>{alert.evidence.map(item => `${item.field.replaceAll('_', ' ')}: ${item.value === null ? 'Unavailable' : `${item.value} ${item.unit}`} · ${item.quality}`).join(' · ')}</small>}</li>)}</ul> : <p className="analysis-empty">No rule alerts were returned for this sample. This is not a safety determination.</p>}
        <p className="analysis-quality">Inputs: {result.rules.input_quality.valid} valid · {result.rules.input_quality.missing} missing · {result.rules.input_quality.invalid} invalid · alert window {result.rules.window_available}/{result.rules.window_size}</p>
      </article>
      <article className="analysis-card"><div className="analysis-card__heading"><div><span className="eyebrow">ANOMALY DETECTION</span><h3>Isolation Forest</h3></div><span className={`severity-pill severity-pill--${result.anomaly.status}`}>{statusLabel(result.anomaly.status)}</span></div>
        {result.anomaly.status === 'available' ? <><p className={`model-verdict ${result.anomaly.is_anomaly ? 'model-verdict--flagged' : 'model-verdict--clear'}`}><i aria-hidden="true" />{result.anomaly.is_anomaly ? 'Pattern differs from training data' : 'No unusual pattern flagged'}</p><div className="anomaly-score"><span>Decision score</span><strong>{result.anomaly.score?.toFixed(4) ?? 'Unavailable'}</strong></div><p className="analysis-model-meta">{result.anomaly.score_meaning}</p><p className="analysis-quality">Model {result.anomaly.model_version ?? 'version unreported'} · one sample</p></> : <StatusDetail model="Isolation Forest" status={result.anomaly.status} reason={result.anomaly.reason} inputQuality={result.rules.input_quality} />}
      </article>
      <article className="analysis-card analysis-card--forecast"><div className="analysis-card__heading"><div><span className="eyebrow">NEXT-STEP FORECAST</span><h3>LSTM projection</h3></div><span className={`severity-pill severity-pill--${result.forecast.status}`}>{statusLabel(result.forecast.status)}</span></div>
        {result.forecast.status === 'available' ? <><div className="forecast-summary"><p className="analysis-result-title">Projected from the latest 24 samples</p><p className="analysis-model-meta">Target {result.forecast.target_time ? time(result.forecast.target_time) : 'time unavailable'} · {result.forecast.horizon_seconds ?? result.forecast.sample_period_seconds}s horizon · model {result.forecast.model_version ?? 'version unreported'}</p></div><div className="forecast-values">{Object.entries(result.forecast.values ?? {}).map(([key, value]) => <ForecastMetric key={key} fieldKey={key} forecastValue={value.value} unit={value.unit} observation={observation} />)}</div></> : <StatusDetail model="LSTM projection" status={result.forecast.status} reason={result.forecast.reason} windowAvailable={result.forecast.window_available} windowRequired={result.forecast.window_required} samplePeriod={result.forecast.sample_period_seconds} inputQuality={result.rules.input_quality} />}
      </article>
    </div>}
    {result && <p className="analysis-timestamp">Analyzed {time(result.analyzed_at)} · {scenarioOptions.find(option => option.id === result.scenario_id)?.label ?? result.scenario_id} · observation {result.record_id}</p>}
  </section>;
}

function AnalysisSkeleton({ label, forecast = false }: { label: string; forecast?: boolean }) {
  return <article className={`analysis-card analysis-skeleton ${forecast ? 'analysis-card--forecast' : ''}`} aria-hidden="true">
    <div className="analysis-card__heading"><div><span className="eyebrow">{label}</span><i className="skeleton-line skeleton-line--title" /></div><i className="skeleton-pill" /></div>
    <i className="skeleton-line skeleton-line--wide" />
    <i className="skeleton-line skeleton-line--medium" />
    {forecast && <div className="analysis-skeleton__metrics">{Array.from({ length: 4 }, (_, index) => <i className="skeleton-metric" key={index} />)}</div>}
  </article>;
}

function statusLabel(status: string) {
  return ({ available: 'Available', warming_up: 'Warming up', insufficient_data: 'Insufficient data', unavailable: 'Unavailable' } as Record<string, string>)[status] ?? status;
}

function ForecastMetric({ fieldKey, forecastValue, unit, observation }: { fieldKey: string; forecastValue: number; unit: string; observation: Observation | null }) {
  const field = fields.find(candidate => candidate.key === fieldKey);
  const current = field && observation ? getReading(observation, field) : null;
  const hasCurrent = current?.quality === 'valid' && current.value !== null;
  const change = hasCurrent ? forecastValue - current.value! : null;
  const changeText = change === null ? 'No current comparison' : `${change > 0 ? '+' : ''}${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(change)} ${unit}`;
  return <div className="forecast-value"><span className="forecast-value__label">{field?.label ?? fieldKey.replaceAll('_', ' ')}</span><strong>{pretty(forecastValue, unit)}</strong><small>{hasCurrent ? `Now ${pretty(current.value, unit)} · Δ ${changeText}` : changeText}</small></div>;
}

function StatusDetail({ model, status, reason, windowAvailable, windowRequired, samplePeriod, inputQuality }: { model: string; status: string; reason: string | null; windowAvailable?: number; windowRequired?: number; samplePeriod?: number; inputQuality?: { valid: number; missing: number; invalid: number } }) {
  if (status === 'warming_up') return <div className="model-state-block"><p className="analysis-state-copy">Collecting complete samples for the forecast window: {windowAvailable ?? 0} of {windowRequired ?? 24}. At {samplePeriod ?? 3}-second intervals, projections can begin in about {(windowRequired ?? 24) * (samplePeriod ?? 3)} seconds.</p><progress className="forecast-progress" value={windowAvailable ?? 0} max={windowRequired ?? 24} aria-label={`LSTM history: ${windowAvailable ?? 0} of ${windowRequired ?? 24} samples`} /></div>;
  if (status === 'insufficient_data') return <p className="analysis-state-copy">{model} needs all 17 required measurements to be valid. This sample has {inputQuality?.valid ?? 0} valid, {inputQuality?.missing ?? 0} missing, and {inputQuality?.invalid ?? 0} invalid.</p>;
  const detail = reason === 'artifact_missing' ? `${model} artifacts have not been installed in the simulator service.`
    : reason === 'manifest_missing' ? 'The model manifest is missing, so feature order and cadence cannot be verified.'
      : reason === 'manifest_invalid' ? 'The model manifest could not be read. Recheck the deployed manifest file.'
        : reason === 'feature_order_mismatch' ? 'The model feature order differs from the service configuration.'
          : reason === 'window_mismatch' ? 'The model history window differs from the service configuration.'
            : reason === 'cadence_mismatch' ? 'The model sampling cadence differs from the service configuration.'
              : reason === 'dependencies_missing' ? 'The simulator image is missing its ML runtime packages.'
                : reason === 'dependency_version_mismatch' ? 'The simulator ML package versions do not match the model manifest.'
                  : 'The model did not return a result for this sample. Check simulator logs for inference errors.';
  return <p className="analysis-state-copy">{detail}</p>;
}

function riskLabel(risk: RiskLevel) {
  return ({ normal: 'Nominal', caution: 'Watch', warning: 'Elevated', critical: 'Critical', unknown: 'No status' } as Record<RiskLevel, string>)[risk];
}

function StateIcon({ risk }: { risk: RiskLevel }) {
  return <svg className={`state-icon state-icon--${risk}`} viewBox="0 0 20 20" aria-hidden="true">
    {risk === 'normal' ? <><circle cx="10" cy="10" r="8"/><path d="m6 10 2.5 2.5L14 7"/></>
      : risk === 'caution' ? <><circle cx="10" cy="10" r="8"/><path d="M10 5.5v5M10 13.8h.01"/></>
        : risk === 'warning' || risk === 'critical' ? <><path d="M10 2.2 18 17H2L10 2.2Z"/><path d="M10 7v4.5M10 14.1h.01"/></>
          : <><circle cx="10" cy="10" r="8"/><path d="M6.5 10h7"/></>}
  </svg>;
}

function Metric({ field, fieldKey, group, samples, risk, reading, sampleId }: { field: string; fieldKey: string; group: keyof Pick<Observation, 'physiological' | 'self_assessment' | 'environment'>; samples: Observation[]; risk: RiskLevel; reading: Reading | null; sampleId?: string }) {
  const values = samples.slice(0, 8).reverse().map(sample => sample[group][fieldKey]?.value).filter((value): value is number => value !== null && value !== undefined && Number.isFinite(value));
  const sensorAvailable = reading?.quality === 'valid';
  const numberOnly = fieldKey === 'hrv_rmssd' || fieldKey === 'gravity';
  const referenceLabel = reading?.unit && !numberOnly && !['spo2', 'humidity', 'glucose', 'noise', 'radiation_dose_rate'].includes(fieldKey) && group !== 'self_assessment'
    ? ` · reference ${pretty(simulatorBaselines[fieldKey], reading.unit)}` : '';
  return <article className={`metric-card metric-card--${risk}`}>
    <div className="metric-card__head"><span className="metric-label">{field}</span><span className={`sensor-light ${sensorAvailable ? 'sensor-light--on' : 'sensor-light--off'}`} role="img" aria-label={sensorAvailable ? 'Input available' : 'Input unavailable'} title={sensorAvailable ? 'Input available' : 'Input unavailable'} /></div>
    {numberOnly ? <MetricReadout reading={reading} /> : <strong className={!reading || reading.quality !== 'valid' ? 'metric-value--missing' : ''}>{reading ? pretty(reading.value, reading.unit) : 'Waiting for sample'}</strong>}
    {numberOnly ? <span className="metric-readout-spacer" aria-hidden="true"/> : group === 'self_assessment' ? <ActivityEmoji risk={risk}/> : fieldKey === 'spo2' || fieldKey === 'humidity' ? <PercentageRing value={reading?.value ?? null}/> : fieldKey === 'body_temperature' || fieldKey === 'cabin_temperature' ? <MiniBars values={values} baseline={simulatorBaselines[fieldKey]} sampleId={sampleId}/> : fieldKey === 'radiation_dose_rate' || fieldKey === 'noise' || fieldKey === 'glucose' ? <RangeMeter value={reading?.value ?? null} baseline={simulatorBaselines[fieldKey]} max={fieldKey === 'radiation_dose_rate' ? 12 : fieldKey === 'noise' ? 100 : 200}/> : <Sparkline values={values} baseline={simulatorBaselines[fieldKey]} sampleId={sampleId}/>}
    <div className="metric-card__foot"><span className="quality-label">{riskLabel(risk)}{reading ? ` · ${reading.quality}` : ' · waiting'}{referenceLabel}</span><MetricInfo field={field} info={metricInformation[fieldKey]}/></div>
  </article>;
}

function MetricInfo({ field, info }: { field: string; info?: { what: string; why: string } }) {
  const tooltipId = `metric-info-${field.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  const details = info ?? { what: 'Simulated mission measurement.', why: 'Use it as context when reviewing related mission trends.' };
  return <span className="metric-info">
    <button className="metric-info__trigger" type="button" aria-label={`Information about ${field}`} aria-describedby={tooltipId}>
      <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.4"/><path d="M10 9v4M10 6.5h.01"/></svg>
    </button>
    <span className="metric-info__tooltip" id={tooltipId} role="tooltip"><strong>{field}</strong><span>{details.what}</span><span><b>Why it matters:</b> {details.why}</span></span>
  </span>;
}

function MetricReadout({ reading }: { reading: Reading | null }) {
  if (!reading || reading.value === null) return <strong className="metric-value--missing metric-readout__missing">{reading ? 'Unavailable' : 'Waiting for sample'}</strong>;
  return <div className="metric-readout"><strong>{new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(reading.value)}</strong><span>{reading.unit}</span></div>;
}

function CompoundRiskIndex({ observation, analysis }: { observation: Observation | null; analysis?: AnalysisResponse }) {
  const domains = [
    { id: 'activity', label: 'Activity & wellbeing', keys: ['sleep_duration', 'mood', 'exercise_duration'] },
    { id: 'circulation', label: 'Circulation', keys: ['heart_rate', 'systolic_pressure', 'diastolic_pressure', 'hrv_rmssd'] },
    { id: 'respiratory', label: 'Respiratory', keys: ['spo2'] },
    { id: 'general', label: 'General health', keys: ['body_temperature', 'glucose'] },
    { id: 'environment', label: 'Cabin environment', keys: environmentFields.map(field => field.key) },
  ];
  const scoreForKey = (key: string) => {
    const field = fields.find(item => item.key === key);
    const reading = field && observation ? observation[field.group][key] : undefined;
    if (!reading || reading.quality !== 'valid') return null;
    const points = analysis?.rules.alerts.flatMap(alert => alert.evidence.some(item => item.field === key && item.quality === 'valid')
      ? [alert.severity === 'critical' ? 100 : alert.severity === 'warning' ? 65 : 35] : []) ?? [];
    return Math.max(points.length ? Math.max(...points) : 0, baselineDeviationScore(key, observation));
  };
  const domainScores = domains.map(domain => {
    const scores = domain.keys.map(scoreForKey).filter((value): value is number => value !== null);
    return { ...domain, score: scores.length ? Math.max(...scores) : null, validCount: scores.length };
  });
  const available = Boolean(observation && analysis?.rules.status === 'available' && domainScores.some(domain => domain.score !== null));
  const scoredDomains = domainScores.filter((domain): domain is typeof domain & { score: number } => domain.score !== null);
  const mean = scoredDomains.length ? scoredDomains.reduce((total, domain) => total + domain.score, 0) / scoredDomains.length : 0;
  const peak = scoredDomains.length ? Math.max(...scoredDomains.map(domain => domain.score)) : 0;
  const ruleIndex = Math.round(mean * 0.6 + peak * 0.4);
  const anomalyFlag = analysis?.anomaly.status === 'available' && analysis.anomaly.is_anomaly === true;
  const score = available ? Math.max(ruleIndex, anomalyFlag ? 60 : 0) : null;
  const band = score === null ? 'unknown' : score < 15 ? 'nominal' : score < 40 ? 'watch' : score < 70 ? 'elevated' : 'critical';
  const bandLabel = { unknown: 'Waiting', nominal: 'Nominal', watch: 'Watch', elevated: 'Elevated', critical: 'Critical' }[band];
  const healthDomains = domainScores.slice(0, 4).filter(domain => domain.score !== null);
  const healthScore = healthDomains.length ? Math.round(healthDomains.reduce((total, domain) => total + (domain.score ?? 0), 0) / healthDomains.length) : null;
  const environmentScore = domainScores[4].score;
  const validCount = domainScores.reduce((total, domain) => total + domain.validCount, 0);
  const expectedCount = domains.reduce((total, domain) => total + domain.keys.length, 0);
  const circumference = 2 * Math.PI * 40;
  const offset = score === null ? circumference : circumference * (1 - score / 100);
  return <section className={`cri-panel cri-panel--${band}`} aria-labelledby="cri-title">
    <div className="cri-panel__heading"><div><p className="eyebrow">COMBINED SIGNAL</p><h3 id="cri-title">Compound Risk Index</h3></div><span className={`cri-band cri-band--${band}`}>{bandLabel}</span></div>
    {score === null ? <p className="cri-empty">{!observation ? 'Waiting for the first measurement.' : analysis?.rules.status === 'unavailable' ? 'Rule assessment is unavailable for this sample.' : 'Waiting for current rule assessment.'}</p> : <>
      <div className="cri-score-row"><svg className="cri-ring" viewBox="0 0 100 100" role="img" aria-label={`Compound Risk Index ${score} out of 100, ${bandLabel.toLowerCase()}`}>
        <circle className="cri-ring__track" cx="50" cy="50" r="40"/><circle className="cri-ring__value" cx="50" cy="50" r="40" strokeDasharray={circumference} strokeDashoffset={offset}/><text x="50" y="56" textAnchor="middle">{score}</text>
      </svg><div className="cri-score-copy"><strong>0–100</strong><span>Higher values mean more current rule-based risk.</span><span>{validCount} of {expectedCount} measurements valid</span></div></div>
      <div className="cri-sub-scores"><CriSubscore label="Health" score={healthScore}/><CriSubscore label="Environment" score={environmentScore}/></div>
      {anomalyFlag && <p className="cri-anomaly-note">Anomaly model flagged this sample; the index floor is 60.</p>}
      <p className="cri-method">Combines rule alerts (caution 35, warning 65, critical 100) with deviations beyond 3σ of simulator baselines. Formula: 60% mean domain score + 40% peak. Anomaly flag sets a 60-point floor. Demo references only; not clinical ranges or a diagnosis.</p>
    </>}
  </section>;
}

function CriSubscore({ label, score }: { label: string; score: number | null }) {
  const band = score === null ? 'unknown' : score < 15 ? 'nominal' : score < 40 ? 'watch' : score < 70 ? 'elevated' : 'critical';
  return <div className={`cri-subscore cri-subscore--${band}`}><div><span>{label}</span><strong>{score === null ? '—' : score}</strong></div><span className="cri-subscore__track"><i style={{ width: `${score ?? 0}%` }}/></span></div>;
}

function ActivityEmoji({ risk }: { risk: RiskLevel }) {
  const emoji: Record<RiskLevel, string> = { normal: '💚', caution: '💛', warning: '🧡', critical: '❤️', unknown: '🤍' };
  return <span className={`metric-emoji metric-emoji--${risk}`} role="img" aria-label={`Wellbeing marker: ${riskLabel(risk)}`}>{emoji[risk]}</span>;
}

function PercentageRing({ value }: { value: number | null }) {
  const circumference = 2 * Math.PI * 17;
  const percentage = value === null ? 0 : Math.max(0, Math.min(100, value));
  return <svg className="metric-ring" viewBox="0 0 44 44" aria-hidden="true">
    <circle className="metric-ring__track" cx="22" cy="22" r="17" />
    <circle className="metric-ring__value" cx="22" cy="22" r="17" strokeDasharray={`${circumference * percentage / 100} ${circumference}`} />
    <text x="22" y="25" textAnchor="middle">{value === null ? '—' : `${Math.round(percentage)}%`}</text>
  </svg>;
}

function RangeMeter({ value, baseline, max }: { value: number | null; baseline: number; max: number }) {
  const fill = value === null ? 0 : Math.max(0, Math.min(100, value / max * 100));
  const reference = Math.max(0, Math.min(100, baseline / max * 100));
  const direction = value !== null && value > baseline ? 'over' : 'under';
  return <div className={`range-meter range-meter--${direction}`} role="img" aria-label={value === null ? 'No range value available' : `${pretty(value, '')}; simulator reference ${pretty(baseline, '')}`}>
    <div className="range-meter__track"><span className="range-meter__fill" style={{ width: `${fill}%` }}/><i className="range-meter__reference" style={{ left: `${reference}%` }}/></div>
    <span className="range-meter__caption">Reference {pretty(baseline, '')} · scale to {max}</span>
  </div>;
}

function MiniBars({ values, baseline, sampleId }: { values: number[]; baseline: number; sampleId?: string }) {
  const recent = values.slice(-7);
  const low = Math.min(...recent, baseline); const high = Math.max(...recent, baseline); const spread = high - low || Math.max(Math.abs(high) * .02, .5);
  const y = (value: number) => 29 - ((value - low) / spread) * 22;
  const baselineY = y(baseline);
  return <svg key={sampleId ?? 'empty'} className="metric-bars" viewBox="0 0 112 34" preserveAspectRatio="none" aria-hidden="true">
    <line className="metric-baseline" x1="0" x2="112" y1={baselineY} y2={baselineY}/>
    {recent.length ? recent.map((value, index) => {
      const valueY = y(value); const top = Math.min(valueY, baselineY); const height = Math.max(2, Math.abs(valueY - baselineY));
      return <rect key={`${index}-${value}`} className={value > baseline ? 'metric-bar--above' : 'metric-bar--below'} x={index * 16 + 4} y={top} width="9" height={height} rx="2" />;
    }) : <path className="metric-bars__empty" d="M0 17h112" />}
  </svg>;
}

function Sparkline({ values, baseline, sampleId }: { values: number[]; baseline: number; sampleId?: string }) {
  const width = 112; const height = 30; const low = Math.min(...values, baseline); const high = Math.max(...values, baseline); const range = high - low || Math.max(Math.abs(high) * 0.05, 1);
  const y = (value: number) => height - 3 - ((value - low) / range) * (height - 7);
  const baselineY = y(baseline);
  const coordinates = values.map((value, index) => `${values.length <= 1 ? width / 2 : (index / (values.length - 1)) * width},${height - 3 - ((value - low) / range) * (height - 7)}`);
  const path = coordinates.join(' ');
  return <svg key={sampleId ?? 'empty'} className="metric-sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
    {values.slice(0, -1).map((value, index) => {
      const next = values[index + 1]; const x1 = index / (values.length - 1) * width; const x2 = (index + 1) / (values.length - 1) * width;
      const area = `M ${x1} ${baselineY} L ${x1} ${y(value)} L ${x2} ${y(next)} L ${x2} ${baselineY} Z`;
      return <path key={`${index}-${value}`} className={`metric-sparkline__area ${((value + next) / 2) > baseline ? 'metric-sparkline__area--above' : 'metric-sparkline__area--below'}`} d={area}/>;
    })}
    <line className="metric-baseline" x1="0" x2={width} y1={baselineY} y2={baselineY}/>
    {values.length > 1 ? <polyline points={path}/> : values.length === 1 ? <circle cx={width / 2} cy={height / 2} r="2.5"/> : <path className="metric-sparkline__empty" d={`M 0 ${height / 2} H ${width}`} />}
  </svg>;
}

function RegionHotspot({ x, y, id, selected, label, labelX, labelY, hasAlert, onChoose, onKeyDown }: { x: number; y: number; id: string; selected: string; label: string; labelX: number; labelY: number; hasAlert: boolean; onChoose: (id: string) => void; onKeyDown: (event: KeyboardEvent<SVGGElement>, id: string) => void }) {
  const active = selected === id;
  const labelWidth = label.length * 5.55 + 18;
  return <g className={`body-hotspot ${active ? 'is-selected' : ''} ${hasAlert ? 'has-alert' : ''}`} role="button" tabIndex={0} aria-label={hasAlert ? `${label} — alert or large simulator deviation active` : label} aria-pressed={active} onClick={() => onChoose(id)} onKeyDown={event => onKeyDown(event, id)}>
    <circle className="body-hotspot__hit" cx={x} cy={y} r="23"/><circle className="body-hotspot__ring" cx={x} cy={y} r="15"/><circle className="body-hotspot__core" cx={x} cy={y} r="5"/>
    <g className="body-hotspot__label" aria-hidden="true"><rect x={labelX - labelWidth / 2} y={labelY - 9} width={labelWidth} height="18" rx="9"/><text x={labelX} y={labelY + 3} textAnchor="middle">{label}</text></g>
  </g>;
}

function HeartRateTrend({ samples, risk }: { samples: Observation[]; risk: RiskLevel }) {
  const points = samples.slice(0, 8).reverse().map(sample => sample.physiological.heart_rate?.value).filter((value): value is number => value !== null && value !== undefined);
  const baseline = simulatorBaselines.heart_rate;
  const width = 250; const height = 56; const center = height / 2; const maxDeviation = Math.max(1, ...points.map(value => Math.abs(value - baseline)));
  const y = (value: number) => center - (value - baseline) / maxDeviation * (center - 6);
  const x = (index: number) => points.length < 2 ? width / 2 : index / (points.length - 1) * width;
  return <div className={`trend-line trend-line--${risk}`}><div><span className="metric-label">Heart rate · recent samples</span><strong>{points.length} of 8 · reference {baseline} bpm</strong><span className="trend-legend"><i/>Green below · red above</span></div>{points.length > 1 ? <div className="trend-line__visual"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Heart rate across ${points.length} recent simulated samples, centered on simulator reference ${baseline} beats per minute`}>
    {points.slice(0, -1).map((value, index) => {
      const next = points[index + 1]; const x1 = x(index); const x2 = x(index + 1); const segmentClass = (value + next) / 2 > baseline ? 'trend-line__area--above' : 'trend-line__area--below';
      return <g key={`${index}-${value}`}><path className={`trend-line__area ${segmentClass}`} d={`M ${x1} ${center} L ${x1} ${y(value)} L ${x2} ${y(next)} L ${x2} ${center} Z`}/><path className={`trend-line__segment ${segmentClass}`} d={`M ${x1} ${y(value)} L ${x2} ${y(next)}`}/></g>;
    })}
    <line className="metric-baseline" x1="0" x2={width} y1={center} y2={center}/>
  </svg><MetricInfo field="Heart rate trend" info={metricInformation.heart_rate}/></div> : <p className="muted">Trend appears after two samples.</p>}</div>;
}
