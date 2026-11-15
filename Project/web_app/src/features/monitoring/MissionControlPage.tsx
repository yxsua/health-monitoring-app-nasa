import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { apiRequest } from '../../services/http';

type MessageKind = 'text_update' | 'professional_help' | 'additional_help';
type HelpType = 'medical' | 'mental_health' | 'technical' | 'other';
type PacketMessage = { kind: MessageKind; help_type?: HelpType | null; text: string };
type MissionPacket = {
  message_id: string; contract_version: '1.0.0' | '1.1.0'; source_scope: string;
  data: { mission?: string | null; message?: PacketMessage | null; metrics: { field: string; value: number | null; unit: string }[] };
  status: 'queued' | 'deferred' | 'transmitting' | 'sent' | 'cancelled' | 'failed';
  revision: number; payload_bytes: number; bytes_sent: number; attempt_count: number;
  created_at: string; updated_at: string; sent_at: string | null; earth_received_at: string | null;
};
type MissionStatus = {
  link_state: 'open' | 'closed'; current_window_ends_at: string | null; next_contact_at: string;
  window_duration_seconds: number; window_capacity_bytes: number; transfer_rate_bytes_per_second: number;
  queued_count: number; deferred_count: number; transmitting_count: number; sent_count: number;
  cancelled_count: number; failed_count: number; last_sent_at: string | null;
};
type MissionEvent = { event_id: number; event_type: string; created_at: string; detail: Record<string, string> };
const modes: { kind: MessageKind; title: string; description: string }[] = [
  { kind: 'text_update', title: 'Text update', description: 'Send a mission note to the simulated Earth receiver.' },
  { kind: 'professional_help', title: 'Professional help', description: 'Request a response from a professional category.' },
  { kind: 'additional_help', title: 'Additional support', description: 'Ask for other mission or personal support.' },
];
const helpTypes: { value: HelpType; label: string }[] = [
  { value: 'medical', label: 'Medical professional' },
  { value: 'mental_health', label: 'Mental health professional' },
  { value: 'technical', label: 'Technical specialist' },
  { value: 'other', label: 'Other professional' },
];
function formatTime(value?: string | null) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short',
  }).format(new Date(value));
}
function formatCountdown(value?: string | null) {
  if (!value) return '—';
  const remaining = Math.max(0, Math.ceil((new Date(value).getTime() - Date.now()) / 1000));
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const hours = Math.floor(minutes / 60);
  return hours ? `${String(hours).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}:${String(seconds).padStart(2, '0')}` : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function MissionControlPage() {
  const { token, profile } = useAuth();
  const [kind, setKind] = useState<MessageKind>('text_update');
  const [helpType, setHelpType] = useState<HelpType>('medical');
  const [text, setText] = useState('');
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<MissionStatus | null>(null);
  const [packets, setPackets] = useState<MissionPacket[]>([]);
  const [events, setEvents] = useState<Record<string, MissionEvent[]>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [notice, setNotice] = useState('');

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [nextStatus, nextPackets] = await Promise.all([
        apiRequest<MissionStatus>('/api/v1/mission-control/status', token),
        apiRequest<MissionPacket[]>('/api/v1/mission-control/outbox?limit=50', token),
      ]);
      setStatus(nextStatus);
      setPackets(nextPackets);
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Mission Control is temporarily unavailable.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError('');
    setNotice('');
    const cleanText = text.trim();
    if (!cleanText) { setFormError('Write a message before queuing it.'); return; }
    if (!consent) { setFormError('Review and approve this message before queuing it.'); return; }
    setSending(true);
    const message: PacketMessage = {
      kind,
      ...(kind === 'professional_help' ? { help_type: helpType } : {}),
      text: cleanText,
    };
    try {
      await apiRequest<MissionPacket>('/api/v1/mission-control/outbox', token, {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({
          contract_version: '1.1.0', consent: true, source_scope: 'user_entered',
          data: { ...(profile?.mission ? { mission: profile.mission } : {}), metrics: [], alerts: [], message },
        }),
      });
      setText('');
      setConsent(false);
      setNotice('Message queued for the next simulated contact window.');
      await refresh();
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : 'The message could not be queued.');
    } finally {
      setSending(false);
    }
  }

  async function toggleEvents(messageId: string) {
    if (expanded === messageId) { setExpanded(null); return; }
    setExpanded(messageId);
    if (events[messageId]) return;
    try {
      const result = await apiRequest<{ message: MissionPacket; events: MissionEvent[] }>(`/api/v1/mission-control/outbox/${encodeURIComponent(messageId)}`, token);
      setEvents(previous => ({ ...previous, [messageId]: result.events }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load packet history.');
    }
  }

  async function cancel(packet: MissionPacket) {
    setError('');
    try {
      await apiRequest<MissionPacket>(`/api/v1/mission-control/outbox/${encodeURIComponent(packet.message_id)}/cancel`, token, {
        method: 'POST', body: JSON.stringify({ expected_revision: packet.revision }),
      });
      setNotice('Queued message cancelled before transfer began.');
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The message could not be cancelled.');
      await refresh();
    }
  }

  const countdownTarget = status?.link_state === 'open' ? status.current_window_ends_at : status?.next_contact_at;
  const pending = (status?.queued_count ?? 0) + (status?.deferred_count ?? 0);

  return <main className="page-content mission-control-page">
    <div className="page-heading mission-control-heading">
      <div><p className="eyebrow">FLIGHT SYSTEMS · OUTBOUND MESSAGES</p><h1>Mission Control</h1><p className="lead">Send a text update or request additional support through the simulated mission link.</p></div>
      <div className="mission-control-heading__actions"><span className={`live-indicator live-indicator--${status?.link_state === 'open' ? 'live' : 'connecting'}`}><i aria-hidden="true" />{status?.link_state === 'open' ? 'Simulated window open' : 'Waiting for contact window'}</span><a className="button button--secondary" href="http://localhost:8081" target="_blank" rel="noreferrer">Open Earth receiver ↗</a></div>
    </div>

    <div className="notice notice--subtle mission-control-disclaimer"><strong>Simulation notice.</strong> Messages and help requests are stored locally and appear on the separate Earth receiver only after a simulated transfer. No professional, support team, or emergency service is actually contacted.</div>
    {error && <p className="notice notice--error" role="alert">{error}</p>}

    <section className="mission-control-overview" aria-label="Simulated contact status">
      <article className="panel mission-link-card">
        <div className="mission-link-card__visual" aria-hidden="true"><span /><span /><span /><b>AH</b></div>
        <div className="mission-link-card__body"><p className="eyebrow">SIMULATED CONTACT WINDOW</p><h2>{status?.link_state === 'open' ? 'Link is open' : 'Link is closed'}</h2><p className="muted">{status?.link_state === 'open' ? 'Queued messages can transfer now.' : `Next opportunity ${formatTime(status?.next_contact_at)}.`}</p><div className="mission-link-card__countdown"><span>{status?.link_state === 'open' ? 'WINDOW CLOSES IN' : 'NEXT WINDOW IN'}</span><strong>{formatCountdown(countdownTarget)}</strong></div><div className="mission-link-card__meta"><span>{status?.window_duration_seconds ?? '—'} sec window</span><span>{status?.window_capacity_bytes?.toLocaleString() ?? '—'} B capacity</span><span>{status?.transfer_rate_bytes_per_second ?? '—'} B/s</span></div></div>
      </article>
      <article className="panel mission-queue-card"><p className="eyebrow">LOCAL OUTBOX</p><h2>Message queue</h2><div className="mission-queue-card__counts"><div><strong>{pending}</strong><span>Pending</span></div><div><strong>{status?.transmitting_count ?? 0}</strong><span>Transferring</span></div><div><strong>{status?.sent_count ?? 0}</strong><span>Received</span></div></div><p className="muted">Last simulated receipt: {formatTime(status?.last_sent_at)}</p></article>
    </section>

    <section className="mission-control-workspace">
      <article className="panel mission-message-panel">
        <div className="panel-heading"><div><p className="eyebrow">CREW-INITIATED</p><h2>Compose message</h2></div><span className="status-pill status-pill--neutral">User entered</span></div>
        <div className="mission-message-modes" role="group" aria-label="Message type">
          {modes.map(mode => <button key={mode.kind} type="button" className={`mission-message-mode ${kind === mode.kind ? 'mission-message-mode--selected' : ''}`} aria-pressed={kind === mode.kind} onClick={() => { setKind(mode.kind); setNotice(''); setFormError(''); }}><strong>{mode.title}</strong><span>{mode.description}</span></button>)}
        </div>
        <form className="mission-message-form" onSubmit={submit}>
          {kind === 'professional_help' && <label className="mission-form-field">Professional category<select value={helpType} onChange={event => setHelpType(event.target.value as HelpType)}>{helpTypes.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>}
          <label className="mission-form-field">{kind === 'text_update' ? 'Message' : kind === 'professional_help' ? 'What would you like the professional to know?' : 'What additional support do you need?'}<textarea value={text} onChange={event => setText(event.target.value)} maxLength={2000} rows={6} placeholder={kind === 'text_update' ? 'Write a concise mission update…' : 'Describe the request and any useful context…'} required /></label>
          <div className="mission-message-counter">{text.length} / 2,000 characters</div>
          <label className="mission-consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /><span>I reviewed this message and approve storing it in the simulated outbound queue.</span></label>
          {formError && <p className="notice notice--error" role="alert">{formError}</p>}
          {notice && <p className="notice notice--success" role="status">{notice}</p>}
          <button className="button button--primary" type="submit" disabled={sending || !text.trim() || !consent}>{sending ? 'Queuing…' : kind === 'text_update' ? 'Queue text update' : 'Queue help request'}</button>
        </form>
      </article>

      <article className="panel mission-outbox-panel">
        <div className="panel-heading"><div><p className="eyebrow">DELIVERY HISTORY</p><h2>Outbound messages</h2></div><span className="mission-refresh-note">Refreshes every 3 sec</span></div>
        {loading ? <p className="muted">Loading local outbox…</p> : packets.length === 0 ? <div className="mission-empty"><strong>No messages queued</strong><span>Text updates and help requests will be listed here.</span></div> : <div className="mission-packet-list">{packets.map(packet => {
          const message = packet.data.message;
          const title = message?.kind === 'professional_help' ? 'Professional help request' : message?.kind === 'additional_help' ? 'Additional support request' : message ? 'Text update' : 'Structured mission packet';
          const percent = packet.payload_bytes ? Math.min(100, Math.round(packet.bytes_sent / packet.payload_bytes * 100)) : 0;
          const canCancel = ['queued', 'deferred'].includes(packet.status) && packet.attempt_count === 0;
          return <div className="mission-packet" key={packet.message_id}><div className="mission-packet__header"><div><strong>{title}</strong><span>{packet.data.mission || 'Mission update'} · {formatTime(packet.created_at)}</span></div><span className={`status-pill ${packet.status === 'sent' ? 'status-pill--active' : 'status-pill--neutral'}`}>{packet.status}</span></div>
            {message && <p className="mission-packet__message">{message.text}</p>}{message?.help_type && <p className="mission-packet__category">Requested: {helpTypes.find(item => item.value === message.help_type)?.label ?? message.help_type}</p>}
            {packet.status === 'transmitting' && <div className="mission-packet__progress"><span><i style={{ width: `${percent}%` }} /></span><small>{packet.bytes_sent} / {packet.payload_bytes} bytes</small></div>}
            <div className="mission-packet__actions"><button className="text-button" type="button" onClick={() => void toggleEvents(packet.message_id)}>{expanded === packet.message_id ? 'Hide timeline' : 'View timeline'}</button>{canCancel && <button className="text-button text-button--danger" type="button" onClick={() => void cancel(packet)}>Cancel before transfer</button>}{packet.earth_received_at && <span>Received by simulated Earth console {formatTime(packet.earth_received_at)}</span>}</div>
            {expanded === packet.message_id && <ol className="mission-event-list">{(events[packet.message_id] ?? []).map(item => <li key={item.event_id}><span>{item.event_type.replaceAll('_', ' ')}</span><time>{formatTime(item.created_at)}</time></li>)}</ol>}
          </div>;
        })}</div>}
      </article>
    </section>
    <p className="mission-control-footer">Local AstraHealth services remain available independently of this simulated communications link. <Link to="/dashboard">Return to monitoring</Link>.</p>
  </main>;
}
