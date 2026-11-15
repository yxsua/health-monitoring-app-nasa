import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import type { Recommendation } from '../../generated/chatbot-types';

const eventName = 'astrahealth:recommendation';
const cooldownKey = 'astrahealth-recommendation-cooldowns';
const routeLabels: Record<string, string> = {
  '/dashboard': 'Monitoring overview', '/wellbeing': 'Wellbeing', '/wellbeing/history': 'Wellbeing history', '/mission-control': 'Mission Control', '/profile': 'Profile',
};

function localSuggestion(kind: 'screen' | 'idle', path: string): Recommendation {
  const now = new Date().toISOString();
  const screen = kind === 'screen';
  const title = screen ? 'Reset your visual focus' : 'Consider a short movement break';
  return {
    recommendation_id: `app-usage:${kind}:${path}:${Date.now()}`,
    priority: 'routine', title,
    action: screen
      ? 'Look at something far away for a few breaths, then focus on a middle-distance object, and finally a nearby object. Keep the movement comfortable and follow onboard guidance.'
      : 'If you have been seated, consider a brief comfortable stretch or change of position. Skip anything uncomfortable and follow onboard guidance.',
    rationale: screen
      ? `This page has remained open for 20 minutes (${routeLabels[path] ?? 'this page'}). This is a screen-time reminder, not an eye assessment.`
      : 'The app has had no keyboard, pointer, touch, or scroll interaction for 45 minutes. That does not measure physical activity.',
    source_scope: 'app_usage', source_refs: [path], observed_at: now, evidence: [],
  };
}

export function RecommendationOverlay() {
  const location = useLocation();
  const [queue, setQueue] = useState<Recommendation[]>([]);
  const [focusStep, setFocusStep] = useState<number | null>(null);
  const seenRef = useRef(new Map<string, number>());
  const dialogRef = useRef<HTMLDialogElement>(null);
  const firstActionRef = useRef<HTMLButtonElement>(null);
  const current = queue[0];

  useEffect(() => {
    const receive = (event: Event) => {
      const detail = (event as CustomEvent<Recommendation>).detail;
      if (!detail || !detail.title || !detail.action) return;
      const signature = [detail.source_scope, detail.priority, detail.title, detail.evidence.map(item => item.field).sort().join(',')].join('|');
      const now = Date.now();
      let stored: Record<string, number> = {};
      try { stored = JSON.parse(window.sessionStorage.getItem(cooldownKey) ?? '{}') as Record<string, number>; } catch { stored = {}; }
      const lastShown = Math.max(stored[signature] ?? 0, seenRef.current.get(signature) ?? 0);
      if (now - lastShown < (detail.priority === 'critical' || detail.priority === 'warning' ? 180_000 : 900_000)) return;
      stored[signature] = now;
      seenRef.current.set(signature, now);
      try { window.sessionStorage.setItem(cooldownKey, JSON.stringify(stored)); } catch { /* Keep in-memory cooldowns if storage is unavailable. */ }
      setQueue(items => items.some(item => item.recommendation_id === detail.recommendation_id) ? items : [...items, detail]);
    };
    window.addEventListener(eventName, receive);
    return () => window.removeEventListener(eventName, receive);
  }, []);

  useEffect(() => {
    if (!current) return;
    setFocusStep(null);
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
    firstActionRef.current?.focus();
    return () => { if (dialog.open) dialog.close(); };
  }, [current]);

  useEffect(() => {
    const path = location.pathname;
    let elapsed = 0;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      elapsed += 1;
      if (elapsed >= 20 * 60) {
        window.clearInterval(timer);
        window.dispatchEvent(new CustomEvent(eventName, { detail: localSuggestion('screen', path) }));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [location.pathname]);

  useEffect(() => {
    let lastActivity = Date.now();
    const markActivity = () => { lastActivity = Date.now(); };
    const onVisibility = () => { if (document.visibilityState === 'visible') markActivity(); };
    const events = ['pointerdown', 'keydown', 'touchstart', 'wheel', 'scroll'];
    events.forEach(name => window.addEventListener(name, markActivity, { passive: true }));
    document.addEventListener('visibilitychange', onVisibility);
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible' && Date.now() - lastActivity >= 45 * 60_000) {
        lastActivity = Date.now();
        window.dispatchEvent(new CustomEvent(eventName, { detail: localSuggestion('idle', location.pathname) }));
      }
    }, 30_000);
    return () => {
      window.clearInterval(timer);
      events.forEach(name => window.removeEventListener(name, markActivity));
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [location.pathname]);

  function close() { setQueue(items => items.slice(1)); }
  const isFocusReset = current?.source_scope === 'app_usage' && current.title === 'Reset your visual focus';
  const focusSteps = [
    'First, look at a distant object across the room for a few comfortable breaths.',
    'Now shift your focus to something at a middle distance.',
    'Finally, focus on a nearby object, then return to your task when ready.',
  ];
  function advance() {
    if (isFocusReset && focusStep === null) { setFocusStep(0); return; }
    if (isFocusReset && focusStep !== null && focusStep < focusSteps.length - 1) { setFocusStep(focusStep + 1); return; }
    close();
  }
  if (!current) return null;
  const sourceLabel = current.source_scope === 'simulated_fixture' ? 'SIMULATED DATA' : current.source_scope === 'astronaut_profile' ? 'WELLBEING PROFILE' : current.source_scope === 'app_usage' ? 'SCREEN USE' : 'SHARED TOPIC';
  const needsAcknowledgement = current.priority === 'critical' || current.priority === 'warning';
  return <dialog ref={dialogRef} className={`recommendation-dialog recommendation-dialog--${current.priority}`} aria-modal="true" aria-labelledby="recommendation-dialog-title" aria-describedby="recommendation-dialog-copy" onCancel={event => { event.preventDefault(); if (!needsAcknowledgement) close(); }}>
      <div className="recommendation-dialog__top"><span className={`severity-pill severity-pill--${current.priority}`}>{sourceLabel} · {current.priority}</span><span className="recommendation-dialog__count">{queue.length > 1 ? `${queue.length} items` : 'Recommendation'}</span></div>
      <h2 id="recommendation-dialog-title">{current.title}</h2>
      <p className="recommendation-dialog__action" id="recommendation-dialog-copy">{isFocusReset && focusStep !== null ? focusSteps[focusStep] : current.action}</p>
      {isFocusReset && focusStep !== null && <div className="focus-reset-progress" aria-label={`Focus reset step ${focusStep + 1} of ${focusSteps.length}`}>{focusSteps.map((_, index) => <i key={index} className={index <= focusStep ? 'is-complete' : ''} />)}<span>STEP {focusStep + 1} OF {focusSteps.length}</span></div>}
      <p className="recommendation-dialog__reason">{current.rationale}</p>
      {current.evidence.length > 0 && <p className="recommendation-dialog__evidence">Evidence: {current.evidence.map(item => `${item.field.replaceAll('_', ' ')} ${item.value ?? '—'} ${item.unit} · ${item.quality}`).join(' · ')}</p>}
      <div className="recommendation-dialog__footer"><span>{needsAcknowledgement ? 'Acknowledgement required' : 'Review when convenient'}</span><div className="recommendation-dialog__actions">{!needsAcknowledgement && <button className="button button--secondary" type="button" onClick={close}>Not now</button>}<button ref={firstActionRef} className="button button--primary" type="button" onClick={advance}>{needsAcknowledgement ? 'Acknowledge and continue' : isFocusReset ? focusStep === null ? 'Start focus reset' : focusStep === focusSteps.length - 1 ? 'Finish focus reset' : 'Next step' : current.source_scope === 'app_usage' ? 'I’ll take a short break' : 'Got it'}</button></div></div>
    </dialog>;
}
