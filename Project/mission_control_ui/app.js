const API = '/api/v1';
const tokenKey = 'astrahealth-earth-receiver-token';
const $ = (id) => document.getElementById(id);
const loginBackgroundVideo = $('login-background-video');
const loginBackgroundPlaylist = ['/video.mp4', '/video-2.mp4', '/video-3.mp4'];
let loginBackgroundIndex = 0;
if (loginBackgroundVideo) {
  loginBackgroundVideo.addEventListener('ended', () => {
    loginBackgroundIndex = (loginBackgroundIndex + 1) % loginBackgroundPlaylist.length;
    loginBackgroundVideo.src = loginBackgroundPlaylist[loginBackgroundIndex];
    loginBackgroundVideo.play().catch(() => {});
  });
}
let token = sessionStorage.getItem(tokenKey) || '';
let refreshTimer = 0;
let crewRefreshInFlight = false;
const crewSnapshot = new Map();
const crewMetricHistory = new Map();
const individualMetricHistory = new Map();
const crewMetricGroups = [
  { key: 'physiological', title: 'Physiological', fields: [['heart_rate', 'Heart rate'], ['systolic_pressure', 'Systolic pressure'], ['diastolic_pressure', 'Diastolic pressure'], ['spo2', 'SpO₂'], ['body_temperature', 'Body temperature'], ['glucose', 'Glucose'], ['hrv_rmssd', 'HRV · RMSSD']] },
  { key: 'self_assessment', title: 'Activity & wellbeing', fields: [['sleep_duration', 'Sleep duration'], ['mood', 'Mood'], ['exercise_duration', 'Exercise duration']] },
  { key: 'environment', title: 'Environment', fields: [['radiation_dose_rate', 'Radiation dose rate'], ['co2', 'Cabin CO₂'], ['cabin_temperature', 'Cabin temperature'], ['humidity', 'Humidity'], ['noise', 'Noise'], ['cabin_pressure', 'Cabin pressure'], ['gravity', 'Gravity'], ['earth_latency', 'Earth latency'], ['simulated_daylight_duration', 'Daylight duration'], ['social_interaction_duration', 'Social interaction']] },
];
const crewMetricBaselines = {
  heart_rate: 70, systolic_pressure: 115, diastolic_pressure: 75, spo2: 98,
  body_temperature: 36.7, glucose: 95, hrv_rmssd: 65, sleep_duration: 7, mood: 4,
  exercise_duration: 30, radiation_dose_rate: 0.5, co2: 1000, cabin_temperature: 22,
  humidity: 45, noise: 40, cabin_pressure: 101, gravity: 0.1,
};
const consolePages = {
  overview: { title: 'Crew-wide overview', eyebrow: 'EARTH SIDE / CREW MONITORING', subtitle: 'Aggregated simulated readings across registered crew.' },
  crew: { title: 'Crew member metrics', eyebrow: 'EARTH SIDE / INDIVIDUAL READINGS', subtitle: 'Select a crew member to inspect their current simulated measurements.' },
  messages: { title: 'Received updates', eyebrow: 'EARTH SIDE / INBOUND COMMS', subtitle: 'Messages appear here after the local contact simulator delivers them to its receiver.' },
};

const request = async (path, options = {}) => {
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API}${path}`, { ...options, headers, cache: 'no-store' });
  let body = {};
  try { body = response.status === 204 ? {} : await response.json(); } catch { body = {}; }
  if (!response.ok) {
    const error = new Error(body?.error?.message || 'The request could not be completed.');
    error.status = response.status;
    throw error;
  }
  return body;
};

function setConsolePage(pageKey) {
  const page = consolePages[pageKey] ? pageKey : 'overview';
  document.querySelectorAll('[data-console-page]').forEach(section => {
    section.classList.toggle('hidden', section.dataset.consolePage !== page);
  });
  document.querySelectorAll('.console-nav__link').forEach(button => {
    const active = button.dataset.consoleTarget === page;
    button.classList.toggle('is-active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  $('console-eyebrow').textContent = consolePages[page].eyebrow;
  $('console-title').textContent = consolePages[page].title;
  $('console-subtitle').textContent = consolePages[page].subtitle;
}

function showLogin(error = '') {
  clearInterval(refreshTimer);
  loginBackgroundVideo?.play().catch(() => {});
  $('login-view').classList.remove('hidden');
  $('console-view').classList.add('hidden');
  $('logout').classList.add('hidden');
  $('identity').textContent = 'NOT AUTHENTICATED';
  $('login-error').textContent = error;
}

function showConsole(username = '') {
  loginBackgroundVideo?.pause();
  $('login-view').classList.add('hidden');
  $('console-view').classList.remove('hidden');
  $('logout').classList.remove('hidden');
  $('identity').textContent = username ? username.toUpperCase() : 'CREW SESSION';
  clearInterval(refreshTimer);
  void refresh();
  refreshTimer = setInterval(() => {
    if (document.visibilityState === 'visible') void refresh();
  }, 3000);
}

function timeLabel(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'UTC', timeZoneName: 'short' }).format(new Date(value));
}

function countdownTo(value) {
  if (!value) return '—';
  const seconds = Math.max(0, Math.ceil((new Date(value).getTime() - Date.now()) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remaining = seconds % 60;
  return hours ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}` : `${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);
}

async function refresh() {
  if (!token) return;
  void refreshCrewTelemetry();
  try {
    const [status, windows, received] = await Promise.all([
      request('/mission-control/status'),
      request('/mission-control/contact-windows?limit=5'),
      request('/mission-control/receiver/messages?limit=100'),
    ]);
    renderStatus(status, windows.windows || [], received || []);
    renderReceived(received || []);
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      token = '';
      sessionStorage.removeItem(tokenKey);
      showLogin('Your session expired. Sign in again to continue.');
    } else {
      $('refresh-state').textContent = 'RECEIVER UNAVAILABLE · RETRYING';
      $('service-state').textContent = 'SIMULATED LINK UNAVAILABLE';
      $('received-list').innerHTML = '<div class="empty-state">The local receiver could not be reached. Messages remain in the onboard outbox until the service is available.</div>';
    }
  }
}

async function refreshCrewTelemetry() {
  if (!token || crewRefreshInFlight) return;
  crewRefreshInFlight = true;
  try {
    const [crew, schedule] = await Promise.all([
      request('/astronauts/crew'),
      request('/simulation/runs/demo-run/scenario'),
    ]);
    const results = [];
    for (let index = 0; index < crew.length; index += 8) {
      const group = crew.slice(index, index + 8);
      const batch = await Promise.allSettled(group.map(async (member) => {
        const sample = await request(`/simulation/runs/demo-run/astronauts/${encodeURIComponent(member.astronaut_id)}/inputs`);
        const previous = crewSnapshot.get(member.astronaut_id) || {};
        const updated = {
          ...previous,
          member,
          observation: sample.items?.[0] || null,
          scenario_id: sample.scenario_id || schedule.scenario_id,
          sampled_at: sample.items?.[0]?.observed_at || null,
        };
        if (updated.observation) crewSnapshot.set(member.astronaut_id, updated);
        return updated;
      }));
      results.push(...batch.map((result, batchIndex) => result.status === 'fulfilled'
        ? result.value
        : crewSnapshot.get(group[batchIndex].astronaut_id) || { member: group[batchIndex], observation: null, scenario_id: schedule.scenario_id, sampled_at: null }));
    }
    renderCrewTelemetry(results, schedule);
    const missing = results.filter(member => !member.observation).length;
    $('crew-refresh-state').textContent = missing ? `PARTIAL · ${results.length - missing}/${results.length} REPORTING` : 'LIVE · AUTO REFRESH 3 SEC';
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      token = '';
      sessionStorage.removeItem(tokenKey);
      showLogin('Your session expired. Sign in again to continue.');
    } else {
      $('crew-refresh-state').textContent = 'SIMULATOR UNAVAILABLE · RETRYING';
      if (!crewSnapshot.size) {
        $('crew-metric-summary').innerHTML = '<div class="empty-state">The crew roster or simulator is temporarily unavailable. Retrying automatically.</div>';
        $('crew-list').innerHTML = '';
      }
    }
  } finally {
    crewRefreshInFlight = false;
  }
}

function metricReading(member, group, field) {
  return member.observation?.[group]?.[field] || null;
}

function metricText(reading) {
  if (!reading || reading.value === null || reading.value === undefined) return '—';
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(reading.value)} ${reading.unit || ''}`.trim();
}

function metricSparkline(values, baseline = null) {
  const samples = values.slice(-12);
  if (!samples.length) return '<span class="metric-visual__waiting">LIVE TREND · COLLECTING</span>';
  const hasBaseline = Number.isFinite(baseline);
  const reference = hasBaseline ? baseline : null;
  const low = Math.min(...samples, ...(hasBaseline ? [reference] : []));
  const high = Math.max(...samples, ...(hasBaseline ? [reference] : []));
  const span = high - low || Math.max(Math.abs(high) * 0.05, 1);
  const y = (value) => 23 - (value - low) / span * 19;
  const points = samples.map((value, index) => `${(samples.length === 1 ? 50 : index / (samples.length - 1) * 100).toFixed(1)},${y(value).toFixed(1)}`);
  const areaSegments = hasBaseline ? samples.slice(0, -1).map((value, index) => {
    const next = samples[index + 1];
    const x1 = index / (samples.length - 1) * 100;
    const x2 = (index + 1) / (samples.length - 1) * 100;
    const direction = (value + next) / 2 > reference ? 'above' : 'below';
    return `<path class="metric-sparkline__area metric-sparkline__area--${direction}" d="M${x1} ${y(reference)} L${x1} ${y(value)} L${x2} ${y(next)} L${x2} ${y(reference)} Z"></path>`;
  }).join('') : '';
  const baselineLine = hasBaseline ? `<line class="metric-sparkline__baseline" x1="0" x2="100" y1="${y(reference)}" y2="${y(reference)}"></line>` : '';
  return `<svg class="metric-sparkline" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true">${areaSegments}${baselineLine}<polyline class="metric-sparkline__line" points="${points.join(' ')}"></polyline><circle class="metric-sparkline__point" cx="${points.at(-1).split(',')[0]}" cy="${points.at(-1).split(',')[1]}" r="2.4"></circle></svg>`;
}

function metricVisual(metric, mean) {
  if (mean === null) return '<span class="metric-visual__waiting">NO VALID READINGS</span>';
  const baseline = crewMetricBaselines[metric.field];
  if (['spo2', 'humidity'].includes(metric.field)) {
    const percent = Math.max(0, Math.min(100, mean));
    return `<div class="metric-ring-wrap"><span class="metric-ring" style="--metric-progress:${percent}%"><i></i></span>${metricSparkline(crewMetricHistory.get(metric.field) || [], baseline)}</div>`;
  }
  return metricSparkline(crewMetricHistory.get(metric.field) || [], baseline);
}

function individualMetricVisual(metric, member, reading) {
  const numericValue = reading?.quality === 'valid' && Number.isFinite(Number(reading.value))
    ? Number(reading.value)
    : null;
  if (numericValue === null) return '<span class="metric-visual__waiting">NO VALID READINGS</span>';
  const historyKey = `${member.astronaut_id}:${metric.field}`;
  const history = individualMetricHistory.get(historyKey) || [];
  const baseline = crewMetricBaselines[metric.field];
  if (['spo2', 'humidity'].includes(metric.field)) {
    const percent = Math.max(0, Math.min(100, numericValue));
    return `<div class="metric-ring-wrap"><span class="metric-ring" style="--metric-progress:${percent}%"><i></i></span>${metricSparkline(history, baseline)}</div>`;
  }
  return metricSparkline(history, baseline);
}

function renderCrewTelemetry(crew, schedule) {
  const members = crew.length ? crew : Array.from(crewSnapshot.values());
  const reporting = members.filter(member => member.observation);
  const allMetrics = crewMetricGroups.flatMap(group => group.fields.map(([field, label]) => ({ group: group.key, field, label })));
  let validReadingCount = 0;
  for (const member of reporting) {
    for (const metric of allMetrics) {
      const reading = metricReading(member, metric.group, metric.field);
      if (reading?.quality === 'valid' && reading.value !== null && Number.isFinite(Number(reading.value))) validReadingCount += 1;
    }
  }
  for (const member of reporting) {
    const astronautId = String(member.member?.astronaut_id || 'unknown');
    for (const metric of allMetrics) {
      const reading = metricReading(member, metric.group, metric.field);
      if (reading?.quality !== 'valid' || reading.value === null || !Number.isFinite(Number(reading.value))) continue;
      const historyKey = `${astronautId}:${metric.field}`;
      const history = individualMetricHistory.get(historyKey) || [];
      history.push(Number(reading.value));
      individualMetricHistory.set(historyKey, history.slice(-48));
    }
  }
  $('crew-total').textContent = members.length.toLocaleString();
  $('crew-reporting').textContent = `${reporting.length.toLocaleString()} / ${members.length.toLocaleString()}`;
  $('crew-valid').textContent = validReadingCount.toLocaleString();
  $('crew-scenario').textContent = (schedule.scenario_id || reporting[0]?.scenario_id || '—').replaceAll('_', ' ');
  $('crew-metric-summary').innerHTML = allMetrics.map(metric => {
    const readings = reporting.map(member => metricReading(member, metric.group, metric.field)).filter(reading => reading?.quality === 'valid' && reading.value !== null && Number.isFinite(Number(reading.value)));
    const values = readings.map(reading => Number(reading.value));
    const mean = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
    if (mean !== null) {
      const history = crewMetricHistory.get(metric.field) || [];
      history.push(mean);
      crewMetricHistory.set(metric.field, history.slice(-48));
    }
    const unit = readings[0]?.unit || reporting.map(member => metricReading(member, metric.group, metric.field)?.unit).find(Boolean) || '';
    const range = values.length ? `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(Math.min(...values))}–${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(Math.max(...values))} ${unit}`.trim() : 'No valid readings';
    const baseline = crewMetricBaselines[metric.field];
    const baselineLabel = baseline === undefined ? 'not set' : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(baseline)} ${unit}`.trim();
    return `<article class="crew-metric-card"><span>${escapeHtml(metric.label)}</span><strong>${mean === null ? '—' : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(mean)} ${escapeHtml(unit)}`.trim()}</strong><div class="crew-metric-card__chart ${['spo2', 'humidity'].includes(metric.field) ? 'crew-metric-card__chart--ring' : ''}">${metricVisual(metric, mean)}</div><small>${readings.length}/${members.length} reporting · Range ${escapeHtml(range)} · Baseline ${escapeHtml(baselineLabel)}</small></article>`;
  }).join('');

  if (!members.length) {
    $('crew-list').innerHTML = '<div class="empty-state">No registered crew accounts were found.</div>';
    return;
  }
  const existingCrewRows = Array.from($('crew-list').querySelectorAll('.crew-member'));
  const hadRenderedCrewRows = existingCrewRows.length > 0;
  const openCrewIds = new Set(existingCrewRows.filter(row => row.open).map(row => row.dataset.astronautId));
  $('crew-list').innerHTML = members.map((member, index) => {
    const profile = member.member || {};
    const crewId = String(profile.astronaut_id || `crew-${index}`);
    const observation = member.observation;
    const shouldBeOpen = hadRenderedCrewRows ? openCrewIds.has(crewId) : index === 0;
    const validCount = allMetrics.filter(metric => {
      const reading = metricReading(member, metric.group, metric.field);
      return reading?.quality === 'valid' && reading.value !== null;
    }).length;
    const groups = crewMetricGroups.map(group => `<section class="crew-reading-group"><h4>${escapeHtml(group.title)}</h4><div class="crew-reading-grid">${group.fields.map(([field, label]) => {
      const reading = metricReading(member, group.key, field);
      const metric = { field, label };
      const baseline = crewMetricBaselines[field];
      const unit = reading?.unit || '';
      const baselineLabel = baseline === undefined ? 'Baseline not set' : `Baseline ${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(baseline)} ${unit}`.trim();
      return `<article class="crew-reading"><div class="crew-reading__top"><span>${escapeHtml(label)}</span><small>${escapeHtml(reading?.quality || 'missing')}</small></div><strong>${escapeHtml(metricText(reading))}</strong><div class="crew-reading__chart ${['spo2', 'humidity'].includes(field) ? 'crew-reading__chart--ring' : ''}">${individualMetricVisual(metric, profile, reading)}</div><small class="crew-reading__baseline">${escapeHtml(baselineLabel)}</small></article>`;
    }).join('')}</div></section>`).join('');
    return `<details class="crew-member" data-astronaut-id="${escapeHtml(crewId)}" ${shouldBeOpen ? 'open' : ''}><summary><span class="crew-member__identity"><strong>${escapeHtml(profile.display_name || 'Crew member')}</strong><small>${escapeHtml(profile.mission || 'Mission not set')}</small></span><span class="crew-member__state"><b class="${observation ? 'is-live' : 'is-offline'}">${observation ? 'LIVE' : 'NO SAMPLE'}</b><small>${validCount}/${allMetrics.length} valid · ${timeLabel(member.sampled_at)}</small></span></summary><div class="crew-member__body"><div class="crew-member__meta">Crew ID ${escapeHtml(profile.astronaut_id || '')} · ${escapeHtml((member.scenario_id || 'normal').replaceAll('_', ' '))}</div>${groups}</div></details>`;
  }).join('');
  const latestSample = reporting.map(member => member.sampled_at).filter(Boolean).sort().at(-1);
  $('crew-updated-at').textContent = latestSample ? `Latest simulated sample ${timeLabel(latestSample)} · Refreshes every 3 seconds.` : 'Waiting for the first simulated crew samples.';
}

function renderStatus(status, windows, received) {
  const open = status.link_state === 'open';
  const current = windows[0];
  $('service-state').textContent = 'SIMULATED RECEIVER';
  $('link-title').textContent = open ? 'Contact window open' : 'Contact window closed';
  $('contact-caption').textContent = open ? 'WINDOW CLOSES IN' : 'NEXT CONTACT OPENS IN';
  $('countdown').dataset.target = open ? status.current_window_ends_at : status.next_contact_at;
  $('countdown').textContent = countdownTo($('countdown').dataset.target);
  $('window-time').textContent = open && status.current_window_ends_at
    ? `Window ends ${timeLabel(status.current_window_ends_at)}`
    : `Next window ${timeLabel(status.next_contact_at)}`;
  const capacity = Math.max(0, Number(status.window_capacity_bytes) || 0);
  const used = current?.state === 'open' ? Number(current.bytes_used || 0) : 0;
  $('capacity-fill').style.width = `${capacity ? Math.min(100, used / capacity * 100) : 0}%`;
  $('capacity-label').textContent = `Window capacity ${used.toLocaleString()} / ${capacity.toLocaleString()} bytes`;
  $('received-count').textContent = Number(status.sent_count || 0).toLocaleString();
  const latest = received[0];
  $('last-receipt').textContent = latest ? messageTitle(latest.message.data.message) : 'No messages received';
  $('last-receipt-time').textContent = latest ? timeLabel(latest.received_at) : 'Waiting for a simulated delivery';
  document.querySelector('.state-light').style.background = open ? '#92bd00' : '#b9c1d3';
  document.querySelector('.state-light').style.boxShadow = open ? '0 0 0 3px #edf5cb' : '0 0 0 3px #eef0f4';
  $('refresh-state').textContent = 'AUTO REFRESH · 3 SEC';
}

function messageTitle(message) {
  if (message?.kind === 'professional_help') return 'Professional help request';
  if (message?.kind === 'additional_help') return 'Additional support request';
  if (message?.kind === 'text_update') return 'Crew text update';
  return 'Structured mission update';
}

function renderReceived(items) {
  if (!items.length) {
    $('received-list').innerHTML = '<div class="empty-state">No messages have arrived yet.<br>Updates appear here after a simulated transfer completes.</div>';
    return;
  }
  $('received-list').innerHTML = items.map((item) => {
    const packet = item.message;
    const content = packet.data?.message;
    const isHelp = content?.kind === 'professional_help' || content?.kind === 'additional_help';
    const category = content?.help_type ? ` · ${content.help_type.replaceAll('_', ' ')}` : '';
    return `<article class="received-message ${isHelp ? 'received-message--help' : ''}">
      <div class="received-message__top"><div><span class="received-message__classification">${isHelp ? 'SUPPORT REQUEST' : 'MISSION UPDATE'}</span><h3>${escapeHtml(messageTitle(content))}${escapeHtml(category)}</h3><p>${escapeHtml(packet.data?.mission || 'Mission not specified')} · Received ${timeLabel(item.received_at)}</p></div><span class="received-message__state">SIMULATED RECEIPT</span></div>
      ${content?.text ? `<p class="received-message__text">${escapeHtml(content.text)}</p>` : ''}
      ${packet.data?.metrics?.length ? `<div class="received-message__metrics">${packet.data.metrics.map(metric => `<span>${escapeHtml(metric.field.replaceAll('_', ' '))}: <b>${metric.value ?? '—'} ${escapeHtml(metric.unit)}</b></span>`).join('')}</div>` : ''}
      <div class="received-message__footer"><span>Message ID ${escapeHtml(packet.message_id.slice(0, 8))}…</span><span>Origin ${escapeHtml(packet.source_scope.replaceAll('_', ' '))}</span></div>
    </article>`;
  }).join('');
}

async function login(event) {
  event.preventDefault();
  $('login-error').textContent = '';
  const button = $('login-form').querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username: $('username').value.trim(), password: $('password').value }) });
    token = result.access_token;
    sessionStorage.setItem(tokenKey, token);
    showConsole(result.astronaut?.username || $('username').value.trim());
  } catch (error) {
    $('login-error').textContent = error.status === 401 ? 'Username or password was not accepted.' : error.message;
  } finally {
    button.disabled = false;
  }
}

$('login-form').addEventListener('submit', login);
document.querySelectorAll('.console-nav__link').forEach(button => {
  button.addEventListener('click', () => setConsolePage(button.dataset.consoleTarget));
});
$('logout').addEventListener('click', async () => {
  try { await request('/auth/logout', { method: 'POST' }); } catch { /* A server-side expiration still clears the local view. */ }
  token = '';
  sessionStorage.removeItem(tokenKey);
  showLogin();
});
setInterval(() => {
  const node = $('countdown');
  if (node.dataset.target && !node.closest('.hidden')) node.textContent = countdownTo(node.dataset.target);
}, 1000);

if (token) {
  request('/auth/session').then((session) => showConsole(session.username || '')).catch(() => {
    token = '';
    sessionStorage.removeItem(tokenKey);
    showLogin('Your session expired. Sign in again to continue.');
  });
} else showLogin();
