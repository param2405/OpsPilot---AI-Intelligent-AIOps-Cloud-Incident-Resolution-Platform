import { apiBaseUrl, apiGet } from "./client";

export type HealthResponse = {
  status: string;
  service: string;
  environment: string;
  version: string;
};

export type ReadinessResponse = {
  status: string;
  service: string;
  environment: string;
  version: string;
  database: {
    connected: boolean;
    detail: string;
  };
};

export function getLiveness(signal?: AbortSignal): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/api/v1/health", signal);
}

export async function getReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  const url = `${apiBaseUrl}/api/v1/health/ready`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch {
    throw new Error("Network error while calling /api/v1/health/ready. Is the API running?");
  }

  const body = (await response.json().catch(() => null)) as ReadinessResponse | null;
  if ((response.status === 200 || response.status === 503) && body) {
    return body;
  }
  throw new Error(`API ${response.status} from /api/v1/health/ready`);
}
