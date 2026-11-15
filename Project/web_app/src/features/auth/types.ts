export type AstronautProfile = {
  astronaut_id: string;
  username: string;
  display_name: string;
  mission: string | null;
  age_years: number | null;
  birthdate: string | null;
  gender: string | null;
  pronouns: string | null;
  blood_type: string | null;
  allergies: string | null;
  medical_conditions: string | null;
  medications: string | null;
  emergency_contact_name: string | null;
  emergency_contact_relationship: string | null;
  emergency_contact_phone: string | null;
  created_at: string;
  updated_at: string;
};

export type LoginResult = { access_token: string; token_type: string; expires_at: string; astronaut: AstronautProfile };

export type HealthProfileDraft = {
  age_years: string;
  birthdate: string;
  gender: string;
  pronouns: string;
  blood_type: string;
  allergies: string;
  medical_conditions: string;
  medications: string;
  emergency_contact_name: string;
  emergency_contact_relationship: string;
  emergency_contact_phone: string;
};

export type HealthProfilePatch = {
  age_years: number | null;
  birthdate: string | null;
  gender: string | null;
  pronouns: string | null;
  blood_type: string | null;
  allergies: string | null;
  medical_conditions: string | null;
  medications: string | null;
  emergency_contact_name: string | null;
  emergency_contact_relationship: string | null;
  emergency_contact_phone: string | null;
};

export function emptyHealthProfileDraft(): HealthProfileDraft {
  return { age_years: '', birthdate: '', gender: '', pronouns: '', blood_type: '', allergies: '', medical_conditions: '', medications: '', emergency_contact_name: '', emergency_contact_relationship: '', emergency_contact_phone: '' };
}

export function healthDraftFromProfile(profile: AstronautProfile | null): HealthProfileDraft {
  const empty = emptyHealthProfileDraft();
  if (!profile) return empty;
  return {
    age_years: profile.age_years === null ? '' : String(profile.age_years),
    birthdate: profile.birthdate ?? '', gender: profile.gender ?? '', pronouns: profile.pronouns ?? '',
    blood_type: profile.blood_type ?? '', allergies: profile.allergies ?? '',
    medical_conditions: profile.medical_conditions ?? '', medications: profile.medications ?? '',
    emergency_contact_name: profile.emergency_contact_name ?? '',
    emergency_contact_relationship: profile.emergency_contact_relationship ?? '',
    emergency_contact_phone: profile.emergency_contact_phone ?? '',
  };
}

export function healthPatchFromDraft(value: HealthProfileDraft): HealthProfilePatch {
  const text = (input: string) => input.trim() || null;
  return {
    age_years: value.birthdate || !value.age_years ? null : Number(value.age_years),
    birthdate: value.birthdate || null,
    gender: text(value.gender), pronouns: text(value.pronouns), blood_type: value.blood_type || null,
    allergies: text(value.allergies), medical_conditions: text(value.medical_conditions), medications: text(value.medications),
    emergency_contact_name: text(value.emergency_contact_name),
    emergency_contact_relationship: text(value.emergency_contact_relationship),
    emergency_contact_phone: text(value.emergency_contact_phone),
  };
}
