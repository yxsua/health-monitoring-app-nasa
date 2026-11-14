import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const isRegister = mode === 'register';
  const { signIn, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [values, setValues] = useState({ username: '', password: '', display_name: '', mission: '' });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      if (isRegister) await register(values); else await signIn(values.username, values.password);
      navigate(location.state?.from?.pathname ?? '/dashboard', { replace: true });
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'The request could not be completed.'); }
    finally { setBusy(false); }
  }
  return <main className="auth-layout">
    <aside className="auth-aside">
      <div className="brand brand--large"><span className="brand-mark" aria-hidden="true">M</span><span>Mission Health Console</span></div>
      <div className="auth-aside__copy"><p className="eyebrow">LOCAL ASTRONAUT HEALTH</p><h1>Monitoring and wellbeing assessments</h1><div className="auth-facts"><p>Simulated measurements are labeled as fixture data.</p><p>Assessment questions and scores come from the local service.</p><p>The main risk engine and real sensor feeds are not included.</p></div></div>
      <div className="auth-aside__foot"><span className="status-dot" /> Local services only <span className="divider">/</span> No external sign-in</div>
    </aside>
    <section className="auth-panel" aria-labelledby="auth-title">
      <div className="auth-card">
        <p className="eyebrow">{isRegister ? 'NEW ACCOUNT' : 'ASTRONAUT ACCESS'}</p>
        <h2 id="auth-title">{isRegister ? 'Create your profile' : 'Sign in to your account'}</h2>
        <p className="muted">{isRegister ? 'Your profile is stored by the local identity service.' : 'Use the account registered with the local identity service.'}</p>
        {!isRegister && location.state?.logoutMessage && <p className="notice notice--error" role="status">{location.state.logoutMessage}</p>}
        <form onSubmit={submit} className="form-stack">
          {isRegister && <label>Display name<input autoComplete="name" required maxLength={100} value={values.display_name} onChange={e => setValues({ ...values, display_name: e.target.value })} /></label>}
          <label>Username<input autoComplete="username" required minLength={3} maxLength={40} pattern="[A-Za-z0-9_.-]+" value={values.username} onChange={e => setValues({ ...values, username: e.target.value })} /></label>
          <label>Password<input type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} required minLength={8} maxLength={128} value={values.password} onChange={e => setValues({ ...values, password: e.target.value })} /></label>
          {isRegister && <label>Mission <span className="optional">Optional</span><input maxLength={100} value={values.mission} onChange={e => setValues({ ...values, mission: e.target.value })} /></label>}
          {error && <p className="notice notice--error" role="alert">{error}</p>}
          <button className="button button--primary button--full" disabled={busy}>{busy ? 'Connecting…' : isRegister ? 'Create profile' : 'Sign in'}</button>
        </form>
        <p className="auth-switch">{isRegister ? 'Already have a profile?' : 'New to the console?'} <Link to={isRegister ? '/login' : '/register'}>{isRegister ? 'Sign in' : 'Create a profile'}</Link></p>
        <p className="auth-note">Access token stays in memory and clears when this page reloads.</p>
      </div>
    </section>
  </main>;
}
