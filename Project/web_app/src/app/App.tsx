import { useEffect } from 'react';
import { Link, NavLink, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AuthPage } from '../features/auth/AuthPages';
import { useAuth } from '../features/auth/AuthContext';
import { Dashboard } from '../features/monitoring/Dashboard';
import { RecommendationOverlay } from '../features/monitoring/RecommendationOverlay';
import { Wellbeing } from '../features/chatbot/Wellbeing';
import { SessionPage } from '../features/chatbot/SessionPage';
import { ResultPage, HistoryPage } from '../features/chatbot/Results';
import { ProfilePage } from '../features/auth/ProfilePage';
import { MissionControlPage } from '../features/monitoring/MissionControlPage';

function Protected() {
  const { token } = useAuth(); const location = useLocation();
  return token ? <Outlet /> : <Navigate to="/login" replace state={{ from: location }} />;
}
function Shell() {
  const { profile, signOut, expire } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    const onUnauthorized = () => { expire(); navigate('/login', { replace: true }); };
    window.addEventListener('auth:expired', onUnauthorized);
    return () => window.removeEventListener('auth:expired', onUnauthorized);
  }, [expire, navigate]);
  async function logout() {
    const message = await signOut(); navigate('/login', { replace: true, state: message ? { logoutMessage: message } : undefined });
  }
  return <div className="app-shell">
    <header className="topbar">
      <Link to="/dashboard" className="brand" aria-label="AstraHealth overview"><img className="brand-mark" src="/logo-mark.png" alt="" aria-hidden="true" /><span>AstraHealth</span></Link>
      <nav className="main-nav" aria-label="Main navigation">
        <NavLink to="/dashboard">Overview</NavLink><NavLink to="/wellbeing">Wellbeing</NavLink><NavLink to="/wellbeing/history">History</NavLink><NavLink to="/mission-control">Mission Control</NavLink>
      </nav>
      <div className="topbar__account"><span className="account-name">{profile?.display_name}</span><button className="button button--quiet" onClick={() => navigate('/profile')}>Profile</button><button className="button button--quiet" onClick={logout}>Sign out</button></div>
    </header>
    <RecommendationOverlay />
    <div hidden={location.pathname !== '/dashboard'}><Dashboard /></div>
    <Outlet />
  </div>;
}

export function App() {
  const { token } = useAuth();
  return <Routes>
    <Route path="/login" element={token ? <Navigate to="/dashboard" replace /> : <AuthPage mode="login" />} />
    <Route path="/register" element={token ? <Navigate to="/dashboard" replace /> : <AuthPage mode="register" />} />
    <Route element={<Protected />}><Route element={<Shell />}>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={null} />
      <Route path="/wellbeing" element={<Wellbeing />} />
      <Route path="/wellbeing/sessions/:sessionId" element={<SessionPage />} />
      <Route path="/wellbeing/results/:sessionId" element={<ResultPage />} />
      <Route path="/wellbeing/history" element={<HistoryPage />} />
      <Route path="/mission-control" element={<MissionControlPage />} />
      <Route path="/profile" element={<ProfilePage />} />
    </Route></Route>
    <Route path="*" element={<Navigate to={token ? '/dashboard' : '/login'} replace />} />
  </Routes>;
}
