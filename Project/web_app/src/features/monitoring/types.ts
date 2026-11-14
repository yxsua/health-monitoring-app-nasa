export type Reading = { value: number | null; unit: string; observed_at: string | null; quality: 'valid' | 'missing' | 'invalid'; period_start: string | null; period_end: string | null };
export type Observation = {
  record_id: string; astronaut_id: string; observed_at: string; mission: string; source: 'simulated';
  physiological: Record<string, Reading>;
  self_assessment: Record<string, Reading>;
  environment: Record<string, Reading>;
};
export type SimulationResponse = { schema_version: '1.1.0'; run_id: string; scenario_id: string; seed: number; generator_version: string; simulation_time: string; items: Observation[]; next_cursor: null };
