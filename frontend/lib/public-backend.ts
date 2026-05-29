const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function publicFetch<T>(path: string): Promise<T> {
  return publicBackendFetch<T>(path);
}

export async function publicBackendFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const response = await fetch(`${backendUrl}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const message = await readBackendError(response);
    throw new Error(`Public backend request failed for ${path} (${response.status}): ${message}`);
  }
  return parseJsonResponse<T>(response, path);
}

async function parseJsonResponse<T>(response: Response, path: string): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const body = await response.text();

  if (!contentType.includes("application/json")) {
    throw new Error(
      `Backend returned non-JSON for ${path}. Check BACKEND_URL. Received ${response.status} ${contentType}: ${body.slice(0, 120)}`
    );
  }

  return JSON.parse(body) as T;
}

async function readBackendError(response: Response): Promise<string> {
  const body = await response.text();
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const parsed = JSON.parse(body) as unknown;
      if (typeof parsed === "string" && parsed.trim()) {
        return parsed;
      }
      if (parsed && typeof parsed === "object") {
        const detail = (parsed as { detail?: unknown; message?: unknown }).detail ?? (parsed as { message?: unknown }).message;
        if (typeof detail === "string" && detail.trim()) {
          return detail;
        }
        if (detail != null) {
          return JSON.stringify(detail);
        }
      }
    } catch {
      // Fall back to the raw body below.
    }
  }

  const trimmed = body.trim();
  return trimmed || `HTTP ${response.status}`;
}
