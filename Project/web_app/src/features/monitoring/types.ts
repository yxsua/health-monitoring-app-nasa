export type Reading = { value: number | null; unit: string; observed_at: string | null; quality: 'valid' | 'missing' | 'invalid'; period_start: string | null; period_end: string | null };
export type Observation = {
  record_id: string; astronaut_id: string; observed_at: string; mission: string; source: 'simulated';
  physiological: Record<string, Reading>;
  self_assessment: Record<string, Reading>;
  environment: Record<string, Reading>;
};
export type ScenarioTransition = { active: boolean; step: number; total_steps: number };
export type SimulationResponse = { schema_version: '1.1.0'; run_id: string; scenario_id: string; seed: number; generator_version: string; simulation_time: string; scenario_transition: ScenarioTransition; items: Observation[]; next_cursor: null };
export type AnalysisComponentStatus = 'available' | 'warming_up' | 'insufficient_data' | 'unavailable';
export type AnalysisAlert = {
  code: string; severity: 'caution' | 'warning' | 'critical'; system: string; message: string;
  evidence: Array<{ field: string; value: number | null; unit: string; quality: 'valid' | 'missing' | 'invalid' }>;
  procedure_id: string | null;
};
export type AnalysisResponse = {
  contract_version: '1.1.0'; run_id: string; astronaut_id: string;
  scenario_id: 'normal' | 'solar_event' | 'high_co2' | 'prolonged_isolation'; record_id: string;
  observed_at: string; analyzed_at: string; analysis_status: 'complete' | 'partial' | 'unavailable';
  rules: {
    status: AnalysisComponentStatus; version: string; overall_level: 'normal' | 'caution' | 'warning' | 'critical' | null;
    alerts: AnalysisAlert[]; input_quality: { valid: number; missing: number; invalid: number };
    window_size: number; window_available: number;
  };
  anomaly: {
    status: AnalysisComponentStatus; reason: string | null; model_id: string; model_version: string | null;
    is_anomaly: boolean | null; score: number | null; score_meaning: string;
  };
  forecast: {
    status: AnalysisComponentStatus; reason: string | null; model_id: string; model_version: string | null;
    window_required: number; window_available: number; sample_period_seconds: number;
    horizon_seconds: number | null; target_time: string | null;
    values: Record<string, { value: number; unit: string }> | null;
  };
};
