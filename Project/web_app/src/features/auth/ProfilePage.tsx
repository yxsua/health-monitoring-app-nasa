import { useState, type FormEvent } from 'react';
import { useAuth } from './AuthContext';
import { HealthProfileFields } from './HealthProfileFields';
import { healthDraftFromProfile, healthPatchFromDraft } from './types';

export function ProfilePage() {
  const { profile, updateProfile } = useAuth();
  const [name, setName] = useState(profile?.display_name ?? ''); const [mission, setMission] = useState(profile?.mission ?? '');
  const [health, setHealth] = useState(() => healthDraftFromProfile(profile));
  const [status, setStatus] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setStatus(''); setError('');
    try { await updateProfile({ display_name: name, mission: mission || null, ...healthPatchFromDraft(health) }); setStatus('Profile saved.'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Profile could not be saved.'); }
    finally { setBusy(false); }
  }
  return <main className="page-content page-content--narrow"><div className="page-heading"><div><p className="eyebrow">ACCOUNT</p><h1>Profile</h1><p className="lead">Update account, wellbeing, and emergency details. Health fields are optional.</p></div></div>
    <form className="panel profile-form form-stack" onSubmit={save}><label>Display name<input required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label><label>Mission <span className="optional">Optional</span><input maxLength={100} value={mission} onChange={e => setMission(e.target.value)} /></label><HealthProfileFields value={health} onChange={setHealth} idPrefix="profile" /><div className="profile-id"><span>Astronaut ID</span><code>{profile?.astronaut_id}</code></div>{error && <p className="notice notice--error" role="alert">{error}</p>}{status && <p className="notice notice--success" role="status">{status}</p>}<button className="button button--primary" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button></form>
  </main>;
}
