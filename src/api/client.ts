export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = `${apiBaseUrl}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch {
    throw new Error(`Network error while calling ${path}. Is the API running?`);
  }

  const body = (await response.json().catch(() => null)) as T | null;
  if (!response.ok) {
    throw new Error(`API ${response.status} from ${path}`);
  }
  if (body == null) {
    throw new Error(`Empty response from ${path}`);
  }
  return body;
}

export async function apiPost<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const url = `${apiBaseUrl}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch {
    throw new Error(`Network error while calling ${path}. Is the API running?`);
  }

  const resBody = (await response.json().catch(() => null)) as T | null;
  if (!response.ok) {
    const errorMsg = (resBody as { detail?: string })?.detail || `API ${response.status} from ${path}`;
    throw new Error(errorMsg);
  }
  if (resBody == null) {
    throw new Error(`Empty response from ${path}`);
  }
  return resBody;
}

