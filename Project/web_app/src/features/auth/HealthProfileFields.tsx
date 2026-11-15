import type { HealthProfileDraft } from './types';

export function HealthProfileFields({ value, onChange, idPrefix }: {
  value: HealthProfileDraft;
  onChange: (value: HealthProfileDraft) => void;
  idPrefix: string;
}) {
  const update = (field: keyof HealthProfileDraft, next: string) => onChange({
    ...value,
    [field]: next,
    ...(field === 'birthdate' && next ? { age_years: '' } : {}),
    ...(field === 'age_years' && next ? { birthdate: '' } : {}),
  });
  const id = (name: string) => `${idPrefix}-${name}`;
  return <fieldset className="health-fields">
    <legend>Health and emergency details <span className="optional">Optional</span></legend>
    <p className="health-fields__note">Share only details you’re comfortable storing in this profile. These fields are not an emergency dispatch channel.</p>
    <div className="health-fields__grid">
      <label htmlFor={id('age')}>Age <span className="optional">Optional</span><input id={id('age')} type="number" min="0" max="120" step="1" inputMode="numeric" value={value.age_years} disabled={Boolean(value.birthdate)} onChange={event => update('age_years', event.target.value)} /></label>
      <label htmlFor={id('birthdate')}>Date of birth <span className="optional">Optional</span><input id={id('birthdate')} type="date" max={new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)} value={value.birthdate} onChange={event => update('birthdate', event.target.value)} /><small>Enter age or date of birth; age is calculated when a birthdate is provided.</small></label>
      <label htmlFor={id('gender')}>Gender <span className="optional">Optional</span><input id={id('gender')} autoComplete="off" maxLength={80} value={value.gender} onChange={event => update('gender', event.target.value)} /></label>
      <label htmlFor={id('pronouns')}>Pronouns <span className="optional">Optional</span><input id={id('pronouns')} autoComplete="off" maxLength={80} value={value.pronouns} onChange={event => update('pronouns', event.target.value)} /></label>
      <label htmlFor={id('blood-type')}>Blood type <span className="optional">Optional</span><select id={id('blood-type')} value={value.blood_type} onChange={event => update('blood_type', event.target.value)}><option value="">Not provided</option>{['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(type => <option key={type} value={type}>{type}</option>)}</select></label>
      <label htmlFor={id('emergency-name')}>Emergency contact <span className="optional">Optional</span><input id={id('emergency-name')} autoComplete="off" maxLength={100} value={value.emergency_contact_name} onChange={event => update('emergency_contact_name', event.target.value)} /></label>
      <label htmlFor={id('emergency-relationship')}>Contact relationship <span className="optional">Optional</span><input id={id('emergency-relationship')} autoComplete="off" maxLength={80} value={value.emergency_contact_relationship} onChange={event => update('emergency_contact_relationship', event.target.value)} /></label>
      <label htmlFor={id('emergency-phone')}>Contact phone <span className="optional">Optional</span><input id={id('emergency-phone')} type="tel" autoComplete="off" maxLength={40} value={value.emergency_contact_phone} onChange={event => update('emergency_contact_phone', event.target.value)} /></label>
      <label htmlFor={id('allergies')}>Allergies <span className="optional">Optional</span><textarea id={id('allergies')} rows={2} maxLength={2000} value={value.allergies} onChange={event => update('allergies', event.target.value)} placeholder="List known allergies, if any" /></label>
      <label htmlFor={id('conditions')}>Medical conditions <span className="optional">Optional</span><textarea id={id('conditions')} rows={2} maxLength={2000} value={value.medical_conditions} onChange={event => update('medical_conditions', event.target.value)} /></label>
      <label htmlFor={id('medications')}>Medications <span className="optional">Optional</span><textarea id={id('medications')} rows={2} maxLength={2000} value={value.medications} onChange={event => update('medications', event.target.value)} /></label>
    </div>
  </fieldset>;
}
