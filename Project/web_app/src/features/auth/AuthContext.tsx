import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { apiRequest } from '../../services/http';
import type { AstronautProfile, HealthProfileDraft, HealthProfilePatch, LoginResult } from './types';

type AuthValue = {
  token: string | null;
  profile: AstronautProfile | null;
  signIn: (username: string, password: string) => Promise<void>;
  register: (input: { username: string; password: string; display_name: string; mission: string } & HealthProfileDraft) => Promise<void>;
  updateProfile: (patch: { display_name?: string; mission?: string | null } & Partial<HealthProfilePatch>) => Promise<void>;
  signOut: () => Promise<string | null>;
  expire: () => void;
};
const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [profile, setProfile] = useState<AstronautProfile | null>(null);
  const expire = useCallback(() => { setToken(null); setProfile(null); }, []);
  const loadLogin = useCallback(async (path: string, body: unknown) => {
    const result = await apiRequest<LoginResult>(path, null, { method: 'POST', body: JSON.stringify(body) });
    setToken(result.access_token);
    try {
      const current = await apiRequest<AstronautProfile>('/api/v1/astronauts/me', result.access_token);
      setProfile(current);
    } catch (error) {
      setToken(null);
      throw error;
    }
  }, []);
  const signIn = useCallback((username: string, password: string) => loadLogin('/api/v1/auth/login', { username, password }), [loadLogin]);
  const register = useCallback(async (input: { username: string; password: string; display_name: string; mission: string } & HealthProfileDraft) => {
    const health = {
      age_years: input.birthdate || !input.age_years ? null : Number(input.age_years),
      birthdate: input.birthdate || null,
      gender: input.gender.trim() || null, pronouns: input.pronouns.trim() || null,
      blood_type: input.blood_type || null, allergies: input.allergies.trim() || null,
      medical_conditions: input.medical_conditions.trim() || null, medications: input.medications.trim() || null,
      emergency_contact_name: input.emergency_contact_name.trim() || null,
      emergency_contact_relationship: input.emergency_contact_relationship.trim() || null,
      emergency_contact_phone: input.emergency_contact_phone.trim() || null,
    };
    await apiRequest<AstronautProfile>('/api/v1/auth/register', null, { method: 'POST', body: JSON.stringify({ ...input, ...health, mission: input.mission || null }) });
    await loadLogin('/api/v1/auth/login', { username: input.username, password: input.password });
  }, [loadLogin]);
  const updateProfile = useCallback(async (patch: { display_name?: string; mission?: string | null } & Partial<HealthProfilePatch>) => {
    const updated = await apiRequest<AstronautProfile>('/api/v1/astronauts/me', token, { method: 'PATCH', body: JSON.stringify(patch) });
    setProfile(updated);
  }, [token]);
  const signOut = useCallback(async () => {
    let message: string | null = null;
    try { await apiRequest<void>('/api/v1/auth/logout', token, { method: 'POST' }); }
    catch { message = 'Your local session was cleared, but server logout was not confirmed.'; }
    expire();
    return message;
  }, [expire, token]);
  const value = useMemo(() => ({ token, profile, signIn, register, updateProfile, signOut, expire }), [token, profile, signIn, register, updateProfile, signOut, expire]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
