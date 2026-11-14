export type AstronautProfile = {
  astronaut_id: string;
  username: string;
  display_name: string;
  mission: string | null;
  created_at: string;
  updated_at: string;
};

export type LoginResult = { access_token: string; token_type: string; expires_at: string; astronaut: AstronautProfile };
