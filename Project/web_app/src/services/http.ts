export type ApiError = Error & { status?: number };

export async function apiRequest<T>(path: string, token?: string | null, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      cache: 'no-store',
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw Object.assign(new Error('Local service is unavailable. Start the required backend and try again.'), { status: 0 });
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = new Error(payload?.error?.message ?? `Request failed (${response.status}).`) as ApiError;
    error.status = response.status;
    if (response.status === 401 && token) window.dispatchEvent(new CustomEvent('auth:expired'));
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
